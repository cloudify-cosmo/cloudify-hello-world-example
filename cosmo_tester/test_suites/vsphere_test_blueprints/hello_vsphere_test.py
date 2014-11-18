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


__author__ = 'boris'


class HelloVsphereTest(TestCase):
    """Tests vSphere with basic blueprint
       To run this tests locally you should have VSPHERE_PLUGIN_TOKEN and
       CLOUDIFY_AUTOMATION_TOKEN env variables set (see quickbuild's vars for the values)
    """
    def test_hello(self):
        self.token_place_holder = '{VSPHERE_PLUGIN_TOKEN}'
        self.token_env_variable = 'VSPHERE_PLUGIN_TOKEN'
        self.cloudify_automation_token_place_holder = '{CLOUDIFY_AUTOMATION_TOKEN}'
        self.cloudify_automation_token_env_variable = 'CLOUDIFY_AUTOMATION_TOKEN'
        self.base_url='https://raw.githubusercontent.com/Gigaspaces/cloudify-vsphere-plugin/master/plugin.yaml'
        blueprint_path = self.copy_blueprint('hello-vsphere')
        self.blueprint_yaml = blueprint_path / 'blueprint.yaml'
        self.download_and_modify_plugin(blueprint_path)

        self.cfy.upload_blueprint(
            blueprint_id=self.test_id,
            blueprint_path=self.blueprint_yaml)
        self.cfy.create_deployment(
            blueprint_id=self.test_id,
            deployment_id=self.test_id)

        deployment_env_creation_execution = \
            self.client.executions.list(
                deployment_id=self.test_id)[0]
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

    def download_and_modify_plugin(self, blueprint_path):
        url = '{0}?token={1}'.format(self.base_url,
                                     os.environ.get(self.token_env_variable))
        plugin = urllib.URLopener()
        file_path = blueprint_path+"/plugin.yaml"
        plugin.retrieve(url, file_path)
        with open(file_path, 'r') as f:
            newlines = []
            for line in f.readlines():
                newlines.append(line.replace(self.cloudify_automation_token_place_holder,
                                             os.environ.get(self.cloudify_automation_token_env_variable)))
        with open(file_path, 'w') as f:
            for line in newlines:
                f.write(line)