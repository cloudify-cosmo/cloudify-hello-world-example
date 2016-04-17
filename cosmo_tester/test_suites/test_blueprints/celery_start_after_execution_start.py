########
# Copyright (c) 2016 GigaSpaces Technologies Ltd. All rights reserved
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
from cloudify_rest_client.executions import Execution
from cosmo_tester.framework.testenv import TestCase


class CeleryStartAfterExecutionStart(TestCase):
    _RETRY_COUNT = 10

    def test_celery_start_after_execution(self):
        self._create_blueprint()
        self._stop_celery()
        self._create_execution()
        self._start_celery()
        self.wait_until_all_deployment_executions_end(
            deployment_id=self.test_id,
            end_status_list=[Execution.TERMINATED])

    def _create_blueprint(self):
        self.logger.info('setup blueprint')
        self.blueprint_path = self.copy_blueprint('mocks')
        self.blueprint_yaml = self.blueprint_path / 'empty-blueprint.yaml'

    def _create_execution(self):
        self.logger.info('create execution')
        self.client.blueprints.upload(
            blueprint_path=self.blueprint_yaml, blueprint_id=self.test_id)
        self.client.deployments.create(
            blueprint_id=self.test_id, deployment_id=self.test_id)
        self.client.executions.list(deployment_id=self.test_id)

    def _stop_celery(self):
        self.logger.info('celery stopping celery')
        with self.manager_env_fabric() as api:
            api.sudo('systemctl stop cloudify-mgmtworker')
            for _ in xrange(self._RETRY_COUNT):
                output = api.sudo(
                    'ps -ef | '
                    'grep celery | '
                    'grep -v color=auto | '
                    'wc -l')
                process_count = int(output) - 1
                if process_count == 0:
                    self.logger.info('celery stopped')
                    return
        self.fail('unable to stop celery')

    def _start_celery(self):
        self.logger.info('celery starting celery')
        with self.manager_env_fabric() as api:
            api.sudo('systemctl start cloudify-mgmtworker')
            for _ in xrange(self._RETRY_COUNT):
                output = api.sudo(
                    'ps -ef | '
                    'grep celery | '
                    'grep -v color=auto | '
                    'wc -l')
                process_count = int(output) - 1
                if process_count - 1 >= 2:
                    self.logger.info('celery started')
                    return
        self.fail('unable to start celery. '
                  '[NOTE: we can not start celery,'
                  ' so all the next suite tests will fail as well]')
