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

        diamond_config = {}

        expected_service_contains = ''
        expected_metric_contains = ''

        self.upload_deploy_and_execute_install(inputs={
            'image_name': self.env.self.env.ubuntu_image_name,
            'flavor': self.env.flavor_name,
            'diamond_config': diamond_config
        })

        self.wait_for_expected_outputs({
            'service': expected_service_contains,
            'metric': expected_metric_contains
        }, timeout=300)

    def wait_for_expected_outputs(self, expected_outputs, timeout):
        def assertion():
            outputs = self.client.deployments.outputs.get(self.test_id)
            for output_name, expected_value in expected_outputs.items():
                self.assertIn(expected_value,
                              outputs[output_name]['value'][0])
        self.repetitive(assertion, timeout=timeout)
