########
# Copyright (c) 2015 GigaSpaces Technologies Ltd. All rights reserved
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

from cosmo_tester.test_suites.backwards.test_nodecellar_backwards_compatibility \
    .nodecellar_backwards_compatibility_test_base import \
    NodecellarNackwardsCompatibilityTestBase
from cosmo_tester.test_suites.test_blueprints.nodecellar_test import \
    OpenStackNodeCellarTestBase


class NodeCellar321BackwardsTest(OpenStackNodeCellarTestBase,
                                 NodecellarNackwardsCompatibilityTestBase):

    def test_321_openstack_nodecellar(self):
        self.setup_manager()
        self._test_openstack_nodecellar('openstack-blueprint.yaml')

    def get_inputs(self):

        return {
            'image': self.env.ubuntu_trusty_image_id,
            'flavor': self.env.small_flavor_id,
            'agent_user': 'ubuntu'
        }

    @property
    def repo_branch(self):
        return 'tags/3.2.1'

    @property
    def entrypoint_node_name(self):
        return 'nodecellar_floatingip'

    def get_manager_blueprint_inputs_override(self):
        # No openstack wagon for 3.2.1
        return {'install_python_compilers': 'true'}
