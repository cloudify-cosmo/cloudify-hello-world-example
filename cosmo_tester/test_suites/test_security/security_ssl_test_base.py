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
import sh

from cloudify_cli import constants
from cloudify_rest_client import CloudifyClient

from cosmo_tester.framework import util
from cosmo_tester.test_suites.test_security.security_test_base import \
    SecurityTestBase

openssl = util.sh_bake(sh.openssl)


class SSLTestBase(SecurityTestBase):

    def setUp(self):
        super(SSLTestBase, self).setUp()
        self.cert_path = ''
        self.key_path = ''

    def _set_credentials_env_vars(self):
        super(SSLTestBase, self)._set_credentials_env_vars()
        os.environ[constants.CLOUDIFY_SSL_TRUST_ALL] = 'true'

    def set_rest_client(self):
        self.client = CloudifyClient(
            host=self.env.management_ip,
            port=constants.SECURED_REST_PORT,
            protocol=constants.SECURED_PROTOCOL,
            headers=util.get_auth_header(username=self.TEST_CFY_USERNAME,
                                         password=self.TEST_CFY_PASSWORD),
            trust_all=True)

    # def _running_env_setup(self):
    #     self.env.management_ip = self.get_manager_ip()
    #     self.set_rest_client()

        def clean_mgmt_ip():
            self.env.management_ip = None
        self.addCleanup(clean_mgmt_ip)

    def is_ssl_enabled(self):
        return True

    def get_cert_path(self):
        return self.cert_path

    def get_key_path(self):
        return self.key_path

    def create_floating_ip(self):
        _, neutron, _ = self.env.handler.openstack_clients()

        ext_network_id = [
            n for n in neutron.list_networks()['networks']
            if n['name'] == self.env.external_network_name][0]['id']

        floating_ip = neutron.create_floatingip(
            {
                'floatingip': {'floating_network_id': ext_network_id}
            })['floatingip']

        return floating_ip['floating_ip_address']

    @staticmethod
    def create_self_signed_certificate(target_certificate_path,
                                       target_key_path,
                                       common_name):
        openssl.req(
            '-x509', '-newkey', 'rsa:2048',
            '-keyout', target_key_path,
            '-out', target_certificate_path,
            '-days', '365', '-nodes',
            '-subj', '/CN={0}'.format(common_name)).wait()
