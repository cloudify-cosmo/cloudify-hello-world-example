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


import time

from cosmo_tester.framework.testenv import TestCase


class ManyInstancesTest(TestCase):

    def test_many_instances(self):
        blueprint_path = self.copy_blueprint('many-instances')
        self.blueprint_yaml = blueprint_path / 'blueprint.yaml'

        self.cfy.upload_blueprint(
            blueprint_id=self.test_id,
            blueprint_path=self.blueprint_yaml)
        self.cfy.create_deployment(
            blueprint_id=self.test_id,
            deployment_id=self.test_id)

        install_workers = self.client.deployments.list_executions(
            deployment_id=self.test_id)[0]
        self.logger.info('Waiting for install workers workflow to terminate')
        self.wait_for_execution(install_workers, timeout=120)

        execution = self.client.deployments.execute(deployment_id=self.test_id,
                                                    workflow_id='install')
        self.logger.info('Waiting for install workflow to terminate')
        start = time.time()
        self.wait_for_execution(execution, timeout=600)
        self.logger.info('All done! execution took {} seconds'
                         .format(time.time() - start))
