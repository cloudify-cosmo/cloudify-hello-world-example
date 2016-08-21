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

import os

from cosmo_tester.framework.testenv import TestCase
from cosmo_tester.framework.util import get_blueprint_path


class ManagerMaintenanceModeTest(TestCase):

    def _check_maintenance_status(self, status):
        self.assertEqual(status, self.client.maintenance_mode.status().status)

    def _execute_install(self):
        self.logger.info("attempting to execute install on deployment {0}"
                         .format(self.test_id))
        self.wait_until_all_deployment_executions_end(self.test_id)
        return self.client.executions.start(
            deployment_id=self.test_id,
            workflow_id='install'
        )

    def test_maintenance_mode(self):

        self.blueprint_yaml = os.path.join(
            get_blueprint_path('continous-installation-blueprint'),
            'blueprint.yaml'
        )

        self.cfy.blueprints.upload(
            self.blueprint_yaml,
            blueprint_id=self.test_id
        )
        self.create_deployment(
            inputs={
                'image': self.env.ubuntu_trusty_image_id,
                'flavor': self.env.small_flavor_id,
                'agent_user': 'ubuntu'
            }
        )

        # Running not blocking installation
        execution = self._execute_install()

        self.logger.info(
            "checking if maintenance status has status 'deactivated'")
        self._check_maintenance_status('deactivated')

        self.logger.info('activating maintenance mode')
        self.client.maintenance_mode.activate()

        self.logger.info(
            "checking if maintenance status has changed to 'activating'")
        self.repetitive(self._check_maintenance_status, timeout=60,
                        exception_class=AssertionError, args=['activating'])

        self.logger.info('cancelling installation')
        self.cfy.executions.cancel(execution['id'])

        self.logger.info(
            "checking if maintenance status has changed to 'activated'")
        self.repetitive(self._check_maintenance_status, timeout=60,
                        exception_class=AssertionError, args=['activated'])

        self.logger.info('deactivating maintenance mode')
        self.client.maintenance_mode.deactivate()
        self.logger.info(
            "checking if maintenance status has changed to 'deactivated'")
        self.repetitive(self._check_maintenance_status, timeout=60,
                        exception_class=AssertionError, args=['deactivated'])

        self.uninstall_delete_deployment_and_blueprint()
