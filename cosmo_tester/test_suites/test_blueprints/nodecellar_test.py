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
import json
from requests.exceptions import ConnectionError
from influxdb import InfluxDBClient

from cosmo_tester.framework.testenv import TestCase
from cosmo_tester.framework.util import YamlPatcher
from cosmo_tester.framework.git_helper import clone


class NodecellarAppTest(TestCase):

    def _test_nodecellar_impl(self, blueprint_file):
        self.repo_dir = clone(self.repo_url, self.workdir)
        self.blueprint_yaml = self.repo_dir / blueprint_file

        self.modify_blueprint()

        before, after = self.upload_deploy_and_execute_install(
            inputs=self.get_inputs()
        )

        self.post_install_assertions(before, after)

        self.execute_uninstall()

        self.post_uninstall_assertions()

    def modify_blueprint(self):
        pass

    def get_inputs(self):
        raise RuntimeError('Must be implemented by Subclasses')

    def assert_nodecellar_working(self, public_ip):
        nodejs_server_page_response = requests.get('http://{0}:8080'
                                                   .format(self.public_ip))
        self.assertEqual(200, nodejs_server_page_response.status_code,
                         'Failed to get home page of nodecellar app')
        page_title = 'Node Cellar'
        self.assertTrue(page_title in nodejs_server_page_response.text,
                        'Expected to find {0} in web server response: {1}'
                        .format(page_title, nodejs_server_page_response))

        wines_page_response = requests.get('http://{0}:8080/wines'.format(
            self.public_ip))
        self.assertEqual(200, wines_page_response.status_code,
                         'Failed to get the wines page on nodecellar app ('
                         'probably means a problem with the connection to '
                         'MongoDB)')

        try:
            wines_json = json.loads(wines_page_response.text)
            if type(wines_json) != list:
                self.fail('Response from wines page is not a JSON list: {0}'
                          .format(wines_page_response.text))

            self.assertGreater(len(wines_json), 0,
                               'Expected at least 1 wine data in nodecellar '
                               'app; json returned on wines page is: {0}'
                               .format(wines_page_response.text))
        except BaseException:
            self.fail('Response from wines page is not a valid JSON: {0}'
                      .format(wines_page_response.text))

    def post_install_assertions(self, before_state, after_state):
        delta = self.get_manager_state_delta(before_state, after_state)

        self.logger.info('Current manager state: {0}'.format(delta))

        self.assertEqual(len(delta['blueprints']), 1,
                         'blueprint: {0}'.format(delta))

        self.assertEqual(len(delta['deployments']), 1,
                         'deployment: {0}'.format(delta))

        deployment_from_list = delta['deployments'].values()[0]

        deployment_by_id = self.client.deployments.get(deployment_from_list.id)
        self.deployment_id = deployment_from_list.id

        executions = self.client.executions.list(
            deployment_id=deployment_by_id.id)

        self.assertEqual(len(executions), 2,
                         'There should be 2 executions but are: {0}'.format(
                             executions))

        execution_from_list = executions[0]
        execution_by_id = self.client.executions.get(execution_from_list.id)

        self.assertEqual(execution_from_list.id, execution_by_id.id)
        self.assertEqual(execution_from_list.workflow_id,
                         execution_by_id.workflow_id)
        self.assertEqual(execution_from_list['blueprint_id'],
                         execution_by_id['blueprint_id'])

        self.assertEqual(len(delta['deployment_nodes']), 1,
                         'deployment_nodes: {0}'.format(delta))

        self.assertEqual(len(delta['node_state']), 1,
                         'node_state: {0}'.format(delta))

        self.assertEqual(len(delta['nodes']), self.expected_nodes_count,
                         'nodes: {0}'.format(delta))

        nodes_state = delta['node_state'].values()[0]
        self.assertEqual(len(nodes_state), self.expected_nodes_count,
                         'nodes_state: {0}'.format(nodes_state))
        self.assert_monitoring_data_exists()
        self.public_ip = None
        entrypoint_node_name = self.entrypoint_node_name
        entrypoint_runtime_property_name = self.entrypoint_property_name
        for key, value in nodes_state.items():
            if '_host' in key:
                expected = self.host_expected_runtime_properties
                for expected_property in expected:
                    self.assertTrue(
                        expected_property in value['runtime_properties'],
                        'Missing {0} in runtime_properties: {1}'
                        .format(expected_property, value))

                self.assertEqual(value['state'], 'started',
                                 'vm node should be started: {0}'
                                 .format(nodes_state))
            if key.startswith(entrypoint_node_name):
                self.public_ip = value['runtime_properties'][
                    entrypoint_runtime_property_name]

        self.assertIsNotNone(self.public_ip,
                             'Could not find the '
                             '"{0}" node for '
                             'retrieving the public IP'
                             .format(entrypoint_node_name))

        events, total_events = self.client.events.get(execution_by_id.id)

        self.assertGreater(len(events), 0,
                           'Expected at least 1 event for execution id: {0}'
                           .format(execution_by_id.id))

        self.assert_nodecellar_working(self.public_ip)

    def assert_monitoring_data_exists(self):
        client = InfluxDBClient(self.env.management_ip, 8086, 'root', 'root',
                                'cloudify')
        try:
            # select monitoring events for deployment from the past 5 seconds.
            # a NameError will be thrown only if NO deployment events exist
            # in the DB regardless of time-span in query.
            client.query('select * from /^{0}\./i '
                         'where time > now() - 5s'
                         .format(self.deployment_id))
        except NameError as e:
            self.fail('monitoring events list for deployment with ID {0} were'
                      ' not found on influxDB. error is: {1}'
                      .format(self.deployment_id, e))

    def post_uninstall_assertions(self):
        nodes_instances = self.client.node_instances.list(self.deployment_id)
        self.assertFalse(any(node_ins for node_ins in nodes_instances if
                             node_ins.state != 'deleted'))
        try:
            requests.get('http://{0}:8080'.format(self.public_ip))
            self.fail('Expected a no route to host error to be raised when '
                      'trying to retrieve the web page after uninstall, '
                      'but no error was raised.')
        except ConnectionError:
            pass

    @property
    def repo_url(self):
        return 'https://github.com/cloudify-cosmo/' \
               'cloudify-nodecellar-example.git'

    @property
    def expected_nodes_count(self):
        return 8

    @property
    def host_expected_runtime_properties(self):
        return ['ip', 'networks']

    @property
    def entrypoint_node_name(self):
        return 'nodecellar_floatingip'

    @property
    def entrypoint_property_name(self):
        return 'floating_ip_address'


