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

import shutil

from cloudify_rest_client.client import CloudifyClient
from cloudify_rest_client.exceptions import CloudifyClientError

from cosmo_tester.test_suites.test_security.security_test_base import \
    SecurityTestBase, SECURITY_PROP_PATH
from cosmo_tester.framework import util


CUSTOM_AUTH_PROVIDER_PLUGIN = 'mock-auth-provider-with-no-userstore'
PLUGINS_PROP_PATH = 'node_templates.manager.properties.cloudify.plugins'


class NoUserstoreTests(SecurityTestBase):

    def test_authentication_without_userstore(self):
        self.setup_secured_manager()
        self._assert_unauthorized_user_fails()

    def get_manager_blueprint_additional_props_override(self):
        src_plugin_dir = util.get_plugin_path(CUSTOM_AUTH_PROVIDER_PLUGIN)
        shutil.copytree(src_plugin_dir,
                        self.test_manager_blueprint_path.dirname() /
                        CUSTOM_AUTH_PROVIDER_PLUGIN)
        return {PLUGINS_PROP_PATH: self.get_plugins_settings()}

    def get_plugins_settings(self):
        return {
            'user_custom_auth_provider': {
                'source': CUSTOM_AUTH_PROVIDER_PLUGIN
            }
        }

    def get_authentication_providers(self):
        return [
            {
                'implementation': 'mock_auth_provider_with_no_userstore'
                                  '.auth_without_userstore:AuthorizeUser1',
                'name': 'password',
                'properties': {
                    'dummy_param': 'dumdum'
                }
            }
        ]

    def get_security_settings(self):
        settings = {
            SECURITY_PROP_PATH + '.enabled': self.get_enabled(),
        }

        authentication_providers = self.get_authentication_providers()
        if authentication_providers:
            settings[SECURITY_PROP_PATH + '.authentication_providers'] = \
                authentication_providers

        settings[SECURITY_PROP_PATH + '.userstore_driver'] = ''

        return settings

    def _assert_unauthorized_user_fails(self):
        client = CloudifyClient(host=self.env.management_ip,
                                headers=util.get_auth_header(
                                    username='wrong_user',
                                    password='wrong_pass'))
        self.assertRaisesRegexp(CloudifyClientError, '401: user unauthorized',
                                client.manager.get_status)
