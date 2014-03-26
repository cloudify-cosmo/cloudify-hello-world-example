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


__author__ = 'dan'


import shutil

from cosmo_tester.framework.testenv import TestCase
from cosmo_tester.framework.util import get_blueprint_path, YamlPatcher
from cosmo_tester.framework.openstack_api import openstack_clients


class NeutronGaloreTest(TestCase):

    flavor_name = 'm1.small'
    host_name = 'novaservertest'
    image_name = 'Ubuntu 12.04 64bit'
    security_groups = ['neutron_test_security_group_dst']

    def test_neutron_galore(self):
        self.security_groups.append(self.env.agents_security_group)

        blueprint_path = self.copy_blueprint('neutron-galore')
        self.blueprint_yaml = blueprint_path / 'blueprint.yaml'
        self.modify_blueprint()

        before, after = self.upload_deploy_and_execute_install()

        self.post_install_assertions(before, after)

        self.execute_uninstall()

        self.post_uninstall_assertions()

    def copy_python_webserver_blueprint(self, target):
        shutil.copytree(get_blueprint_path('neutron-galore'), target)

    def modify_blueprint(self):
        with YamlPatcher(self.blueprint_yaml) as patch:
            vm_path = 'blueprint.nodes[0].properties'
            patch.set_value('{0}.management_network_name'.format(vm_path),
                            self.env.management_network_name)
            patch.set_value('{0}.worker_config.key'.format(vm_path),
                            self.env.agent_key_path)
            patch.merge_obj('{0}.server'.format(vm_path), {
                'name': self.host_name,
                'image_name': self.image_name,
                'flavor_name': self.flavor_name,
                'key_name': self.env.agent_keypair_name,
                'security_groups': self.security_groups,
            })

            router_path = 'blueprint.nodes[3].properties.router.'\
                          'external_gateway_info.network_name'
            patch.set_value(router_path, self.env.external_network_name)

            ip_path = 'blueprint.nodes[7].properties.floatingip.'\
                      'floating_network_name'
            patch.set_value(ip_path, self.env.external_network_name)

    def post_install_assertions(self, before_state, after_state):
        delta = self.get_manager_state_delta(before_state, after_state)
        node_states = self.get_node_states(delta['node_state'])
        openstack = self.get_openstack_components(node_states)


        print
        print

    def post_uninstall_assertions(self):
        pass

    def get_node_states(self, node_states):
        return {
            'server': self._node_state('nova_server', node_states),
            'network': self._node_state('neutron_network', node_states),
            'subnet': self._node_state('neutron_subnet', node_states),
            'router': self._node_state('neutron_router', node_states),
            'port': self._node_state('neutron_port', node_states),
            'sg_src': self._node_state('security_group_src', node_states),
            'sg_dst': self._node_state('security_group_dst', node_states),
            'floatingip': self._node_state('floatingip', node_states)
        }

    def get_openstack_components(self, states):
        nova, neutron = openstack_clients(self.env.cloudify_config)
        sid = 'openstack_server_id'
        eid = 'external_id'
        return {
            'server': nova.servers.get(states['server'][sid]),
            'network': neutron.show_network(states['network'][eid]),
            'subnet': neutron.show_subnet(states['subnet'][eid]),
            'router': neutron.show_router(states['router'][eid]),
            'port': neutron.show_port(states['port'][eid]),
            'sg_src': neutron.show_security_group(states['sg_src'][eid]),
            'sg_dst': neutron.show_security_group(states['sg_dst'][eid]),
            'floatingip': neutron.show_floatingip(states['floatingip'][eid])
        }

    def _node_state(self, starts_with, node_states):
        node_states = node_states.values()[0].values()
        state = [state for state in node_states
                 if state['id'].startswith(starts_with)][0]
        self.assertEqual(state['state'], 'started')
        return state['runtimeInfo']
