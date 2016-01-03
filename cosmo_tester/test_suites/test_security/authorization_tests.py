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
from cosmo_tester.test_suites.test_security import security_test_base

security_test_base.TEST_CFY_USERNAME = 'alice'
security_test_base.TEST_CFY_PASSWORD = 'alice_password'


class AuthorizationTests(auth_test_base.BaseAuthTest):

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
                'username': auth_test_base.ADMIN_USERNAME,
                'password': auth_test_base.ADMIN_PASSWORD,
                'groups': ['cfy_admins']
            },
            {
                'username': auth_test_base.DEPLOYER_USERNAME,
                'password': auth_test_base.DEPLOYER_PASSWORD,
                'groups': ['managers', 'users']
            },
            {
                'username': auth_test_base.VIEWER_USERNAME,
                'password': auth_test_base.VIEWER_PASSWORD,
                'groups': ['users'],
                'roles': ['viewer']
            },
            {
                'username': auth_test_base.NO_ROLE_USERNAME,
                'password': auth_test_base.NO_ROLE_PASSWORD,
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
