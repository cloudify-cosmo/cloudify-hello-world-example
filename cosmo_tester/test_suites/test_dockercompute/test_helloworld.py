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

import shutil

from cosmo_tester.framework.test_cases import (
    assert_deployment_monitoring_data_exists)
from cosmo_tester.test_suites.test_dockercompute import DockerComputeTestCase
from cosmo_tester.test_suites.test_blueprints.hello_world_bash_test import (
    clone_hello_world)


class DockerComputeHelloWorldTest(DockerComputeTestCase):

    def test_dockercompute_hello_world(self):
        helloworld = DockerHelloWorld(self)
        helloworld.full_test()


class DockerHelloWorld(object):

    def __init__(self, test_case, blueprint_id=None, deployment_id=None):
        self.test_case = test_case
        self.blueprint_id = blueprint_id or test_case.test_id
        self.deployment_id = deployment_id or test_case.test_id
        self._url = None

    def full_test(self):
        self.prepare()
        self.install()
        self.assert_installed()
        self.uninstall()
        self.assert_uninstalled()

    def prepare(self):
        repo_dir = clone_hello_world(self.test_case.workdir)
        blueprint_file = 'dockercompute-blueprint.yaml'
        self.test_case.blueprint_yaml = repo_dir / blueprint_file
        shutil.copy(self.test_case.blueprint_resource_path(
            'helloworld/{0}'.format(blueprint_file)),
            self.test_case.blueprint_yaml)
        self.test_case.add_plugin_yaml_to_blueprint()

    def install(self):
        self.test_case.upload_deploy_and_execute_install(
            fetch_state=False,
            blueprint_id=self.blueprint_id,
            deployment_id=self.deployment_id
        )

    def uninstall(self):
        self.test_case.uninstall_delete_deployment_and_blueprint(
            deployment_id=self.deployment_id
        )

    def assert_installed(self):
        self.assert_events()
        assert_deployment_monitoring_data_exists(
            self.test_case,
            deployment_id=self.deployment_id)
        self.assert_webserver_running()

    def assert_uninstalled(self):
        self.assert_web_server_not_running()

    def assert_events(self):
        events = self.test_case.client.events.list(
            deployment_id=self.deployment_id)
        self.test_case.assertGreater(len(events.items), 0)

    def assert_webserver_running(self):
        response = self.test_case.repetitive(self._webserver_request)
        self.test_case.assertIn('http_web_server', response)

    def assert_web_server_not_running(self):
        self.test_case.assertRaises(RuntimeError, self._webserver_request)

    def _webserver_request(self):
        return self.test_case.request(self.url, connect_timeout=1)

    @property
    def url(self):
        if not self._url:
            self._url = 'http://{0}:8080'.format(
                self.test_case.ip('vm', deployment_id=self.deployment_id))
        return self._url
