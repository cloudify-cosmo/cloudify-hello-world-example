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

import uuid
import copy
import shutil

import requests
import yaml
from path import path
from cosmo_manager_rest_client.cosmo_manager_rest_client import (
    CosmoManagerRestClient)

from cosmo_tester.framework import cfy_helper, testenv, util
from cosmo_tester.framework.util import get_blueprint_path


class HelloWorldTest(testenv.TestCase):

    uuid = uuid.uuid4()

    management_ip = '192.168.15.15'
    flavor_name = 'm1.small'
    key_path = '~/.ssh/dank-cloudify-agents-kp-pclab-devstack.pem'
    host_name = 'danktestvm'
    image_name = 'Ubuntu 12.04 64bit'
    key_name = 'dank-cloudify-agents-kp'
    management_network_name = 'dank-cloudify-admin-network'
    security_groups = ['dank-cloudify-sg-agents']
    floating_network_name = 'public'

    def test_hello_world(self):
        with util.TemporaryDirectory() as tmpdir:
            self.cfy = cfy_helper.CfyHelper(cfy_workdir=tmpdir,
                                            management_ip=self.management_ip)
            self.rest = CosmoManagerRestClient(self.management_ip)

            blueprint_path = path(tmpdir) / 'python-webserver'
            self.copy_python_webserver_blueprint(str(blueprint_path))
            self.blueprint_yaml = blueprint_path / 'blueprint.yaml'
            self.hello_world_yaml = blueprint_path / 'hello_world.yaml'
            self.modify_hello_world()

            before, after = self.upload_deploy_and_execute_install()

            self.post_install_assertions(before, after)

            self.execute_uninstall()

            self.post_uninstall_assertions()

    def copy_python_webserver_blueprint(self, target):
        shutil.copytree(get_blueprint_path('python-webserver'), target)

    def modify_hello_world(self):
        hello_yaml = yaml.load(self.hello_world_yaml.text())

        # make modifications
        vm_props = hello_yaml['type_implementations']\
            ['vm_openstack_host_impl']['properties']
        vm_props['management_network_name'] = \
            self.management_network_name
        vm_props['worker_config']['key'] = self.key_path
        vm_props['server'] = {
            'name': self.host_name,
            'image_name': self.image_name,
            'flavor_name': self.flavor_name,
            'key_name': self.key_name,
            'security_groups': self.security_groups,
        }

        ip_props = hello_yaml['type_implementations']\
            ['virtual_ip_impl']['properties']
        ip_props['floatingip'] = {
            'floating_network_name': self.floating_network_name
        }

        self.hello_world_yaml.write_text(yaml.dump(hello_yaml))

    def upload_deploy_and_execute_install(self):
        before_state = self.get_manager_state()
        self.cfy.upload_deploy_and_execute_install(
            str(self.blueprint_yaml),
            blueprint_id=self.uuid,
            deployment_id=self.uuid,
        )
        after_state = self.get_manager_state()
        return before_state, after_state

    def execute_uninstall(self):
        self.cfy.execute_uninstall(deployment_id=self.uuid)

    def get_manager_state(self):
        self.logger.info('Fetching manager current state')
        blueprints = {}
        for blueprint in self.rest.list_blueprints():
            blueprints[blueprint.id] = blueprint
        deployments = {}
        for deployment in self.rest.list_deployments():
            deployments[deployment.id] = deployment
        nodes = {}
        for deployment_id in deployments.keys():
            for node in self.rest.list_deployment_nodes(deployment_id).nodes:
                nodes[node.id] = node
        workflows = {}
        deployment_nodes = {}
        node_state = {}
        for deployment_id in deployments.keys():
            workflows[deployment_id] = self.rest.list_workflows(deployment_id)
            deployment_nodes[deployment_id] = self.rest.list_deployment_nodes(
                deployment_id,
                get_state=True)
            node_state[deployment_id] = {}
            for node in deployment_nodes[deployment_id].nodes:
                node_state[deployment_id][node.id] = self.rest.get_node_state(
                    node.id,
                    get_state=True,
                    get_runtime_properties=True)

        return {
            'blueprints': blueprints,
            'deployments': deployments,
            'workflows': workflows,
            'nodes': nodes,
            'node_state': node_state,
            'deployment_nodes': deployment_nodes
        }

    def get_manager_state_delta(self, before, after):
        after = copy.deepcopy(after)
        for blueprint_id in before['blueprints'].keys():
            del after['blueprints'][blueprint_id]
        for deployment_id in before['deployments'].keys():
            del after['deployments'][deployment_id]
            del after['workflows'][deployment_id]
            del after['deployment_nodes'][deployment_id]
            del after['node_state'][deployment_id]
        for node_id in before['nodes'].keys():
            del after['nodes'][node_id]
        return after

    def post_install_assertions(self, before_state, after_state):
        delta = self.get_manager_state_delta(before_state, after_state)

        self.logger.info('Current manager state: {0}'.format(delta))

        self.assertEqual(len(delta['blueprints']), 1,
                         'Expected 1 blueprint: {0}'.format(delta))

        blueprint_from_list = delta['blueprints'].values()[0]
        blueprint_by_id = self.rest._blueprints_api\
            .getById(blueprint_from_list.id)
        # field is expected not to return from getById call,
        # so before comparing need to disable this field
        blueprint_from_list.source = 'None'
        self.assertEqual(yaml.dump(blueprint_from_list),
                         yaml.dump(blueprint_by_id))

        self.assertEqual(len(delta['deployments']), 1,
                         'Expected 1 deployment: {0}'.format(delta))

        deployment_from_list = delta['deployments'].values()[0]
        deployment_by_id = self.rest._deployments_api\
            .getById(deployment_from_list.id)
        # plan is good enough because it contains generated ids
        self.assertEqual(deployment_from_list.plan,
                         deployment_by_id.plan)

        executions = self.rest._deployments_api\
            .listExecutions(deployment_by_id.id)
        self.assertEqual(len(executions), 1,
                         'Expected 1 execution: {0}'.format(executions))

        execution_from_list = executions[0]
        execution_by_id = self.rest._executions_api\
            .getById(execution_from_list.id)
        self.assertEqual(execution_from_list.id, execution_by_id.id)
        self.assertEqual(execution_from_list.workflowId,
                         execution_by_id.workflowId)
        self.assertEqual(execution_from_list.blueprintId,
                         execution_by_id.blueprintId)

        self.assertEqual(len(delta['deployment_nodes']), 1,
                         'Expected 1 deployment_nodes: {0}'.format(delta))

        self.assertEqual(len(delta['node_state']), 1,
                         'Expected 1 node_state: {0}'.format(delta))

        self.assertEqual(len(delta['nodes']), 2,
                         'Expected 2 nodes: {0}'.format(delta))

        self.assertEqual(len(delta['workflows']), 1,
                         'Expected 1 workflows: {0}'.format(delta))

        nodes_state = delta['node_state'].values()[0]
        self.assertEqual(len(nodes_state), 2,
                         'Expected 2 node_state: {0}'.format(nodes_state))

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
                private_ip = value['runtimeInfo']['ip']
                networks = value['runtimeInfo']['networks']
                ips = self.flatten_ips(networks)
                self.logger.info('host ips are: {0}'.format(ips))
                public_ip = filter(lambda ip: ip != private_ip, ips)[0]
                self.assertEqual(value['state'], 'started',
                                 'vm node should be started: {0}'
                                 .format(nodes_state))
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

    def flatten_ips(self, networks):
        flattened_ips = []
        for k, v in networks.iteritems():
            if not isinstance(v, list):
                flattened_ips.append(v)
            else:
                for ip in v:
                    flattened_ips.append(ip)
        return flattened_ips

    def post_uninstall_assertions(self):
        pass
