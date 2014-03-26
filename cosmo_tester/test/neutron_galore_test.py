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
    image_name = 'Ubuntu-NP'
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

        self.assertEqual(openstack['server']['addresses']
                                  ['dank-cloudify-admin-network']
                                  [0]['OS-EXT-IPS:type'], 'fixed')
        self.assertEqual(openstack['server']['addresses']
                         ['dank-cloudify-admin-network']
                         [1]['OS-EXT-IPS:type'], 'fixed')
        floatingip_address = openstack['server']['addresses'][
            'dank-cloudify-admin-network'][0]['addr']
        self.assertEqual(openstack['server']['addresses']
                         ['neutron_network_test']
                         [0]['OS-EXT-IPS:type'], 'fixed')
        self.assertEqual(openstack['server']['addresses']
                         ['neutron_network_test']
                         [0]['version'], 4)
        port_assigned_addr = openstack['server']['addresses'][
            'neutron_network_test'][0]['addr']
        self.assertTrue(port_assigned_addr.startswith('10.10.10.'))
        self.assert_obj_list_contains_subset(
            openstack['server']['security_groups'],
            {'name': 'neutron_test_security_group_dst'})
        self.assert_obj_list_contains_subset(
            openstack['server']['security_groups'],
            {'name': 'dank-cloudify-sg-agents'})
        self.assert_obj_list_contains_subset(
            openstack['server']['security_groups'],
            {'name': 'neutron_test_security_group_src'})
        self.assertEqual(openstack['server']['name'], 'novaservertest')
        self.assertEqual(openstack['port']['name'], 'neutron_test_port')
        port_security_group_id = openstack['port']['security_groups'][0]
        port_fixed_ip = openstack['port']['fixed_ips'][0]['ip_address']
        self.assertEqual(port_fixed_ip, port_assigned_addr)
        port_network_id = openstack['port']['network_id']
        port_subnet_id = openstack['port']['fixed_ips'][0]['subnet_id']
        self.assertEqual(openstack['floatingip']['floating_ip_address'],
                         floatingip_address)
        self.assertEqual(openstack['router']['name'], 'neutron_router_test')
        router_network_id = openstack['router']['external_gateway_info'][
            'network_id']
        self.assertEqual(openstack['sg_src']['name'],
                         'neutron_test_security_group_src')
        sg_src_id = openstack['sg_src']['id']
        self.assertEqual(port_security_group_id, sg_src_id)
        self.assertEqual(openstack['network']['name'], 'neutron_network_test')
        network_subnet_id = openstack['network']['subnets'][0]
        self.assertEqual(router_network_id, openstack['network']['id'])
        self.assertEqual(port_network_id, openstack['network']['id'])
        self.assertEqual(openstack['subnet']['name'], 'neutron_subnet_test')
        self.assertEqual(openstack['subnet']['cidr'], '10.10.10.0/24')
        self.assertEqual(network_subnet_id, openstack['subnet']['id'])
        self.assertEqual(port_subnet_id, openstack['subnet']['id'])
        self.assertEqual(openstack['sg_dst']['name'],
                         'neutron_test_security_group_dst')
        self.assertEqual(4, len(openstack['sg_dst']['security_group_rules']))
        self.assert_obj_list_contains_subset(
            openstack['sg_dst']['security_group_rules'],
            {'remote_ip_prefix': '1.2.3.0/24',
             'port_range_min': 80,
             'port_range_max': 80,
             'direction': 'ingress'})
        self.assert_obj_list_contains_subset(
            openstack['sg_dst']['security_group_rules'],
            {'remote_ip_prefix': '2.3.4.0/24',
             'port_range_min': 65500,
             'port_range_max': 65510,
             'direction': 'ingress'})
        self.assert_obj_list_contains_subset(
            openstack['sg_dst']['security_group_rules'],
            {'remote_group_id': sg_src_id,
             'port_range_min': 65521,
             'port_range_max': 65521,
             'direction': 'ingress'})
        self.assert_obj_list_contains_subset(
            openstack['sg_dst']['security_group_rules'],
            {'remote_ip_prefix': '3.4.5.0/24',
             'port_range_min': 443,
             'port_range_max': 443,
             'direction': 'egress'})
        self.assertEqual(node_states['floatingip']['floating_ip_address'],
                         floatingip_address)
        self.assertEqual(openstack['server']['addresses']
                                  ['dank-cloudify-admin-network'][0]['addr'],
                         node_states['server']['networks']
                         ['dank-cloudify-admin-network'][0])
        self.assertEqual(openstack['server']['addresses']
                         ['neutron_network_test'][0]['addr'],
                         node_states['server']['networks']
                         ['neutron_network_test'][0])
        self.assertEqual(node_states['server']['ip'],
                         openstack['server']['addresses']
                         ['dank-cloudify-admin-network'][0]['addr'])

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
        sg = 'security_group'
        i = 'floatingip'
        return {
            'server': nova.servers.get(states['server'][sid]).to_dict(),
            'network': neutron.show_network(states['network'][eid])['network'],
            'subnet': neutron.show_subnet(states['subnet'][eid])['subnet'],
            'router': neutron.show_router(states['router'][eid])['router'],
            'port': neutron.show_port(states['port'][eid])['port'],
            'sg_src': neutron.show_security_group(states['sg_src'][eid])[sg],
            'sg_dst': neutron.show_security_group(states['sg_dst'][eid])[sg],
            'floatingip': neutron.show_floatingip(states['floatingip'][eid])[i]
        }

    def _node_state(self, starts_with, node_states):
        node_states = node_states.values()[0].values()
        state = [state for state in node_states
                 if state['id'].startswith(starts_with)][0]
        self.assertEqual(state['state'], 'started')
        return state['runtimeInfo']

    def assert_obj_list_contains_subset(self, obj_list, subset):
        for obj in obj_list:
            if set(subset.keys()) <= set(obj.keys()) and \
               all([obj[key] == value for key, value in subset.items()]):
                    return
        self.fail('Could not find {0} in {1}'.format(subset, obj_list))
