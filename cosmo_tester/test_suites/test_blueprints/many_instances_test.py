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

import time

from cosmo_tester.framework.testenv import TestCase


class ManyInstancesTest(TestCase):

    def test_many_instances(self):
        blueprint_path = self.copy_blueprint('many-instances')
        self.blueprint_yaml = blueprint_path / 'blueprint.yaml'

        self.cfy.blueprints.upload(
            self.blueprint_yaml,
            blueprint_id=self.test_id
        )
        self.create_deployment()

        # elasticsearch takes its time, so it might initially fail
        # with IndexError
        deployment_env_creation_execution = self.repetitive(
            lambda: self.client.executions.list(deployment_id=self.test_id)[0],
            exception_class=IndexError)

        self.logger.info('Waiting for create_deployment_environment workflow '
                         'execution to terminate')
        self.wait_for_execution(deployment_env_creation_execution, timeout=240)

        execution = self.client.executions.start(deployment_id=self.test_id,
                                                 workflow_id='install')
        self.logger.info('Waiting for install workflow to terminate')
        start = time.time()
        self.wait_for_execution(execution, timeout=600)
        self.logger.info('All done! execution took {} seconds'
                         .format(time.time() - start))
