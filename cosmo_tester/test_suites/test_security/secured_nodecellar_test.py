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

from cloudify_rest_client.client import CloudifyClient
from cloudify_cli.constants import (CLOUDIFY_USERNAME_ENV,
                                    CLOUDIFY_PASSWORD_ENV)

from cosmo_tester.framework import util
from cosmo_tester.test_suites.test_blueprints.nodecellar_test \
    import OpenStackNodeCellarTestBase


TEST_CFY_USERNAME = 'user1'
TEST_CFY_PASSWORD = 'pass1'


class SecuredOpenstackNodecellarTest(OpenStackNodeCellarTestBase):

    def test_secured_openstack_nodecellar(self):
        inputs_path, mb_path = self._copy_manager_blueprint()
        self.test_manager_blueprint_path = path(mb_path)
        self.test_inputs_path = path(inputs_path)

        self._update_manager_blueprint_security()
        self._bootstrap()
        self._set_credentials_env_vars()
        self._running_env_setup()

        self._test_openstack_nodecellar('openstack-blueprint.yaml')

    def _copy_manager_blueprint(self):
        return util.generate_unique_configurations(
            workdir=self.workdir,
            original_inputs_path=self.env.cloudify_config_path,
            original_manager_blueprint_path=self.env._manager_blueprint_path)

    def _update_manager_blueprint_security(self):
        security_path = 'node_templates.manager.properties.cloudify.security'
        security_settings = {
            'enabled': 'true',
            'userstore_driver': {
                'implementation':
                    'flask_securest.userstores.simple:SimpleUserstore',
                'properties': {
                    'userstore': {
                        'user1': {
                            'username': 'user1',
                            'password': 'pass1',
                            'email': 'user1@domain.dom'
                        },
                        'user2': {
                            'username': 'user2',
                            'password': 'pass2',
                            'email': 'user2@domain.dom'
                        },
                        'user3': {
                            'username': 'user3',
                            'password': 'pass3',
                            'email': 'user3@domain.dom'
                        },
                    },
                    'identifying_attribute': 'username'
                }
            },
            'authentication_providers': [
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
        }
        self._update_manager_blueprint(security_path, security_settings)

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
        os.environ[CLOUDIFY_USERNAME_ENV] = TEST_CFY_USERNAME
        os.environ[CLOUDIFY_PASSWORD_ENV] = TEST_CFY_PASSWORD

    def _running_env_setup(self):
        self.env.management_ip = self.cfy.get_management_ip()
        self.client = CloudifyClient(
            self.env.management_ip,
            user=TEST_CFY_USERNAME,
            password=TEST_CFY_PASSWORD)

        response = self.client.manager.get_status()
        if not response['status'] == 'running':
            raise RuntimeError('Manager at {0} is not running.'
                               .format(self.management_ip))
