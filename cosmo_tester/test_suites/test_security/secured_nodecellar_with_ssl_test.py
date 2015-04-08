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
from cloudify_cli.constants import CLOUDIFY_SSL_CERT
from cloudify_cli.constants import CLOUDIFY_SSL_TRUST_ALL
from cloudify_rest_client import CloudifyClient
from cosmo_tester.framework import util
from cosmo_tester.test_suites.test_security import TEST_CFY_USERNAME, TEST_CFY_PASSWORD

from cosmo_tester.test_suites.test_security.secured_nodecellar_test import SecuredOpenstackNodecellarTest


class SecuredWithSSLOpenstackNodecellarTest(SecuredOpenstackNodecellarTest):

    def test_secured_openstack_nodecellar_with_ssl_without_cert(self):
        self.setup_secured_manager()
        self._test_openstack_nodecellar('openstack-blueprint.yaml')

    def _set_ssl_env_vars(self):
        os.environ[CLOUDIFY_SSL_CERT] = ''
        os.environ[CLOUDIFY_SSL_TRUST_ALL] = 'trust'

    def set_rest_client(self):
        self.env.port = 443
        self.client = CloudifyClient(
            host=self.env.management_ip,
            port=443,
            protocol='https',
            headers=util.get_auth_header(username=TEST_CFY_USERNAME,
                                         password=TEST_CFY_PASSWORD),
            cert=os.environ.get(CLOUDIFY_SSL_CERT),
            trust_all=os.environ.get(CLOUDIFY_SSL_TRUST_ALL))

    def get_security_settings(self):
        super(SecuredWithSSLOpenstackNodecellarTest, self).get_security_settings()