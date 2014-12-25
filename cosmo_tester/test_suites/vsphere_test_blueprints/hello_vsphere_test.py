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
import os
import time
import urllib

from cosmo_tester.framework.testenv import TestCase


class HelloVsphereTest(TestCase):
    """Tests vSphere with basic blueprint
       To run this tests locally you should have CLOUDIFY_AUTOMATION_TOKEN
       env variable set (see quickbuild's vars for the values)
    """
    def test_hello(self):
        self.cloudify_automation_token_ph = '{CLOUDIFY_AUTOMATION_TOKEN}'
        self.cloudify_automation_token_var = 'CLOUDIFY_AUTOMATION_TOKEN'
        blueprint_path = self.copy_blueprint('hello-vsphere')
        self.blueprint_yaml = blueprint_path / 'blueprint.yaml'
        self.download_and_modify_plugin(blueprint_path)

        self.cfy.upload_blueprint(
            blueprint_id=self.test_id,
            blueprint_path=self.blueprint_yaml)
        self.cfy.create_deployment(
            blueprint_id=self.test_id,
            deployment_id=self.test_id)

        deployment_env_creation_execution = self.repetitive(
            lambda: self.client.executions.list(deployment_id=self.test_id)[0],
            exception_class=IndexError)

        self.logger.info('Waiting for create_deployment_environment workflow '
                         'execution to terminate')
        self.wait_for_execution(deployment_env_creation_execution, timeout=240)
        self.execute_workflow('install', 720)
        self.execute_workflow('uninstall', 600)

    def execute_workflow(self, exec_type, timeout_seconds):
        execution = self.client.executions.start(deployment_id=self.test_id,
                                                 workflow_id=exec_type)
        self.logger.info('Waiting for workflow {} to terminate'
                         .format(exec_type))
        start = time.time()
        self.wait_for_execution(execution, timeout=timeout_seconds)
        self.logger.info('workflow {} done! execution took {} seconds'
                         .format(exec_type, time.time() - start))

    def download_and_modify_plugin(self, blueprint_path):
        url = 'http://getcloudify.org.s3.amazonaws.com' \
              '/spec/vsphere-plugin/1.1/plugin.yaml'
        plugin = urllib.URLopener()
        file_path = blueprint_path+"/plugin.yaml"
        plugin.retrieve(url, file_path)
        with open(file_path, 'r') as f:
            newlines = []
            for line in f.readlines():
                newlines.append(line.replace
                                (self.cloudify_automation_token_ph,
                                    os.environ.get
                                    (self.cloudify_automation_token_var)))
        with open(file_path, 'w') as f:
            for line in newlines:
                f.write(line)
