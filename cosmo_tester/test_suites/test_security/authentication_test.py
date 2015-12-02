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

from cloudify_rest_client.client import CloudifyClient
from cloudify_rest_client.exceptions import UserUnauthorizedError

from cosmo_tester.framework import util
import cosmo_tester.test_suites.test_security.security_test_base as \
    security_test_base
from security_test_base import SecurityTestBase, SECURITY_PROP_PATH

security_test_base.TEST_CFY_USERNAME = 'alice'
security_test_base.TEST_CFY_PASSWORD = 'alice_password'


class AuthenticationWithoutAuthorizationTest(SecurityTestBase):

    def test_authentication_without_authorization(self):
        self.setup_secured_manager()
        self._assert_valid_credentials_authenticate()
        self._assert_invalid_credentials_fails()
        self._assert_empty_credentials_fails()
        self._assert_valid_token_authenticates()
        self._assert_invalid_token_fails()
        self._assert_empty_token_fails()
        self._assert_no_credentials_or_token_fails()

    def _assert_valid_credentials_authenticate(self):
        user_pass_header = util.get_auth_header(username='alice',
                                                password='alice_password')
        self.client = CloudifyClient(host=self.env.management_ip,
                                     headers=user_pass_header)
        self._assert_authorized()

    def _assert_invalid_credentials_fails(self):
        user_pass_header = util.get_auth_header(username='wrong_username',
                                                password='wrong_password')
        self.client = CloudifyClient(host=self.env.management_ip,
                                     headers=user_pass_header)
        self._assert_unauthorized()

    def _assert_empty_credentials_fails(self):
        user_pass_header = util.get_auth_header(username='',
                                                password='')
        self.client = CloudifyClient(host=self.env.management_ip,
                                     headers=user_pass_header)
        self._assert_unauthorized()

    def _assert_valid_token_authenticates(self):
        user_pass_header = util.get_auth_header(username='alice',
                                                password='alice_password')
        client = CloudifyClient(host=self.env.management_ip,
                                headers=user_pass_header)
        token_header = util.get_auth_header(token=client.tokens.get().value)
        self.client = CloudifyClient(self.env.management_ip,
                                     headers=token_header)
        self._assert_authorized()

    def _assert_invalid_token_fails(self):
        token_header = util.get_auth_header(token='wrong_token')
        self.client = CloudifyClient(self.env.management_ip,
                                     headers=token_header)
        self._assert_unauthorized()

    def _assert_empty_token_fails(self):
        token_header = util.get_auth_header(token='')
        self.client = CloudifyClient(host=self.env.management_ip,
                                     headers=token_header)
        self._assert_unauthorized()

    def _assert_no_credentials_or_token_fails(self):
        self.client = CloudifyClient(host=self.env.management_ip)
        self._assert_unauthorized()

    def get_security_settings(self):
        settings = {
            SECURITY_PROP_PATH + '.enabled': self.get_enabled(),
        }

        authentication_providers = self.get_authentication_providers()
        if authentication_providers:
            settings[SECURITY_PROP_PATH + '.authentication_providers'] = \
                authentication_providers

        settings[SECURITY_PROP_PATH + '.authorization_provider'] = ''
        userstore_drive = self.get_userstore_driver()
        if userstore_drive:
            settings[
                '{0}.userstore_driver'.format(SECURITY_PROP_PATH)] = \
                userstore_drive

        return settings

    def get_userstore_driver(self):
        return {
            'implementation':
                'flask_securest.userstores.simple:SimpleUserstore',
            'properties': {
                'userstore': {
                    'users': [
                        {
                            'username': 'alice',
                            'password': 'alice_password'
                        }
                    ]
                }
            }
        }

    def _assert_authorized(self):
        response = self.client.manager.get_status()
        if not response['status'] == 'running':
            raise RuntimeError('Failed to get manager status using username'
                               ' and password')

    def _assert_unauthorized(self):
        self.assertRaisesRegexp(UserUnauthorizedError,
                                '401: user unauthorized',
                                self.client.manager.get_status)
