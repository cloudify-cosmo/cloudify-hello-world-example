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

from cloudify_cli import constants
from cloudify_rest_client.client import CloudifyClient
from cosmo_tester.framework import util

from cosmo_tester.framework.testenv import TestCase


TEST_CFY_USERNAME = 'user1'
TEST_CFY_PASSWORD = 'pass1'


class SecurityTestBase(TestCase):

    def setup_secured_manager(self):
        self._copy_manager_blueprint()
        prop_path = 'node_templates.manager.properties.cloudify.security'
        new_value = self.get_security_settings()
        self._update_manager_blueprint({prop_path: new_value})
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
        settings = {
            'enabled': self.get_enabled(),
            'authentication_providers': self.get_authentication_providers_list()
        }
        userstore = self.get_userstore()
        if userstore:
            settings['userstore_driver'] = {
                'implementation': self.get_userstore_driver_implementation(),
                'properties': {
                    'userstore': userstore,
                    },
                'identifying_attribute': self.get_identifying_attribute()
            }
        auth_token_generator = self.get_auth_token_generator()
        if auth_token_generator:
            settings['auth_token_generator'] = auth_token_generator
        ssl_settings = self.get_ssl_settings()
        if ssl_settings:
            settings['ssl'] = ssl_settings
        return settings

    def get_enabled(self):
        True

    def get_userstore_driver_implementation(self):
        return 'flask_securest.userstores.simple:SimpleUserstore'

    def get_userstore(self):
        return {
            'user1':
                {
                    'username': 'user1',
                    'password': 'pass1',
                    'email': 'user1@domain.dom'
                }
        }

    def get_identifying_attribute(self):
        return 'username'

    def get_authentication_providers_list(self):
        return [
            {
                'name': 'password',
                'implementation': 'flask_securest.'
                                  'authentication_providers.password:'
                                  'PasswordAuthenticator',
                'properties': {
                    'password_hash': 'plaintext'
                }
            }
        ]

    def get_auth_token_generator(self):
        return ''

    def get_ssl_settings(self):
        return ''

    def _update_manager_blueprint(self, props):
        with util.YamlPatcher(self.test_manager_blueprint_path) as patch:
            for key, value in props.items():
                patch.set_value(key, value)

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

        def clean_mgmt_ip():
            self.env.management_ip = None
        self.addCleanup(clean_mgmt_ip)

        response = self.client.manager.get_status()
        if not response['status'] == 'running':
            raise RuntimeError('Manager at {0} is not running.'
                               .format(self.env.management_ip))

