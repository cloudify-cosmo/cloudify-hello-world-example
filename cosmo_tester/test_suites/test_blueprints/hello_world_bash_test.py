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

__author__ = 'elip'

import requests
from neutronclient.common.exceptions import NeutronException
from novaclient.exceptions import NotFound
from retrying import retry

from cosmo_tester.framework.util import YamlPatcher
from cosmo_tester.framework.testenv import TestCase
from cosmo_tester.framework.util import get_yaml_as_dict
from cosmo_tester.framework.handlers.openstack import openstack_clients
from cosmo_tester.framework.git_helper import clone


CLOUDIFY_HELLO_WORLD_EXAMPLE_URL = "https://github.com/cloudify-cosmo/" \
                                   "cloudify-hello-world-example.git"


class HelloWorldBashTest(TestCase):

    def test_hello_world_on_ubuntu(self):
        self._run(self.env.ubuntu_image_name, self.env.cloudify_agent_user)

    def test_hello_world_with_reinstall(self):
        self._run(self.env.ubuntu_image_name, self.env.cloudify_agent_user)
        self._run(self.env.ubuntu_image_name, self.env.cloudify_agent_user,
                  is_existing_deployment=True)

    # def test_hello_world_uninstall_after_failure(self):
    #     try:
    #         self._run(self.env.ubuntu_image_name, self.env.cloudify_agent_user,
    #                   vm_security_group='gibberish')
    #         self.fail('Install should have failed!')
    #     except Exception as e:
    #         # verifying the install failed where we expected it to fail.
    #         # TODO: verify the actual error is really the expected one
    #         floating_ip_id, neutron, nova, sg_id, _ = \
    #             self._verify_deployment_installed(with_server=False)
    #         self.logger.info("failed to install, as expected ({0}) ".format(e))
    #
    #     self._uninstall_and_make_assertions(
    #         floating_ip_id, neutron, nova, sg_id)

    def test_hello_world_on_centos(self):
        self._run(self.env.centos_image_name, self.env.centos_image_user)

    def _run(self, image_name, user, is_existing_deployment=False,
             vm_security_group='webserver_security_group'):
        if not is_existing_deployment:
            self.repo_dir = clone(CLOUDIFY_HELLO_WORLD_EXAMPLE_URL,
                                  self.workdir)
            self.blueprint_path = self.repo_dir / 'hello-world'
            self.blueprint_yaml = self.blueprint_path / 'blueprint.yaml'
            modify_yaml(env=self.env,
                        yaml_file=self.blueprint_yaml,
                        host_name='bash-web-server',
                        image_name=image_name,
                        user=user,
                        security_groups=[vm_security_group])

            self.upload_deploy_and_execute_install(fetch_state=False)
        else:
            self.execute_install(deployment_id=self.test_id, fetch_state=False)

        floating_ip_id, neutron, nova, sg_id, server_id =\
            self._verify_deployment_installed()

        self._uninstall_and_make_assertions(floating_ip_id, neutron, nova,
                                            sg_id, server_id)

    def _verify_deployment_installed(self, with_server=True):
        (floatingip_node, security_group_node, server_node) = self._instances()

        nova, neutron = openstack_clients(self.env.cloudify_config)

        server_id = None
        if with_server:
            verify_webserver_running(blueprint_yaml=self.blueprint_yaml,
                                     floatingip_node=floatingip_node)

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
def verify_webserver_running(blueprint_yaml, floatingip_node):
    """
    This method is also used by two_deployments_test!
    """
    blueprint = get_yaml_as_dict(blueprint_yaml)
    webserver_props = blueprint['node_templates']['http_web_server'][
        'properties']
    server_port = webserver_props['port']
    server_ip = floatingip_node.runtime_properties['floating_ip_address']
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


def modify_yaml(env, yaml_file, host_name, security_groups,
                image_name=None,
                user=None,
                security_group_name=None):
    """
    This method is also used by two_deployments_test!
    """
    if image_name is None:
        image_name = env.ubuntu_image_name
    if user is None:
        user = env.cloudify_agent_user
    with YamlPatcher(yaml_file) as patch:
        vm_properties_path = 'node_templates.vm.properties'
        patch.merge_obj('{0}.cloudify_agent'.format(vm_properties_path), {
            'user': user,
        })
        patch.merge_obj('{0}.server'.format(vm_properties_path), {
            'name': host_name,
            'image_name': image_name,
            'flavor_name': env.flavor_name,
            'security_groups': security_groups,
        })
        sg_name_path = 'node_templates.security_group.properties' \
                       '.security_group.name'
        if security_group_name is not None:
            patch.set_value(sg_name_path, security_group_name)
