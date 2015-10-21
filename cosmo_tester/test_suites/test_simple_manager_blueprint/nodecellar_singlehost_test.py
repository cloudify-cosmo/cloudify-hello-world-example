########
# Copyright (c) 2014 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.

from cosmo_tester.test_suites.test_blueprints.nodecellar_test\
    import NodecellarAppTest
from cosmo_tester.test_suites.test_simple_manager_blueprint\
    .abstract_single_host_test import AbstractSingleHostTest


class NodecellarSingleHostTest(NodecellarAppTest, AbstractSingleHostTest):

    def setUp(self):
        super(NodecellarSingleHostTest, self).setUp()
        self.setup_simple_manager_env()

    def test_nodecellar_single_host(self):
        self.bootstrap_simple_manager_blueprint()
        self._test_nodecellar_impl('simple-blueprint.yaml')

    def get_public_ip(self, nodes_state):
        return self.public_ip_address

    def get_inputs(self):
        return dict(self.access_credentials,
                    **{'host_ip': self.private_ip_address})

    @property
    def expected_nodes_count(self):
        return 4

    @property
    def host_expected_runtime_properties(self):
        return []

    @property
    def entrypoint_node_name(self):
        return 'host'

    @property
    def entrypoint_property_name(self):
        return 'ip'
