########
# Copyright (c) 2015 GigaSpaces Technologies Ltd. All rights reserved
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
from path import path

from cloudify import constants
from cloudify_rest_client.client import CloudifyClient

from cosmo_tester.framework import util
from cosmo_tester.framework.testenv import TestCase


TEST_CFY_USERNAME = 'user1'
TEST_CFY_PASSWORD = 'pass1'


class SecurityTestBase(TestCase):

    def setup_secured_manager(self):
        self._copy_manager_blueprint()
        self._update_manager_blueprint(
            prop_path='node_templates.manager.properties.cloudify.security',
            new_value=self.get_security_settings()
        )
        self._bootstrap()
        self._set_credentials_env_vars()
        self._running_env_setup()

    def _copy_manager_blueprint(self):
        inputs_path, mb_path = util.generate_unique_configurations(
            workdir=self.workdir,
            original_inputs_path=self.env.cloudify_config_path,
            original_manager_blueprint_path=self.env._manager_blueprint_path)
        self.test_manager_blueprint_path = path(mb_path)
        self.test_inputs_path = path(inputs_path)

    def get_security_settings(self):
        raise RuntimeError('Must be implemented by Subclasses')

    def _update_manager_blueprint(self, prop_path, new_value):
        with util.YamlPatcher(self.test_manager_blueprint_path) as patch:
            patch.set_value(prop_path, new_value)

    def _bootstrap(self):
        self.cfy.bootstrap(blueprint_path=self.test_manager_blueprint_path,
                           inputs_file=self.test_inputs_path,
                           task_retries=5,
                           install_plugins=self.env.install_plugins)
        self.addCleanup(self.cfy.teardown)

    def _set_credentials_env_vars(self):
        os.environ[constants.CLOUDIFY_USERNAME_ENV] = TEST_CFY_USERNAME
        os.environ[constants.CLOUDIFY_PASSWORD_ENV] = TEST_CFY_PASSWORD

    def set_rest_client(self):
        self.client = CloudifyClient(
            host=self.env.management_ip,
            headers=util.get_auth_header(username=TEST_CFY_USERNAME,
                                         password=TEST_CFY_PASSWORD))

    def _running_env_setup(self):
        self.env.management_ip = self.cfy.get_management_ip()
        self.set_rest_client()
        response = self.client.manager.get_status()
        if not response['status'] == 'running':
            raise RuntimeError('Manager at {0} is not running.'
                               .format(self.management_ip))

    def get_ssl_enabled(self):
        return False
