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

import requests

from cosmo_tester.test_suites.test_dockercompute import DockerComputeTestCase


class MonitoringTest(DockerComputeTestCase):

    def test_monitoring(self):

        blueprint_path = self.copy_blueprint('monitoring-dockercompute')
        self.blueprint_yaml = blueprint_path / 'blueprint.yaml'
        self.add_plugin_yaml_to_blueprint()

        expected_service_contains = 'example'
        expected_metric = 42.0

        self.upload_deploy_and_execute_install(fetch_state=False)

        self.wait_for_expected_outputs(
            expected_service_contains,
            expected_metric,
            timeout=300)

        url = "http://{0}/#/deployment/{1}/monitoring" \
              .format(self.env.management_ip, self.test_id)
        self.assert_grafana_path_active(url)

        self.uninstall_delete_deployment_and_blueprint()

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

    def assert_grafana_path_active(self, url):
        response = requests.get(url=url)
        self.assertEqual(response.status_code, requests.codes.ok,
                         "grafana url {0} returned status code {1}. "
                         "expecting 200 OK status code"
                         .format(url, response.status_code))
