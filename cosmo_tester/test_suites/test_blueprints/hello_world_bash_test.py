from neutronclient.common.exceptions import NeutronException
from novaclient.exceptions import NotFound

from cosmo_tester.framework.util import YamlPatcher


__author__ = 'elip'

from cosmo_tester.framework.testenv import TestCase
from cosmo_tester.framework.util import get_yaml_as_dict
from cosmo_tester.framework.openstack_api import openstack_clients

import requests


class HelloWorldBashTest(TestCase):

    CLOUDIFY_EXAMPLES_URL = "https://github.com/cloudify-cosmo/" \
                            "cloudify-examples.git"

    host_name = 'bash-web-server'
    security_groups = ['webserver_security_group']
    virtual_ip_node_id = 'virtual_ip'
    server_node_id = 'vm'
    security_group_node_id = 'security_group'

    repo_dir = None

    def setUp(self):
        super(HelloWorldBashTest, self).setUp()
        from cosmo_tester.framework.git_helper import clone
        self.repo_dir = clone(self.CLOUDIFY_EXAMPLES_URL, self.workdir)

    def test_hello_world_bash(self):

        # Add agents security group from the cloudify-config file
        # used to bootstrap
        self.security_groups.append(self.env.agents_security_group)

        self.blueprint_path = self.repo_dir / 'hello-world'
        self.blueprint_yaml = self.blueprint_path / 'blueprint.yaml'

        blueprint = get_yaml_as_dict(self.blueprint_yaml)

        self.modify_yaml(self.blueprint_yaml)

        # Upload --> Create Deployment --> Execute Install
        before, after = self.upload_deploy_and_execute_install()

        manager_state_delta = self.get_manager_state_delta(before, after)
        nodes_state = manager_state_delta['node_state'].values()[0]

        server_node = None
        security_group_node = None
        floatingip_node = None
        for key, value in nodes_state.items():
            if key.startswith(self.virtual_ip_node_id):
                floatingip_node = value
            if key.startswith(self.security_group_node_id):
                security_group_node = value
            if key.startswith(self.server_node_id):
                server_node = value

        webserver_port = blueprint['blueprint']['nodes'][3]['properties'][
            'port']
        web_server_page_response = \
            requests.get('http://{0}:{1}'.format(
                floatingip_node['runtimeInfo']['floating_ip_address'],
                webserver_port))

        self.assertEqual(200, web_server_page_response.status_code)

        nova, neutron = openstack_clients(self.env.cloudify_config)

        self.logger.info("Retrieving agent server : {0}"
                         .format(nova.servers.get(server_node['runtimeInfo'][
                             'openstack_server_id'])))
        self.logger.info("Retrieving agent floating ip : {0}"
                         .format(neutron.show_floatingip(floatingip_node[
                             'runtimeInfo']['external_id'])))
        self.logger.info("Retrieving agent security group : {0}"
                         .format(neutron.show_security_group(
                             security_group_node['runtimeInfo'][
                                 'external_id'])))

        self.execute_uninstall()

        # No components should exist after uninstall

        try:
            server = nova.servers.get(server_node['runtimeInfo'][
                'openstack_server_id'])
            self.fail("Expected agent machine to be terminated. but found : "
                      "{0}".format(server))
        except NotFound as e:
            self.logger.info(e)
            pass

        try:
            floatingip = neutron.show_floatingip(floatingip_node[
                'runtimeInfo']['external_id'])
            self.fail("Expected agent floating ip to be terminated. "
                      "but found : {0}".format(floatingip))
        except NeutronException as e:
            self.logger.info(e)
            pass

        try:
            security_group = neutron.show_security_group(security_group_node[
                'runtimeInfo']['external_id'])
            self.fail("Expected webserver security group ip to be terminated. "
                      "but found : {0}".format(security_group))
        except NeutronException as e:
            self.logger.info(e)
            pass

    def modify_yaml(self, yaml_file):
        with YamlPatcher(yaml_file) as patch:
            vm_properties_path = 'blueprint.nodes[2].properties'
            patch.set_value('{0}.management_network_name'.format(
                vm_properties_path),
                self.env.management_network_name)
            patch.set_value('{0}.worker_config.key'.format(vm_properties_path),
                            self.env.agent_key_path)
            patch.merge_obj('{0}.server'.format(vm_properties_path), {
                'name': self.host_name,
                'image_name': self.env.ubuntu_image_name,
                'flavor_name': self.env.flavor_name,
                'key_name': self.env.agent_keypair_name,
                'security_groups': self.security_groups,
            })
            floating_ip_path = 'blueprint.nodes[0]'
            patch.merge_obj('{0}'.format(floating_ip_path), {
                'properties':                             {
                    'floatingip': {
                        'floating_network_name': self.env.external_network_name
                    }
                }
            })
