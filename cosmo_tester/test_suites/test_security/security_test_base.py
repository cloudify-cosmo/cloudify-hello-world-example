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


TEST_CFY_USERNAME = 'admin'
TEST_CFY_PASSWORD = 'admin'
SECURITY_PROP_PATH = 'node_types.cloudify\.nodes\.MyCloudifyManager.properties.' \
                     'security.default'


class SecurityTestBase(TestCase):

    def setup_secured_manager(self):
        self._copy_manager_blueprint()
        if self.get_ssl_enabled():
            self._handle_ssl_files()
        self._update_manager_blueprint()
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
        self.test_manager_types_path = os.path.join(
            self.workdir, 'manager-blueprint/types/manager-types.yaml')

    def _handle_ssl_files(self):
        pass

    def get_security_settings(self):
        settings = {
            SECURITY_PROP_PATH + '.enabled': self.get_enabled(),
        }

        authentication_providers = self.get_authentication_providers()
        if authentication_providers:
            settings[SECURITY_PROP_PATH + '.authentication_providers'] = \
                authentication_providers

        authorization_providers = self.get_authorization_providers()
        if authorization_providers:
            settings[SECURITY_PROP_PATH + '.authorization_providers'] = \
                authorization_providers

        userstore_drive = self.get_userstore_driver()
        if userstore_drive:
            settings[SECURITY_PROP_PATH + '.userstore_driver'] = \
                userstore_drive

        auth_token_generator = self.get_auth_token_generator()
        if auth_token_generator:
            settings[SECURITY_PROP_PATH + '.auth_token_generator'] = \
                auth_token_generator

        settings[SECURITY_PROP_PATH + '.ssl'] = {
            constants.SSL_ENABLED_PROPERTY_NAME: self.get_ssl_enabled(),
        }

        return settings

    def get_enabled(self):
        return True

    def get_userstore_driver(self):
        return ''

    def get_authentication_providers(self):
        return ''

    def get_authorization_providers(self):
        return ''

    def get_auth_token_generator(self):
        return ''

    def get_ssl_enabled(self):
        return False

    def _update_manager_blueprint(self):
        security_settings = self.get_security_settings()
        with util.YamlPatcher(self.test_manager_types_path) as patch:
            for key, value in security_settings.items():
                patch.set_value(key, value)

        props = self.get_manager_blueprint_additional_props_override()
        with util.YamlPatcher(self.test_manager_blueprint_path) as patch:
            for key, value in props.items():
                patch.set_value(key, value)

    def get_manager_blueprint_additional_props_override(self):
        return {}

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
