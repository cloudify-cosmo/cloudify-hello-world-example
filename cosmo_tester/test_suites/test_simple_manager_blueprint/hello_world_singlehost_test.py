########
# Copyright (c) 2015 GigaSpaces Technologies Ltd. All rights reserved
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

from cosmo_tester.test_suites.test_blueprints.hello_world_bash_test \
    import AbstractHelloWorldTest
from cosmo_tester.test_suites.test_simple_manager_blueprint\
    .abstract_single_host_test import AbstractSingleHostTest


class HelloWorldSingleHostTest(AbstractHelloWorldTest, AbstractSingleHostTest):

    def setUp(self):
        super(HelloWorldSingleHostTest, self).setUp()
        self.setup_simple_manager_env()

    def test_hello_world_singlehost(self):
        self.bootstrap_simple_manager_blueprint()
        self._run(blueprint_file='singlehost-blueprint.yaml',
                  inputs=dict(self.access_credentials,
                              **{'server_ip': self.public_ip_address}),
                  delete_deployment=True)

    def _do_post_uninstall_assertions(self, context):
        instances = self.client.node_instances.list(self.test_id)
        for x in instances:
            self.assertEqual('deleted', x.state)