class OpenStackNodeCellarTestBase(NodecellarAppTest):

    def _test_openstack_nodecellar(self, blueprint_file):
        self._test_nodecellar_impl(blueprint_file)

    def get_inputs(self):

        return {
            'image': self.env.ubuntu_image_id,
            'flavor': self.env.small_flavor_id,
            'agent_user': 'ubuntu'
        }


class OpenStackNodeCellarTest(OpenStackNodeCellarTestBase):

    def test_openstack_nodecellar(self):
        self._test_openstack_nodecellar('openstack-blueprint.yaml')


class OldVersionOpenStackNodeCellarTest(OpenStackNodeCellarTestBase):

    # Nodecellar test using an older Openstack plugin version

    def test_old_version_openstack_nodecellar(self):
        self._test_openstack_nodecellar('openstack-blueprint.yaml')

    def modify_blueprint(self):
        old_openstack_plugin_yaml =\
            'http://www.getcloudify.org/spec/openstack-plugin/1.1/plugin.yaml'

        # modifying the Openstack plugin import in the nodecellar blueprint
        with YamlPatcher(self.blueprint_yaml) as patch:
            openstack_plugin_import_path = 'imports[1]'
            patch.set_value(openstack_plugin_import_path,
                            old_openstack_plugin_yaml)
