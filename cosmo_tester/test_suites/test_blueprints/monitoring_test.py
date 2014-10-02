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

from cosmo_tester.framework.testenv import TestCase


class MonitoringTest(TestCase):

    def test_monitoring(self):

        blueprint_path = self.copy_blueprint('monitoring')
        self.blueprint_yaml = blueprint_path / 'blueprint.yaml'

        expected_service_contains = 'example'
        expected_metric = 42.0

        self.upload_deploy_and_execute_install(inputs={
            'image_name': self.env.ubuntu_image_name,
            'flavor_name': self.env.flavor_name,
        })

        self.wait_for_expected_outputs(
            expected_service_contains,
            expected_metric,
            timeout=300)

        self.execute_uninstall()

    def wait_for_expected_outputs(self,
                                  expected_service_contains,
                                  expected_metric,
                                  timeout):
        def assertion():
            outputs = self.client.deployments.outputs.get(self.test_id)
            outputs = outputs['outputs']
            self.assertIn(expected_service_contains, outputs['service'] or '')
            self.assertEqual(expected_metric, outputs['metric'])
        self.repetitive(assertion, timeout=timeout)
