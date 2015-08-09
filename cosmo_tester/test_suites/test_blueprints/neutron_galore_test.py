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

import os
import time

import fabric.api
import fabric.contrib.files

from cosmo_tester.framework.testenv import TestCase
from cosmo_tester.framework.util import (
    YamlPatcher,
    get_actual_keypath
)

PRIVATE_KEY_PATH = '/tmp/home/neutron-test.pem'


class NeutronGaloreTest(TestCase):

    def test_neutron_galore(self):

        blueprint_path = self.copy_blueprint('neutron-galore')
        self.blueprint_yaml = blueprint_path / 'blueprint.yaml'

        inputs = {
            'server_name': 'novaservertest',
            'image': self.env.ubuntu_image_name,
            'flavor': self.env.flavor_name,
            'private_key_path': PRIVATE_KEY_PATH,
        }

        before, after = self.upload_deploy_and_execute_install(inputs=inputs)

        node_states = self.get_delta_node_states(before, after)

        self.repetitive(self.post_install_assertions,
                        timeout=300,
                        args=[node_states])

        self._test_use_external_resource(inputs=inputs)

        self.execute_uninstall()

        self.post_uninstall_assertions()

    def post_install_assertions(self, node_states):

        def p(name):
            return '{}{}'.format(self.env.resources_prefix, name)

        management_network_name = self.env.management_network_name
        agents_security_group = self.env.agents_security_group

        time.sleep(5)  # actually waiting for Openstack to update...
        openstack = self.get_openstack_components(node_states)

        self.assertTrue(self._check_if_private_key_is_on_manager())

        port_assigned_addr = openstack['server']['addresses'][
            p('neutron_network_test')][0]['addr']
        # the port will get connected to the dst security group automatically
        #  when the server connects to the security group
        port_security_groups = openstack['port']['security_groups']
        port_fixed_ip = openstack['port']['fixed_ips'][0]['ip_address']
        port_network_id = openstack['port']['network_id']
        port_subnet_id = openstack['port']['fixed_ips'][0]['subnet_id']
        router_network_id = openstack['router']['external_gateway_info'][
            'network_id']
        sg_src_id = openstack['sg_src']['id']
        sg_dst_id = openstack['sg_dst']['id']
        network_subnet_id = openstack['network']['subnets'][0]

        self.assertEqual(openstack['server']['addresses']
                         [management_network_name][0]
                         ['OS-EXT-IPS:type'], 'fixed')
        self.assertEqual(openstack['server']['addresses']
                         [p('neutron_network_test')][0]
                         ['OS-EXT-IPS:type'], 'fixed')
        self.assertEqual(openstack['server']['addresses']
                         [p('neutron_network_test')][0]
                         ['version'], 4)
        self.assertTrue(port_assigned_addr.startswith('10.10.10.'))
        self.assert_obj_list_contains_subset(
            openstack['server']['security_groups'],
            {'name': p('neutron_test_security_group_dst')})
        self.assert_obj_list_contains_subset(
            openstack['server']['security_groups'],
            {'name': p('neutron_test_security_group_src')})
        self.assert_obj_list_contains_subset(
            openstack['server']['security_groups'],
            {'name': agents_security_group})
        self.assert_obj_list_contains_subset(
            openstack['server2']['security_groups'],
            {'name': p('neutron_test_security_group_3')})
        self.assert_obj_list_contains_subset(
            openstack['server2']['security_groups'],
            {'name': p('neutron_test_security_group_4')})
        self.assert_obj_list_contains_subset(
            openstack['server2']['security_groups'],
            {'name': agents_security_group})
        self.assertEqual(openstack['server']['name'], p('novaservertest'))
        self.assertEqual(openstack['port']['name'], p('neutron_test_port'))
        self.assertEqual(port_fixed_ip, port_assigned_addr)
        self.assertEqual(openstack['keypair']['name'],
                         openstack['server']['key_name'])
        self.assertEqual(openstack['floatingip']['floating_network_id'],
                         router_network_id)
        self.assertEqual(openstack['router']['name'], p('neutron_router_test'))
        self.assertEqual(openstack['sg_src']['name'],
                         p('neutron_test_security_group_src'))
        self.assertIn(sg_dst_id, port_security_groups)
        self.assertIn(sg_src_id, port_security_groups)
        self.assertEqual(openstack['network']['name'],
                         p('neutron_network_test'))
        self.assertEqual(port_network_id, openstack['network']['id'])
        self.assertEqual(openstack['subnet']['name'],
                         p('neutron_subnet_test'))
        self.assertEqual(openstack['subnet']['cidr'], '10.10.10.0/24')
        self.assertEqual(network_subnet_id, openstack['subnet']['id'])
        self.assertEqual(port_subnet_id, openstack['subnet']['id'])
        self.assertEqual(openstack['sg_dst']['name'],
                         p('neutron_test_security_group_dst'))
        self.assertEqual(3, len(openstack['sg_dst']['security_group_rules']))
        self.assertEqual(2, len(openstack['sg_3']['security_group_rules']))
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
            openstack['sg_3']['security_group_rules'],
            {'remote_ip_prefix': '0.0.0.0/0',
             'port_range_min': 0,
             'port_range_max': 0,
             'protocol': 'icmp',
             'direction': 'ingress'})
        self.assert_obj_list_contains_subset(
            openstack['sg_3']['security_group_rules'],
            {'remote_ip_prefix': '0.0.0.0/0',
             'port_range_min': 0,
             'port_range_max': 0,
             'protocol': 'icmp',
             'direction': 'egress'})
        self.assertEqual(node_states['floatingip']['floating_ip_address'],
                         openstack['floatingip']['floating_ip_address'])
        self.assertEqual(node_states['floatingip2']['floating_ip_address'],
                         openstack['floatingip2']['floating_ip_address'])
        self.assertEqual(openstack['server']['addresses']
                         [management_network_name][0]['addr'],
                         node_states['server']['networks']
                         [management_network_name][0])
        self.assertEqual(openstack['server2']['addresses']
                         [management_network_name][0]['addr'],
                         node_states['server2']['networks']
                         [management_network_name][0])
        self.assertEqual(openstack['server']['addresses']
                         [p('neutron_network_test')][0]['addr'],
                         node_states['server']['networks']
                         [p('neutron_network_test')][0])
        self.assertEqual(node_states['server']['ip'],
                         openstack['server']['addresses']
                         [management_network_name][0]['addr'])
        self.assertEquals(node_states['port2']['fixed_ip_address'],
                          openstack['port2']['fixed_ips'][0]['ip_address'])
        self.assertEquals('10.10.10.123',
                          openstack['port2']['fixed_ips'][0]['ip_address'])
        self.assertEquals(openstack['port2']['id'],
                          openstack['floatingip3']['port_id'])
        self.assert_router_connected_to_subnet(openstack['router']['id'],
                                               openstack['router_ports'],
                                               openstack['subnet']['id'])
        # check the ICMP security group rule for allowing ping is ok
        self._assert_ping_to_server(
            ip=node_states['floatingip2']['floating_ip_address'])

    def post_uninstall_assertions(self):
        leftovers = self._test_cleanup_context.get_resources_to_teardown(self.env)
        self.assertTrue(all([len(g) == 0 for g in leftovers.values()]))
        self.assertFalse(self._check_if_private_key_is_on_manager())

    def _test_use_external_resource(self, inputs):
        before_openstack_infra_state = self.env.handler.openstack_infra_state()

        self._modify_blueprint_use_external_resource()

        bp_and_dep_name = self.test_id + '-use-external-resource'
        _, after = self.upload_deploy_and_execute_install(
            blueprint_id=bp_and_dep_name,
            deployment_id=bp_and_dep_name,
            inputs=inputs)

        self._post_use_external_resource_install_assertions(
            bp_and_dep_name, before_openstack_infra_state, after['node_state'])

        self.execute_uninstall(bp_and_dep_name)

        self._post_use_external_resource_uninstall_assertions(bp_and_dep_name)

    def _assert_ping_to_server(self, ip):
        for i in range(3):
            exit_code = os.system('ping -c 1 {0}'.format(ip))
            if exit_code == 0:
                return
            else:
                time.sleep(3)

        self.fail('Failed to ping server {0}; Exit code for ping command was '
                  '{1}'.format(ip, exit_code))

    def _modify_blueprint_use_external_resource(self):
        node_instances = self.client.node_instances.list(
            deployment_id=self.test_id)

        node_id_to_external_resource_id = {
            node_instance.node_id: node_instance.runtime_properties[
                'external_id'] for node_instance in node_instances
        }

        with YamlPatcher(self.blueprint_yaml) as patch:
            for node_id, resource_id in \
                    node_id_to_external_resource_id.iteritems():
                patch.merge_obj(
                    'node_templates.{0}.properties'.format(node_id),
                    {
                        'use_external_resource': True,
                        'resource_id': resource_id
                    })

    def _post_use_external_resource_install_assertions(
            self, use_external_resource_deployment_id,
            before_openstack_infra_state, after_nodes_state):

        # verify private key still exists
        self.assertTrue(self._check_if_private_key_is_on_manager())

        # verify there aren't any new resources on Openstack
        after_openstack_infra_state = self.env.handler.openstack_infra_state()
        delta = self.env.handler.openstack_infra_state_delta(
            before_openstack_infra_state, after_openstack_infra_state)
        for delta_resources_of_single_type in delta.values():
            self.assertFalse(delta_resources_of_single_type)

        # verify the runtime properties of the new deployment's nodes
        # original_deployment_node_states = self.get_node_states(
        #     after_nodes_state, self.test_id)
        # use_external_resource_deployment_node_states = self.get_node_states(
        #     after_nodes_state, use_external_resource_deployment_id)
        # self.assertDictEqual(original_deployment_node_states,
        #                      use_external_resource_deployment_node_states)

    def _post_use_external_resource_uninstall_assertions(
            self, use_external_resource_deployment_id):

        # verify private key still exists
        self.assertTrue(self._check_if_private_key_is_on_manager())

        # verify the external resources are all still up and running
        original_deployment_node_states = self.get_node_states(
            self.get_manager_state()['node_state'], self.test_id)
        self.post_install_assertions(original_deployment_node_states)

        # verify the use_external_resource deployment has no runtime
        # properties on the nodes
        node_instances = self.client.node_instances.list(
            deployment_id=use_external_resource_deployment_id)
        instances_with_runtime_props = [instance for instance in node_instances
                                        if instance.runtime_properties]
        self.assertEquals(0, len(instances_with_runtime_props))

    def get_node_states(self, node_states, deployment_id):
        return {
            'server': self._node_state('nova_server', node_states,
                                       deployment_id),
            'server2': self._node_state('nova_server2', node_states,
                                        deployment_id),
            'network': self._node_state('neutron_network', node_states,
                                        deployment_id),
            'subnet': self._node_state('neutron_subnet', node_states,
                                       deployment_id),
            'router': self._node_state('neutron_router', node_states,
                                       deployment_id),
            'port': self._node_state('neutron_port', node_states,
                                     deployment_id),
            'port2': self._node_state('neutron_port2', node_states,
                                      deployment_id),
            'sg_src': self._node_state('security_group_src', node_states,
                                       deployment_id),
            'sg_dst': self._node_state('security_group_dst', node_states,
                                       deployment_id),
            'sg_3': self._node_state('security_group_3', node_states,
                                     deployment_id),
            'sg_4': self._node_state('security_group_4', node_states,
                                     deployment_id),
            'floatingip': self._node_state('floatingip', node_states,
                                           deployment_id),
            'floatingip2': self._node_state('floatingip2', node_states,
                                            deployment_id),
            'floatingip3': self._node_state('floatingip3', node_states,
                                            deployment_id),
            'keypair': self._node_state('keypair', node_states,
                                        deployment_id)
        }

    def get_delta_node_states(self, before_state, after_state):
        delta = self.get_manager_state_delta(before_state, after_state)
        node_states = self.get_node_states(delta['node_state'], self.test_id)
        return node_states

    def get_openstack_components(self, states):
        nova, neutron, _ = self.env.handler.openstack_clients()
        eid = 'external_id'
        sg = 'security_group'
        rid = states['router'][eid]
        return {
            'server': nova.servers.get(states['server'][eid]).to_dict(),
            'server2': nova.servers.get(states['server2'][eid]).to_dict(),
            'network': neutron.show_network(states['network'][eid])['network'],
            'subnet': neutron.show_subnet(states['subnet'][eid])['subnet'],
            'router': neutron.show_router(rid)['router'],
            'port': neutron.show_port(states['port'][eid])['port'],
            'port2': neutron.show_port(states['port2'][eid])['port'],
            'sg_src': neutron.show_security_group(states['sg_src'][eid])[sg],
            'sg_dst': neutron.show_security_group(states['sg_dst'][eid])[sg],
            'sg_3': neutron.show_security_group(states['sg_3'][eid])[sg],
            'sg_4': neutron.show_security_group(states['sg_4'][eid])[sg],
            'floatingip': neutron.show_floatingip(
                states['floatingip'][eid])['floatingip'],
            'floatingip2': neutron.show_floatingip(
                states['floatingip2'][eid])['floatingip'],
            'floatingip3': neutron.show_floatingip(
                states['floatingip3'][eid])['floatingip'],
            'router_ports': neutron.list_ports(device_id=rid)['ports'],
            'keypair': nova.keypairs.get(states['keypair'][eid]).to_dict()
        }

    def _node_state(self, starts_with, node_states, deployment_id):
        node_states = node_states[deployment_id].values()
        state = [state for state in node_states
                 if state['id'].startswith('{0}_'.format(starts_with))][0]
        self.assertEqual(state['state'], 'started')
        return state['runtime_properties']

    def assert_obj_list_contains_subset(self, obj_list, subset):
        for obj in obj_list:
            if all([obj.get(key) == value for key, value in subset.items()]):
                    return
        self.fail('Could not find {0} in {1}'.format(subset, obj_list))

    def assert_router_connected_to_subnet(self, router_id,
                                          router_ports, subnet_id):
        for port in router_ports:
            for fixed_ip in port.get('fixed_ips', []):
                if fixed_ip.get('subnet_id') == subnet_id:
                    return
        self.fail('router {0} is not connected to subnet {1}'
                  .format(router_id, subnet_id))

    def _check_if_private_key_is_on_manager(self):

        if self._is_docker_manager():
            path_to_check = '/home/{0}/neutron-test.pem'\
                .format(self.env.management_user_name)
        else:
            path_to_check = PRIVATE_KEY_PATH

        manager_key_path = get_actual_keypath(
            self.env, self.env.management_key_path)

        fabric_env = fabric.api.env
        fabric_env.update({
            'timeout': 30,
            'user': self.env.management_user_name,
            'key_filename': manager_key_path,
            'host_string': self.env.management_ip
        })

        return fabric.contrib.files.exists(path_to_check)

    def _is_docker_manager(self):
        manager_key_path = get_actual_keypath(
            self.env, self.env.management_key_path)

        fabric_env = fabric.api.env
        fabric_env.update({
            'timeout': 30,
            'user': self.env.management_user_name,
            'key_filename': manager_key_path,
            'host_string': self.env.management_ip
        })
        try:
            fabric.api.sudo('which docker')
            return True
        except SystemExit:
            return False
