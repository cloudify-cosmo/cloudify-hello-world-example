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

from cosmo_tester.test_suites.test_security import auth_test_base


class AuthenticationWithoutAuthorizationTest(auth_test_base.BaseAuthTest):

    # overriding super's credentials
    TEST_CFY_USERNAME = 'alice'
    TEST_CFY_PASSWORD = 'alice_password'

    def setUp(self):
        super(AuthenticationWithoutAuthorizationTest, self).setUp()
        self.setup_secured_manager()

    def test_authentication_without_authorization(self):
        self._test_authentication(assert_token=True)

    ######################################
    # override default security settings
    ######################################
    def get_userstore_users(self):
        return [
            {
                'username': self.TEST_CFY_USERNAME,
                'password': self.TEST_CFY_PASSWORD
            }
        ]

    def get_userstore_driver(self):
        return {
            'implementation':
                'flask_securest.userstores.simple:SimpleUserstore',
            'properties': {
                'userstore': {
                    'users': self.get_userstore_users()
                }
            }
        }

    def get_authorization_provider(self):
        return ''
