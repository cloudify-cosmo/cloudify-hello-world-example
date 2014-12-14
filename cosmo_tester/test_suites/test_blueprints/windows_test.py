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

""" Assumes fabric environment already set up """

__author__ = 'elip'

from cosmo_tester.framework.testenv import TestCase


class WindowsAgentTest(TestCase):

    def test_windows(self):

        blueprint_path = self.copy_blueprint('windows')
        self.blueprint_yaml = blueprint_path / 'blueprint.yaml'

        self.upload_deploy_and_execute_install()

        # self.test_id is the default deployment id
        outputs = self.client.deployments.outputs.get(self.test_id)

        # check that our host plugin task was executed
        # see 'tasks.task' in the windows blueprint plugin
        self.assertTrue(outputs['task_execution']['executed'])

        self.execute_uninstall()


