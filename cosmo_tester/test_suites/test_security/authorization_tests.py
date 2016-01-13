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
#

from cosmo_tester.test_suites.test_security import auth_test_base


class AuthorizationTests(auth_test_base.BaseAuthTest):

    # overriding super's credentials
    TEST_CFY_USERNAME = 'alice'
    TEST_CFY_PASSWORD = 'alice_password'

    def setUp(self):
        super(AuthorizationTests, self).setUp()
        self.setup_secured_manager()

    def test_authorization(self):
        self._test_authorization()

    ######################################
    # override default security settings
    ######################################
    def get_authorization_provider(self):
        return {
            'implementation': 'flask_securest.authorization_providers.'
                              'role_based_authorization_provider:'
                              'RoleBasedAuthorizationProvider',
            'properties': {
                'roles_config_file_path': '/opt/manager/roles_config.yaml',
                'role_loader': {
                    'implementation':
                        'flask_securest.authorization_providers.role_loaders.'
                        'simple_role_loader:SimpleRoleLoader'
                }
            }
        }

    def get_userstore_users(self):
        return [
            {
                'username': self.admin_username,
                'password': self.admin_password,
                'groups': ['cfy_admins']
            },
            {
                'username': self.deployer_username,
                'password': self.deployer_password,
                'groups': ['managers', 'users']
            },
            {
                'username': self.viewer_username,
                'password': self.viewer_password,
                'groups': ['users'],
                'roles': ['viewer']
            },
            {
                'username': self.no_role_username,
                'password': self.no_role_password,
                'groups': ['users']
            }
        ]

    def get_userstore_groups(self):
        return [
            {
                'name': 'cfy_admins',
                'roles': ['administrator']
            },
            {
                'name': 'managers',
                'roles': ['deployer', 'viewer']
            },
            {
                'name': 'users',
                'roles': []
            }
        ]

    def get_userstore_driver(self):
        return {
            'implementation':
                'flask_securest.userstores.simple:SimpleUserstore',
            'properties': {
                'userstore': {
                    'users': self.get_userstore_users(),
                    'groups': self.get_userstore_groups()
                }
            }
        }
