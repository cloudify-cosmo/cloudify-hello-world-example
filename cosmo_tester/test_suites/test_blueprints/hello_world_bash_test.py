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

from cosmo_tester.framework.util import YamlPatcher
from cosmo_tester.framework.testenv import TestCase
from cosmo_tester.framework.util import get_yaml_as_dict
from cosmo_tester.framework.openstack_api import openstack_clients
from cosmo_tester.framework.git_helper import clone


class HelloWorldBashTest(TestCase):

    CLOUDIFY_EXAMPLES_URL = "https://github.com/cloudify-cosmo/" \
                            "cloudify-examples.git"

    def test_hello_world_bash(self):
        self.repo_dir = clone(self.CLOUDIFY_EXAMPLES_URL, self.workdir)
        self.blueprint_path = self.repo_dir / 'hello-world'
        self.blueprint_yaml = self.blueprint_path / 'blueprint.yaml'
        self.modify_yaml(env=self.env,
                         yaml_file=self.blueprint_yaml,
                         host_name='bash-web-server',
                         security_groups=['webserver_security_group'])

        self.upload_deploy_and_execute_install(fetch_state=False)

        (floatingip_node,
         security_group_node,
         server_node) = self.get_instances(client=self.client,
                                           deployment_id=self.test_id)

        self.verify_webserver_running(blueprint_yaml=self.blueprint_yaml,
                                      floatingip_node=floatingip_node)

        nova, neutron = openstack_clients(self.env.cloudify_config)

        server_id = server_node.runtime_properties['openstack_server_id']
        floating_ip_id = floatingip_node.runtime_properties['external_id']
        sg_id = security_group_node.runtime_properties['external_id']

        nova_server = nova.servers.get(server_id)
        neutron_floating_ip = neutron.show_floatingip(floating_ip_id)
        neutron_sg = neutron.show_security_group(sg_id)
        self.logger.info("Agent server : {0}".format(nova_server))
        self.logger.info("Floating ip : {0}".format(neutron_floating_ip))
        self.logger.info("Agent security group : {0}".format(neutron_sg))

        self.execute_uninstall()
        # No components should exist after uninstall
        self.assertRaises(NotFound, nova.servers.get, server_id)
        self.assertRaises(NeutronException, neutron.show_security_group, sg_id)
        self.assertRaises(NeutronException, neutron.show_floatingip,
                          floating_ip_id)

    @staticmethod
    def verify_webserver_running(blueprint_yaml, floatingip_node):
        blueprint = get_yaml_as_dict(blueprint_yaml)
        webserver_props = blueprint['blueprint']['nodes'][3]['properties']
        server_port = webserver_props['port']
        server_ip = floatingip_node.runtime_properties['floating_ip_address']
        server_response = requests.get('http://{0}:{1}'.format(server_ip,
                                                               server_port))
        if server_response.status_code != 200:
            raise AssertionError('Unexpected status code: {}'
                                 .format(server_response.status_code))

    @staticmethod
    def get_instances(client, deployment_id):
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

    @staticmethod
    def modify_yaml(env, yaml_file, host_name, security_groups):
        with YamlPatcher(yaml_file) as patch:
            vm_properties_path = 'blueprint.nodes[2].properties'
            patch.merge_obj('{0}.server'.format(vm_properties_path), {
                'name': host_name,
                'image_name': env.ubuntu_image_name,
                'flavor_name': env.flavor_name,
                'security_groups': security_groups,
            })
