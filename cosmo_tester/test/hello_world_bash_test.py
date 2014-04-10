from cosmo_tester.framework.util import YamlPatcher

__author__ = 'elip'

from shutil import rmtree
from cosmo_tester.framework.testenv import TestCase
from cosmo_tester.framework.util import get_yaml_as_dict

import requests


class HelloWorldBashTest(TestCase):

    CLOUDIFY_EXAMPLES_URL = "https://github.com/cloudify-cosmo/cloudify-examples.git"

    host_name = 'bash-web-server'
    flavor = 102
    image = '8c096c29-a666-4b82-99c4-c77dc70cfb40'
    security_groups = ['webserver_security_group']
    virtual_ip_node_id = 'test_hello_world_bash_virtual_ip'

    repo_dir = None

    @classmethod
    def setUpClass(cls):

        from cosmo_tester.framework.git_helper import clone
        cls.repo_dir = clone(cls.CLOUDIFY_EXAMPLES_URL)

    def test_hello_world_bash(self):

        # Add agents security group from the cloudify-config file used to bootstrap
        self.security_groups.append(self.env.agents_security_group)

        self.blueprint_path = self.repo_dir / 'hello-world'
        self.blueprint_yaml = self.blueprint_path / 'blueprint.yaml'

        blueprint = get_yaml_as_dict(self.blueprint_yaml)

        self.modify_yaml(self.blueprint_yaml)

        # Upload --> Create Deployment --> Execute Install
        before, after = self.upload_deploy_and_execute_install()

        manager_state = self.get_manager_state_delta(before, after)
        nodes_state_per_deployment = manager_state['node_state'].values()

        public_ip = None
        for nodes_state in nodes_state_per_deployment:
            for key, value in nodes_state.items():
                if key.startswith(self.virtual_ip_node_id):
                    public_ip = value['runtimeInfo']['floating_ip_address']
                    break
            if public_ip:
                break

        webserver_port = blueprint['blueprint']['nodes'][3]['properties']['port']
        web_server_page_response = requests.get('http://{0}:{1}'
                                                .format(public_ip, webserver_port))

        self.assertEqual(200, web_server_page_response.status_code)

        self.execute_uninstall()

    def modify_yaml(self, yaml_file):
        with YamlPatcher(yaml_file) as patch:
            vm_properties_path = 'blueprint.nodes[2].properties'
            patch.set_value('{0}.management_network_name'.format(vm_properties_path),
                            self.env.management_network_name)
            patch.set_value('{0}.worker_config.key'.format(vm_properties_path),
                            self.env.agent_key_path)
            patch.merge_obj('{0}.server'.format(vm_properties_path), {
                'name': self.host_name,
                'image': self.image,
                'flavor': self.flavor,
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
            virtual_ip_path = 'blueprint.nodes[0]'
            patch.set_value('{0}.name'.format(virtual_ip_path),
                            self.virtual_ip_node_id)
            vm_relationship_path = 'blueprint.nodes[2].relationships[0]'
            patch.set_value('{0}.target'.format(vm_relationship_path),
                            self.virtual_ip_node_id)

    def upload_deploy_and_execute_install(self, blueprint_id=None,
                                          deployment_id=None):
        before_state = self.get_manager_state()
        self.cfy.upload_deploy_and_execute_install(
            str(self.blueprint_yaml),
            blueprint_id=blueprint_id or self.test_id,
            deployment_id=deployment_id or self.test_id,
        )
        after_state = self.get_manager_state()
        return before_state, after_state

    @classmethod
    def tearDownClass(cls):
        if not cls.repo_dir:
            rmtree(cls.repo_dir)
