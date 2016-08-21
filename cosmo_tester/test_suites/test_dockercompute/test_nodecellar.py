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
from cosmo_tester.framework.git_helper import clone
from cosmo_tester.test_suites.test_dockercompute import DockerComputeTestCase
from cosmo_tester.test_suites.test_blueprints.nodecellar_test import (
    NodecellarAppTest)


class DockerComputeNodeCellarTest(DockerComputeTestCase, NodecellarAppTest):

    def test_dockercompute_nodecellar(self):
        nodecellar = DockerNodeCellar(self)
        nodecellar.full_test()


class DockerNodeCellar(object):

    def __init__(self, test_case, blueprint_id=None, deployment_id=None):
        self.test_case = test_case
        self.blueprint_id = blueprint_id or test_case.test_id
        self.deployment_id = deployment_id or test_case.test_id
        self._ip = None

    def full_test(self):
        self.prepare()
        self.install()
        self.assert_installed()
        self.uninstall()
        self.assert_uninstalled()

    def prepare(self):
        repo_dir = clone(self.test_case.repo_url,
                         self.test_case.workdir,
                         self.test_case.repo_branch)
        self.test_case.blueprint_yaml = repo_dir / self.blueprint_file
        shutil.copy(self.test_case.blueprint_resource_path(
            'nodecellar/{0}'.format(self.blueprint_file)),
            self.test_case.blueprint_yaml)
        shutil.copy(self.test_case.blueprint_resource_path(
            'nodecellar/types/dockercompute-types.yaml'),
            repo_dir / 'types' / 'dockercompute-types.yaml')
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
        self.assert_webserver_running()
        assert_deployment_monitoring_data_exists(
            test_case=self.test_case, deployment_id=self.deployment_id)

    def assert_uninstalled(self):
        self.assert_web_server_not_running()

    def assert_webserver_running(self):
        response = self.test_case.repetitive(self._webserver_request)
        self.test_case.assertEqual(list, type(response))
        self.test_case.assertGreater(len(response), 1)

    def assert_web_server_not_running(self):
        self.test_case.assertRaises(RuntimeError, self._webserver_request)

    def _webserver_request(self):
        return self.test_case.request(self.url, connect_timeout=1, json=True)

    @property
    def blueprint_file(self):
        return 'dockercompute-blueprint.yaml'

    @property
    def ip(self):
        if not self._ip:
            self._ip = self.test_case.ip('nodejs_host',
                                         deployment_id=self.deployment_id)
        return self._ip

    @property
    def url(self):
        return 'http://{0}:{1}/wines'.format(self.ip,
                                             self.test_case.nodecellar_port)
