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


SECURITY_PROP_PATH = 'node_types.cloudify\.nodes\.MyCloudifyManager.' \
                     'properties.security.default'
REST_PLUGIN_PATH = 'node_templates.rest_service.properties.plugins'
USERDATA_PATH = 'node_templates.manager_host.properties.parameters.user_data'


class SecurityTestBase(TestCase):

    TEST_CFY_USERNAME = 'admin'
    TEST_CFY_PASSWORD = 'admin'

    def setup_secured_manager(self):
        self._copy_manager_blueprint()
        if self.get_ssl_enabled():
            self._handle_ssl_files()
        if self.get_file_userstore_enabled():
            self._update_userstore_file()
        self._update_manager_blueprint()
        self._set_credentials_env_vars()
        self._bootstrap()
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
        self.test_userstore_file_path = os.path.join(
            self.workdir, 'manager-blueprint/resources/rest/userstore.yaml')

    def _handle_ssl_files(self):
        pass

    def get_security_settings(self):
        settings = {
            '{0}.enabled'.format(SECURITY_PROP_PATH): self.get_enabled(),
        }

        authentication_providers = self.get_authentication_providers()
        if authentication_providers:
            settings[
                '{0}.authentication_providers'.format(SECURITY_PROP_PATH)] = \
                authentication_providers

        authorization_provider = self.get_authorization_provider()
        if authorization_provider is not None:
            settings[
                '{0}.authorization_provider'.format(SECURITY_PROP_PATH)] = \
                authorization_provider

        userstore_drive = self.get_userstore_driver()
        if userstore_drive is not None:
            settings[
                '{0}.userstore_driver'.format(SECURITY_PROP_PATH)] = \
                userstore_drive

        auth_token_generator = self.get_auth_token_generator()
        if auth_token_generator:
            settings[
                '{0}.auth_token_generator'.format(SECURITY_PROP_PATH)] = \
                auth_token_generator

        settings[
            '{0}.ssl'.format(SECURITY_PROP_PATH)] = {
            constants.SSL_ENABLED_PROPERTY_NAME: self.get_ssl_enabled(),
        }

        return settings

    def get_enabled(self):
        return True

    def get_userstore_driver(self):
        return None

    def get_authentication_providers(self):
        return None

    def get_authorization_provider(self):
        return None

    def get_auth_token_generator(self):
        return None

    def get_ssl_enabled(self):
        return False

    def get_rest_plugins(self):
        return None

    def get_file_userstore_enabled(self):
        return False

    # Currently supports userdata injection to the ec2 manager bp only.
    def get_userdata(self):
        return None

    def _update_manager_blueprint(self):
        security_settings = self.get_security_settings()
        with util.YamlPatcher(self.test_manager_types_path) as patch:
            for key, value in security_settings.items():
                patch.set_value(key, value)

        props = self.get_manager_blueprint_additional_props_override()
        with util.YamlPatcher(self.test_manager_blueprint_path) as patch:
            for key, value in props.items():
                patch.set_value(key, value)

    def get_userstore_users(self):
        return None

    def get_userstore_groups(self):
        return None

    def get_userstore_settings(self):
        settings = {}
        users = self.get_userstore_users()
        if users:
            settings['users'] = users
        groups = self.get_userstore_groups()
        if groups:
            settings['groups'] = groups

        return settings

    def _update_userstore_file(self):
        userstore_settings = self.get_userstore_settings()
        with util.YamlPatcher(self.test_userstore_file_path) as patch:
            for key, value in userstore_settings.items():
                patch.set_value(key, value)

    def get_manager_blueprint_additional_props_override(self):
        overrides = {}
        rest_plugins = self.get_rest_plugins()
        if rest_plugins:
            overrides = {'{0}'.format(REST_PLUGIN_PATH): rest_plugins}
        userdata = self.get_userdata()
        if userdata:
            overrides['{0}'.format(USERDATA_PATH)] = \
                userdata
        return overrides

    def _bootstrap(self):
        self.addCleanup(self.cfy.teardown)
        self.cfy.bootstrap(blueprint_path=self.test_manager_blueprint_path,
                           inputs_file=self.test_inputs_path,
                           task_retries=5,
                           install_plugins=self.env.install_plugins)

    def _set_credentials_env_vars(self):
        os.environ[constants.CLOUDIFY_USERNAME_ENV] = self.TEST_CFY_USERNAME
        os.environ[constants.CLOUDIFY_PASSWORD_ENV] = self.TEST_CFY_PASSWORD

    def _unset_credentials_env_vars(self):
        os.environ.pop(constants.CLOUDIFY_USERNAME_ENV, None)
        os.environ.pop(constants.CLOUDIFY_PASSWORD_ENV, None)

    def set_rest_client(self):
        self.client = CloudifyClient(
            host=self.env.management_ip,
            headers=util.get_auth_header(username=self.TEST_CFY_USERNAME,
                                         password=self.TEST_CFY_PASSWORD))

    def _running_env_setup(self):

        def clear_mgmt_and_security_settings():
            self.env.management_ip = None
            self.env.rest_client = None
            self._unset_credentials_env_vars()
        self.addCleanup(clear_mgmt_and_security_settings)
        self.env.management_ip = self.cfy.get_management_ip()
        self.set_rest_client()

        response = self.client.manager.get_status()
        if not response['status'] == 'running':
            raise RuntimeError('Manager at {0} is not running.'
                               .format(self.env.management_ip))
