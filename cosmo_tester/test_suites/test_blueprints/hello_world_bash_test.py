########
# Copyright (c) 2014 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.


import requests
from neutronclient.common.exceptions import NeutronException
from novaclient.exceptions import NotFound
from retrying import retry
import nose.tools

from cosmo_tester.framework.testenv import TestCase
from cosmo_tester.framework.git_helper import clone


CLOUDIFY_HELLO_WORLD_EXAMPLE_URL = "https://github.com/cloudify-cosmo/" \
                                   "cloudify-hello-world-example.git"


class HelloWorldBashTest(TestCase):

    def test_hello_world_on_ubuntu(self):
        self._run(self.env.ubuntu_image_name, self.env.cloudify_agent_user)
        # checking reinstallation scenario
        self._run(self.env.ubuntu_image_name, self.env.cloudify_agent_user,
                  is_existing_deployment=True)

    # TODO: enable this test once the issue with validating agent plugins is
    #       resolved - right now it'll fail because the VM creation is where
    #       the execution should fail
    @nose.tools.nottest
    def test_hello_world_uninstall_after_failure(self):
        try:
            self._run(self.env.ubuntu_image_name,
                      self.env.cloudify_agent_user,
                      vm_security_group='gibberish')
            self.fail('Install should have failed!')
        except Exception as e:
            # verifying the install failed where we expected it to fail.
            # TODO: verify the actual error is really the expected one
            floating_ip_id, neutron, nova, sg_id, _ = \
                self._verify_deployment_installed(with_server=False)
            self.logger.info("failed to install, as expected ({0})"
                             .format(e))

        self._uninstall_and_make_assertions(
            floating_ip_id, neutron, nova, sg_id)

    def test_hello_world_on_centos(self):
        self._run(self.env.centos_image_name, self.env.centos_image_user)

    def assert_events(self):
        deployment_by_id = self.client.deployments.get(self.test_id)
        executions = self.client.executions.list(
            deployment_id=deployment_by_id.id)
        execution_from_list = executions[0]
        execution_by_id = self.client.executions.get(execution_from_list.id)
        events, total_events = self.client.events.get(execution_by_id.id)
        self.assertGreater(len(events), 0,
                           'Expected at least 1 event for execution id: {0}'
                           .format(execution_by_id.id))

    def _run(self, image_name, user, is_existing_deployment=False):
        if not is_existing_deployment:
            self.repo_dir = clone(CLOUDIFY_HELLO_WORLD_EXAMPLE_URL,
                                  self.workdir)
            self.blueprint_path = self.repo_dir / 'hello-world'
            self.blueprint_yaml = self.blueprint_path / 'blueprint.yaml'
            self.upload_deploy_and_execute_install(
                fetch_state=False,
                inputs=dict(
                    agent_user=user,
                    image_name=image_name,
                    flavor_name=self.env.flavor_name))
        else:
            self.execute_install(deployment_id=self.test_id, fetch_state=False)

        # We assert for events to test events are actually
        # sent in a real world environment.
        # This is the only test that needs to make this assertion.
        self.assert_events()

        floating_ip_id, neutron, nova, sg_id, server_id =\
            self._verify_deployment_installed()

        self._uninstall_and_make_assertions(floating_ip_id, neutron, nova,
                                            sg_id, server_id)

    def _verify_deployment_installed(self, with_server=True):
        (floatingip_node, security_group_node, server_node) = self._instances()

        nova, neutron = self.env.handler.openstack_clients()

        server_id = None
        if with_server:
            verify_webserver_running(
                web_server_node=get_web_server_node(
                    self.client, self.test_id),
                floatingip_node_instance=floatingip_node)

            server_id = server_node.runtime_properties['external_id']
            nova_server = nova.servers.get(server_id)
            self.logger.info("Agent server : {0}".format(nova_server))
        else:
            self.assertNotIn('external_id', server_node.runtime_properties)

        floating_ip_id = floatingip_node.runtime_properties['external_id']
        neutron_floating_ip = neutron.show_floatingip(floating_ip_id)
        self.logger.info("Floating ip : {0}".format(neutron_floating_ip))
        sg_id = security_group_node.runtime_properties['external_id']
        neutron_sg = neutron.show_security_group(sg_id)
        self.logger.info("Agent security group : {0}".format(neutron_sg))
        return floating_ip_id, neutron, nova, sg_id, server_id

    def _uninstall_and_make_assertions(self, floating_ip_id, neutron, nova,
                                       sg_id, server_id=None):
        self.execute_uninstall()
        self._assert_components_cleared(floating_ip_id, neutron, nova,
                                        sg_id, server_id)
        self._assert_nodes_deleted()

    def _assert_components_cleared(self, floating_ip_id, neutron, nova,
                                   sg_id, server_id=None):
        if server_id:
            self.assertRaises(NotFound, nova.servers.get, server_id)
        self.assertRaises(NeutronException, neutron.show_security_group, sg_id)
        self.assertRaises(NeutronException, neutron.show_floatingip,
                          floating_ip_id)

    def _assert_nodes_deleted(self):
        (floatingip_node, security_group_node, server_node) = self._instances()
        expected_node_state = 'deleted'
        self.assertEquals(expected_node_state, floatingip_node.state)
        self.assertEquals(expected_node_state, security_group_node.state)
        self.assertEquals(expected_node_state, server_node.state)
        self.assertEquals(0, len(floatingip_node.runtime_properties))
        self.assertEquals(0, len(security_group_node.runtime_properties))
        self.assertEquals(0, len(server_node.runtime_properties))

    def _instances(self):
        return get_instances(client=self.client, deployment_id=self.test_id)


@retry(stop_max_attempt_number=5, wait_fixed=3000)
def verify_webserver_running(web_server_node, floatingip_node_instance):
    """
    This method is also used by two_deployments_test!
    """
    server_port = web_server_node.properties['port']
    server_ip = \
        floatingip_node_instance.runtime_properties['floating_ip_address']
    server_response = requests.get('http://{0}:{1}'.format(server_ip,
                                                           server_port))
    if server_response.status_code != 200:
        raise AssertionError('Unexpected status code: {}'
                             .format(server_response.status_code))


def get_instances(client, deployment_id):
    """
    This method is also used by two_deployments_test!
    """
    server_node = None
    security_group_node = None
    floatingip_node = None
    instances = client.node_instances.list(
        deployment_id=deployment_id)
    for instance in instances:
        if instance.node_id == 'virtual_ip':
            floatingip_node = instance
        if instance.node_id == 'security_group':
            security_group_node = instance
        if instance.node_id == 'vm':
            server_node = instance
    return floatingip_node, security_group_node, server_node


def get_web_server_node(client, deployment_id):
    """
    This method is also used by two_deployments_test!
    """
    return client.nodes.get(deployment_id=deployment_id,
                            node_id='http_web_server')
