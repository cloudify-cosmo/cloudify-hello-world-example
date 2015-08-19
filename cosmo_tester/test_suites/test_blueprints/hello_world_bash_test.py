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

from cosmo_tester.framework.git_helper import clone
from cosmo_tester.framework.test_cases import MonitoringTestCase


CLOUDIFY_HELLO_WORLD_EXAMPLE_URL = "https://github.com/cloudify-cosmo/" \
                                   "cloudify-hello-world-example.git"


class AbstractHelloWorldTest(MonitoringTestCase):

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

    def _run(self,
             inputs=None,
             blueprint_file='blueprint.yaml',
             is_existing_deployment=False):
        if not is_existing_deployment:
            self.repo_dir = clone(CLOUDIFY_HELLO_WORLD_EXAMPLE_URL,
                                  self.workdir)
            self.blueprint_yaml = self.repo_dir / blueprint_file
            self.upload_deploy_and_execute_install(
                fetch_state=False,
                inputs=inputs)
        else:
            self.execute_install(deployment_id=self.test_id, fetch_state=False)

        # We assert for events to test events are actually
        # sent in a real world environment.
        # This is the only test that needs to make this assertion.
        self.logger.info('Asserting events...')
        self.assert_events()

        outputs = self.client.deployments.outputs.get(self.test_id)['outputs']
        self.logger.info('Deployment outputs: {0}'.format(outputs))
        self.logger.info('Verifying web server is running on: {0}'.format(
            outputs['http_endpoint']))
        verify_webserver_running(outputs['http_endpoint'])

        self.logger.info('Performing post install assertions...')
        context = self._do_post_install_assertions()

        self.logger.info('Asserting deployment monitoring data exists...')
        self.assert_deployment_monitoring_data_exists()

        self.logger.info('Uninstalling deployment...')
        self.execute_uninstall()

        self.logger.info('Performing post uninstall assertions...')
        self._do_post_uninstall_assertions(context)

    def _do_post_install_assertions(self):
        pass

    def _do_post_uninstall_assertions(self, context):
        pass

    def _instances(self):
        return get_instances(client=self.client, deployment_id=self.test_id)


class HelloWorldBashTest(AbstractHelloWorldTest):

    def test_hello_world_on_ubuntu(self):
        inputs = {
            'agent_user': self.env.cloudify_agent_user,
            'image': self.env.ubuntu_image_name,
            'flavor': self.env.flavor_name
        }
        self._run(inputs=inputs)
        # checking reinstallation scenario
        self._run(inputs=inputs, is_existing_deployment=True)

    def test_hello_world_on_centos(self):
        inputs = {
            'agent_user': self.env.centos_image_user,
            'image': self.env.centos_image_name,
            'flavor': self.env.flavor_name
        }
        self._run(inputs=inputs)

    def _do_post_install_assertions(self):
        (floatingip_node, security_group_node, server_node) = self._instances()
        nova, neutron, _ = self.env.handler.openstack_clients()
        server_id = server_node.runtime_properties['external_id']
        nova_server = nova.servers.get(server_id)
        self.logger.info("Agent server : {0}".format(nova_server))

        floating_ip_id = floatingip_node.runtime_properties['external_id']
        neutron_floating_ip = neutron.show_floatingip(floating_ip_id)
        self.logger.info("Floating ip : {0}".format(neutron_floating_ip))
        sg_id = security_group_node.runtime_properties['external_id']
        neutron_sg = neutron.show_security_group(sg_id)
        self.logger.info("Agent security group : {0}".format(neutron_sg))

        return {
            'floatingip_id': floating_ip_id,
            'security_group_id': sg_id,
            'server_id': server_id
        }

    def _do_post_uninstall_assertions(self, context):
        self._assert_nodes_deleted()

        nova, neutron, _ = self.env.handler.openstack_clients()
        server_id = context.get('server_id')
        if server_id:
            self.assertRaises(NotFound, nova.servers.get, server_id)
        self.assertRaises(NeutronException,
                          neutron.show_security_group,
                          context['security_group_id'])
        self.assertRaises(NeutronException,
                          neutron.show_floatingip,
                          context['floatingip_id'])

    def _assert_nodes_deleted(self):
        (floatingip_node, security_group_node, server_node) = self._instances()
        expected_node_state = 'deleted'
        self.assertEquals(expected_node_state, floatingip_node.state)
        self.assertEquals(expected_node_state, security_group_node.state)
        self.assertEquals(expected_node_state, server_node.state)
        self.assertEquals(0, len(floatingip_node.runtime_properties))
        self.assertEquals(0, len(security_group_node.runtime_properties))
        # CFY-2670 - diamond plugin leaves one runtime property at this time
        self.assertEquals(1, len(server_node.runtime_properties))


@retry(stop_max_attempt_number=10, wait_fixed=5000)
def verify_webserver_running(http_endpoint):
    """
    This method is also used by two_deployments_test!
    """
    server_response = requests.get(http_endpoint, timeout=15)
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
