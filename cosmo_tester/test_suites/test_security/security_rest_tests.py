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
import shutil

from fabric import api as fabric_api
from path import path

from cosmo_tester.framework import util
from cosmo_tester.framework.testenv import TestCase


class SecurityTests(TestCase):

    def test_secured_nodecellar(self):
        inputs_path, mb_path = self._copy_manager_blueprint()
        self.test_manager_blueprint_path = path(mb_path)
        self.test_inputs_path = path(inputs_path)

        security_path = 'node_templates.manager.properties.cloudify.security'
        security_settings = {
            'enabled': 'true',
            'userstore_driver': {
                'implementation':
                    'flask_securest.userstores.file:FileUserstore',
                'properties': {
                    'userstore_file': 'users.yaml',
                    'identifying_attribute': 'username'
                }
            },
            'authentication_methods': {
                [
                    {
                        'name': 'password',
                        'implementation': 'flask_securest.'
                                          'authentication_providers.password:'
                                          'PasswordAuthenticator',
                        'properties': {
                            'password_hash': 'plaintext'
                        }
                    },
                    {
                        'name': 'token',
                        'implementation': 'flask_securest.'
                                          'authentication_providers.token:'
                                          'TokenAuthenticator',
                        'properties': {
                            'secret_key': 'yaml_secret'
                        }
                    }
                ]
            }
        }

        self._update_manager_blueprint(security_path, security_settings)
        self._bootstrap()
        self._assert_plugins_installed()

    def _copy_manager_blueprint(self):
        return util.generate_unique_configurations(
            workdir=self.workdir,
            original_inputs_path=self.env.cloudify_config_path,
            original_manager_blueprint_path=self.env._manager_blueprint_path)

    def _update_manager_blueprint(self, prop_path, new_value):
        with util.YamlPatcher(self.test_manager_blueprint_path) as patch:
            patch.set_value(prop_path, new_value)

    def _bootstrap(self):
        self.cfy.bootstrap(blueprint_path=self.test_manager_blueprint_path,
                           inputs_file=self.test_inputs_path,
                           task_retries=5,
                           install_plugins=False)
        self.addCleanup(self.cfy.teardown)
