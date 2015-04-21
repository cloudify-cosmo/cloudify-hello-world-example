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
from cloudify_rest_client.exceptions import CloudifyClientError

from cosmo_tester.framework import util
from cosmo_tester.test_suites.test_security.security_test_base import \
    SecurityTestBase


class TokenAuthenticationTest(SecurityTestBase):

    def test_secured_openstack_nodecellar(self):
        self.setup_secured_manager()
        self._assert_invalid_user_fails()
        self._assert_valid_token_authenticates()
        self._assert_invalid_token_fails()

    def get_security_settings(self):
        return {
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
                        }
                    },
                    'identifying_attribute': 'username'
                }
            },
            'auth_token_generator': {
                'implementation':
                    'flask_securest.authentication_providers.token:'
                    'TokenAuthenticator',
                'properties': {
                    'secret_key': 'my_secret',
                    'expires_in': 600
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
                },
                {
                    'name': 'token',
                    'implementation': 'flask_securest.'
                                      'authentication_providers.token:'
                                      'TokenAuthenticator',
                    'properties': {
                        'secret_key': 'my_secret'
                    }
                }
            ]
        }

    def _assert_invalid_user_fails(self):
        client = CloudifyClient(host=self.env.management_ip,
                                headers=util.get_auth_header(username='user1',
                                                             password='pass2'))
        self.assertRaisesRegexp(CloudifyClientError, '401: user unauthorized',
                                client.manager.get_status)

    def _assert_valid_token_authenticates(self):
        user_pass_header = util.get_auth_header(username='user1',
                                                password='pass1')
        client = CloudifyClient(host=self.env.management_ip,
                                headers=user_pass_header)

        token_header = util.get_auth_header(token=client.tokens.get().value)
        client = CloudifyClient(self.env.management_ip, headers=token_header)

        response = client.manager.get_status()
        if not response['status'] == 'running':
            raise RuntimeError('Failed to get manager status using token')

    def _assert_invalid_token_fails(self):
        token_header = util.get_auth_header(token='wrong_token')
        client = CloudifyClient(self.env.management_ip, headers=token_header)
        self.assertRaisesRegexp(CloudifyClientError, '401: user unauthorized',
                                client.manager.get_status)
