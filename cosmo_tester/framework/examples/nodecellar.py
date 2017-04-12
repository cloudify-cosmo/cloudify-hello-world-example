########
# Copyright (c) 2017 GigaSpaces Technologies Ltd. All rights reserved
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

import json

import pytest
import requests

from . import AbstractExample


class NodeCellarExample(AbstractExample):

    REPOSITORY_URL = 'https://github.com/cloudify-cosmo/cloudify-nodecellar-example.git'  # noqa

    @property
    def inputs(self):
        if not self._inputs:
            if 'openstack' in self._blueprint_file:
                self._inputs = {
                    'floating_network_id': self.attributes.floating_network_id,
                    'key_pair_name': self.attributes.keypair_name,
                    'private_key_path': self.manager.remote_private_key_path,
                    'network_name': self.attributes.network_name,
                    'image': self.attributes.ubuntu_14_04_image_name,
                    'flavor': self.attributes.medium_flavor_name,
                    'agent_user': self.attributes.ubuntu_username
                }
            elif self._blueprint_file == 'simple-blueprint.yaml':
                self._inputs = {
                    'host_ip': self.manager.ip_address,
                    'agent_user': self.attributes.centos7_username,
                    'agent_private_key_path':
                        self.manager.remote_private_key_path
                }
            else:
                self._inputs = {}
        return self._inputs

    def verify_installation(self):
        super(NodeCellarExample, self).verify_installation()
        self.assert_nodecellar_working(self.outputs['endpoint'])
        self.assert_mongodb_collector_data()

    def assert_mongodb_collector_data(self):

        influxdb = self.manager.influxdb_client

        # retrieve some instance id of the mongodb node
        mongo_node_name = 'mongod'
        instance_id = self.manager.client.node_instances.list(
                self.deployment_id, mongo_node_name)[0].id

        try:
            # select metrics from the mongo collector explicitly to verify
            # it is working properly
            query = 'select sum(value) from /{0}\.{1}\.{' \
                    '2}\.mongo_connections_totalCreated/' \
                .format(self.deployment_id, mongo_node_name,
                        instance_id)
            influxdb.query(query)
        except Exception as e:
            pytest.fail('monitoring events for {0} node instance '
                        'with id {1} were not found on influxDB. error is: {2}'
                        .format(mongo_node_name, instance_id, e))

    def assert_nodecellar_working(self, endpoint):
        nodecellar_base_url = 'http://{0}:{1}'.format(endpoint['ip_address'],
                                                      endpoint['port'])
        nodejs_server_page_response = requests.get(nodecellar_base_url)
        self.assertEqual(200, nodejs_server_page_response.status_code,
                         'Failed to get home page of nodecellar app')
        page_title = 'Node Cellar'
        self.assertTrue(page_title in nodejs_server_page_response.text,
                        'Expected to find {0} in web server response: {1}'
                        .format(page_title, nodejs_server_page_response))

        wines_page_response = requests.get(
                '{0}/wines'.format(nodecellar_base_url))
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
