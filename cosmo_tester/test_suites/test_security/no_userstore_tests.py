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
import shutil

from cloudify_cli import constants
from cloudify_rest_client.client import CloudifyClient
from cloudify_rest_client.exceptions import UserUnauthorizedError

from cosmo_tester.test_suites.test_security import security_test_base
from cosmo_tester.framework import util


CUSTOM_AUTH_PROVIDER_PLUGIN = 'mock-auth-provider-with-no-userstore'


class NoUserstoreTests(security_test_base.SecurityTestBase):

    TEST_CFY_USERNAME = 'not_the_default_username'
    TEST_CFY_PASSWORD = 'something'

    def setUp(self):
        super(NoUserstoreTests, self).setUp()
        self.setup_secured_manager()

    def test_authentication_without_userstore(self):
        self._assert_unauthorized_user_fails()

    def _update_manager_blueprint(self):
        super(NoUserstoreTests, self)._update_manager_blueprint()

        # copying custom auth provider plugin
        src_plugin_dir = util.get_plugin_path(CUSTOM_AUTH_PROVIDER_PLUGIN)
        shutil.copytree(src_plugin_dir,
                        self.test_manager_blueprint_path.dirname() /
                        CUSTOM_AUTH_PROVIDER_PLUGIN)

    def get_rest_plugins(self):
        return {
            'user_custom_auth_provider': {
                'source': CUSTOM_AUTH_PROVIDER_PLUGIN
            }
        }

    def get_authentication_providers(self):
        return [
            {
                'implementation': 'mock_auth_provider_with_no_userstore'
                                  '.auth_without_userstore:'
                                  'AuthorizeUserByUsername',
                'name': 'Authorize_By_Username',
                'properties': {}
            }
        ]

    def get_userstore_driver(self):
        return ''

    def get_authorization_provider(self):
        return ''

    def _assert_unauthorized_user_fails(self):
        client = CloudifyClient(host=self.env.management_ip,
                                headers=util.get_auth_header(
                                    username='wrong_username',
                                    password='something'))
        self.assertRaisesRegexp(UserUnauthorizedError,
                                '401: user unauthorized',
                                client.manager.get_status)

    def _set_credentials_env_vars(self):
        os.environ[constants.CLOUDIFY_USERNAME_ENV] = \
            'not_the_default_username'
        os.environ[constants.CLOUDIFY_PASSWORD_ENV] = 'something'
