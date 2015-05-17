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

from cloudify_rest_client import CloudifyClient

from cosmo_tester.framework.util import YamlPatcher
from manager_recovery_base import BaseManagerRecoveryTest

# cloudify-cosmo-system-tests3 region a
UBUNTU_DOCKER_IMAGE_ID = 'b3322ff7-5e72-4459-b164-bdb800848289'


# This test can only run on a specific hp tenant
# that contains an ubuntu image running docker.
class ManagerRecoveryWithDockerTest(BaseManagerRecoveryTest):

    def test_manager_recovery(self):
        self._test_manager_recovery_impl()

    def bootstrap(self):
        with YamlPatcher(self.test_inputs_path) as inputs_patch:
            inputs_patch.set_value('image_id', UBUNTU_DOCKER_IMAGE_ID)

        self.cfy.bootstrap(blueprint_path=self.test_manager_blueprint_path,
                           inputs_file=self.test_inputs_path,
                           task_retries=10,
                           install_plugins=self.env.install_plugins)

        # override the client instance to use the correct ip
        self.client = CloudifyClient(self.cfy.get_management_ip())

        self.addCleanup(self.cfy.teardown)
