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

from cloudify_rest_client.exceptions import CloudifyClientError
from cosmo_tester.framework.git_helper import clone
from cosmo_tester.framework.test_cases import MonitoringTestCase
from cosmo_tester.framework.cfy_helper import DEFAULT_EXECUTE_TIMEOUT


class NodecellarAppTest(MonitoringTestCase):

    def _test_nodecellar_impl(
        self, blueprint_file, execute_timeout=DEFAULT_EXECUTE_TIMEOUT
    ):
        self.repo_dir = clone(self.repo_url, self.workdir, self.repo_branch)
        self.blueprint_yaml = self.repo_dir / blueprint_file

        self.modify_blueprint()

        before, after = self.install(
            inputs=self.get_inputs(),
            execute_timeout=execute_timeout
        )

        self.post_install_assertions(before, after)

        self.execute_uninstall(deployment_id=self.test_id,
                               delete_deployment_and_blueprint=True)

        self.post_uninstall_assertions()

    def modify_blueprint(self):
        pass

    def get_inputs(self):
        raise RuntimeError('Must be implemented by Subclasses')

    def assert_nodecellar_working(self, public_ip):
        nodejs_server_page_response = requests.get(
            'http://{0}:{1}'.format(self.public_ip, self.nodecellar_port))
        self.assertEqual(200, nodejs_server_page_response.status_code,
                         'Failed to get home page of nodecellar app')
        page_title = 'Node Cellar'
        self.assertTrue(page_title in nodejs_server_page_response.text,
                        'Expected to find {0} in web server response: {1}'
                        .format(page_title, nodejs_server_page_response))

        wines_page_response = self._get_wines_request()
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

    def _get_wines_request(self):
        return requests.get('http://{0}:{1}/wines'.format(
            self.public_ip, self.nodecellar_port))

    def get_public_ip(self, nodes_state):
        outputs = self.client.deployments.outputs.get(self.test_id)
        return outputs['outputs']['endpoint']['ip_address']

    def assert_host_state_and_runtime_properties(self, nodes_state):
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
        self.public_ip = self.get_public_ip(nodes_state)
        self.assert_host_state_and_runtime_properties(nodes_state)
        self.assert_monitoring_data_exists()
        self.assertIsNotNone(self.public_ip,
                             'Could not find the '
                             '"{0}" node for '
                             'retrieving the public IP'
                             .format(self.entrypoint_node_name))

        events, total_events = self.client.events.get(execution_by_id.id)

        self.assertGreater(len(events), 0,
                           'Expected at least 1 event for execution id: {0}'
                           .format(execution_by_id.id))

        self.assert_nodecellar_working(self.public_ip)

    def assert_monitoring_data_exists(self):
        client = InfluxDBClient(self.env.management_ip, 8086, 'root', 'root',
                                'cloudify')
        self._assert_mongodb_collector_data(client)
        self.assert_deployment_monitoring_data_exists(self.deployment_id)

    def post_uninstall_assertions(self, client=None):
        client = client or self.client

        nodes_instances = client.node_instances.list(self.deployment_id)
        self.assertFalse(any(node_ins for node_ins in nodes_instances if
                             node_ins.state != 'deleted'))
        try:
            requests.get('http://{0}:{1}'.format(self.public_ip,
                                                 self.nodecellar_port))
            self.fail('Expected a no route to host error to be raised when '
                      'trying to retrieve the web page after uninstall, '
                      'but no error was raised.')
        except ConnectionError:
            pass

    def _assert_mongodb_collector_data(self, influx_client):

        # retrieve some instance id of the mongodb node
        instance_id = self.client.node_instances.list(
            self.deployment_id, self.mongo_node_name)[0].id

        try:
            # select metrics from the mongo collector explicitly to verify
            # it is working properly
            query = 'select sum(value) from /{0}\.{1}\.{' \
                    '2}\.mongo_connections_totalCreated/' \
                .format(self.deployment_id, self.mongo_node_name,
                        instance_id)
            influx_client.query(query)
        except Exception as e:
            self.fail('monitoring events for {0} node instance '
                      'with id {1} were not found on influxDB. error is: {2}'
                      .format(self.mongo_node_name, instance_id, e))

    def before_uninstall(self):
        pass

    @property
    def repo_url(self):
        return 'https://github.com/cloudify-cosmo/' \
               'cloudify-nodecellar-example.git'

    @property
    def repo_branch(self):
        return None  # will use git_helper.clone default branch

    @property
    def expected_nodes_count(self):
        return 8

    @property
    def host_expected_runtime_properties(self):
        return ['ip', 'networks']

    @property
    def entrypoint_node_name(self):
        return 'nodecellar_ip'

    @property
    def entrypoint_property_name(self):
        return 'floating_ip_address'

    @property
    def nodecellar_port(self):
        return 8080

    @property
    def mongo_node_name(self):
        return 'mongod'


class OpenStackNodeCellarTestBase(NodecellarAppTest):

    def _do_uninstall(self, deployment_id):
        """Make sure the deployment is uninstalled.

        Even if the install workflow fails partway, this makes sure the
        uninstall workflow runs to clean up.
        Running the uninstall workflow might also be part of the test,
        so the deployment might already have been uninstalled.
        """
        try:
            self.client.deployments.get(deployment_id)
        except CloudifyClientError as e:
            if e.status_code == 404:
                return  # already uninstalled
            else:
                raise  # some other error? we'd better not hide it
        else:
            self.execute_uninstall(deployment_id=deployment_id,
                                   delete_deployment_and_blueprint=True)

    def _test_openstack_nodecellar(self, blueprint_file):

        self.addCleanup(self._do_uninstall, deployment_id=self.test_id)
        self.addCleanup(self.env.handler.remove_keypairs_from_manager,
                        deployment_id=self.test_id)

        self._test_nodecellar_impl(blueprint_file)

    def get_inputs(self):

        return {
            'image': self.env.ubuntu_trusty_image_id,
            'flavor': self.env.small_flavor_id,
            'agent_user': 'ubuntu'
        }


class OpenStackNodeCellarTest(OpenStackNodeCellarTestBase):

    def test_openstack_nodecellar(self):
        self._test_openstack_nodecellar('openstack-blueprint.yaml')
