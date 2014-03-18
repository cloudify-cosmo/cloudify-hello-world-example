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

import requests
import yaml

from cosmo_tester.framework.testenv import TestCase
from cosmo_tester.framework.util import YamlPatcher


class PythonWebServerTest(TestCase):

    flavor_name = 'm1.small'
    key_path = '~/.ssh/dank-cloudify-agents-kp-pclab-devstack.pem'
    host_name = 'danktestvm'
    image_name = 'Ubuntu 12.04 64bit'
    key_name = 'dank-cloudify-agents-kp'
    security_groups = ['dank-cloudify-sg-agents', 'webserver_security_group']
    floating_network_name = 'public'

    def test_hello_world(self):
        blueprint_path = self.copy_blueprint('python-webserver')
        self.blueprint_yaml = blueprint_path / 'blueprint.yaml'
        self.webserver_yaml = blueprint_path / 'python_webserver.yaml'
        self.modify_hello_world()

        before, after = self.upload_deploy_and_execute_install()

        self.post_install_assertions(before, after)

        self.execute_uninstall()

        self.post_uninstall_assertions()

    def modify_hello_world(self):
        with YamlPatcher(self.webserver_yaml) as patch:
            vm_path = 'type_implementations.vm_openstack_host_impl.properties'
            patch.set_value('{0}.management_network_name'.format(vm_path),
                            self.management_network_name)
            patch.set_value('{0}.worker_config.key'.format(vm_path),
                            self.key_path)
            patch.merge_obj('{0}.server'.format(vm_path), {
                'name': self.host_name,
                'image_name': self.image_name,
                'flavor_name': self.flavor_name,
                'key_name': self.key_name,
                'security_groups': self.security_groups,
            })
            ip_path = 'type_implementations.virtual_ip_impl.properties'
            patch.set_value(
                '{0}.floatingip.floating_network_name'.format(ip_path),
                self.floating_network_name)

    def post_install_assertions(self, before_state, after_state):
        delta = self.get_manager_state_delta(before_state, after_state)

        self.logger.info('Current manager state: {0}'.format(delta))

        self.assertEqual(len(delta['blueprints']), 1,
                         'blueprint: {0}'.format(delta))

        blueprint_from_list = delta['blueprints'].values()[0]
        blueprint_by_id = self.rest._blueprints_api\
            .getById(blueprint_from_list.id)
        # field is expected not to return from getById call,
        # so before comparing need to disable this field
        blueprint_from_list.source = 'None'
        self.assertEqual(yaml.dump(blueprint_from_list),
                         yaml.dump(blueprint_by_id))

        self.assertEqual(len(delta['deployments']), 1,
                         'deployment: {0}'.format(delta))

        deployment_from_list = delta['deployments'].values()[0]
        deployment_by_id = self.rest._deployments_api\
            .getById(deployment_from_list.id)
        # plan is good enough because it contains generated ids
        self.assertEqual(deployment_from_list.plan,
                         deployment_by_id.plan)

        executions = self.rest._deployments_api\
            .listExecutions(deployment_by_id.id)
        self.assertEqual(len(executions), 1,
                         'execution: {0}'.format(executions))

        execution_from_list = executions[0]
        execution_by_id = self.rest._executions_api\
            .getById(execution_from_list.id)
        self.assertEqual(execution_from_list.id, execution_by_id.id)
        self.assertEqual(execution_from_list.workflowId,
                         execution_by_id.workflowId)
        self.assertEqual(execution_from_list.blueprintId,
                         execution_by_id.blueprintId)

        self.assertEqual(len(delta['deployment_nodes']), 1,
                         'deployment_nodes: {0}'.format(delta))

        self.assertEqual(len(delta['node_state']), 1,
                         'node_state: {0}'.format(delta))

        self.assertEqual(len(delta['nodes']), 4,
                         'nodes: {0}'.format(delta))

        self.assertEqual(len(delta['workflows']), 1,
                         'workflows: {0}'.format(delta))

        nodes_state = delta['node_state'].values()[0]
        self.assertEqual(len(nodes_state), 4,
                         'nodes_state: {0}'.format(nodes_state))

        public_ip = None
        webserver_node_id = None
        for key, value in nodes_state.items():
            if key.startswith('vm'):
                self.assertTrue('ip' in value['runtimeInfo'],
                                'Missing ip in runtimeInfo: {0}'
                                .format(nodes_state))
                self.assertTrue('networks' in value['runtimeInfo'],
                                'Missing networks in runtimeInfo: {0}'
                                .format(nodes_state))
                self.assertEqual(value['state'], 'started',
                                 'vm node should be started: {0}'
                                 .format(nodes_state))
            elif key.startswith('virtual_ip'):
                public_ip = value['runtimeInfo']['floating_ip_address']
            else:
                webserver_node_id = key

        events, total_events = self.rest\
            .get_execution_events(execution_by_id.id)
        self.assertGreater(len(events), 0,
                           'Expected at least 1 event for execution id: {0}'
                           .format(execution_by_id.id))

        web_server_page_response = requests.get('http://{0}:8080'
                                                .format(public_ip))
        self.assertTrue(webserver_node_id in web_server_page_response.text,
                        'Expected to find {0} in web server response: {1}'
                        .format(webserver_node_id, web_server_page_response))

    def post_uninstall_assertions(self):
        #TODO
        pass
