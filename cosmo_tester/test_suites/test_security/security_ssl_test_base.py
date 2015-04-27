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

from cloudify_cli import constants
from cloudify_rest_client import CloudifyClient

from cosmo_tester.framework import util
from cosmo_tester.test_suites.test_security.security_test_base import \
    SecurityTestBase, TEST_CFY_USERNAME, TEST_CFY_PASSWORD


class SSLTests(SecurityTestBase):

    def setUp(self):
        super(SSLTests, self).setUp()
        self.cert_path = ''
        self.key_path = ''

    def set_rest_client(self):
        self.client = CloudifyClient(
            host=self.env.management_ip,
            port=constants.SECURED_REST_PORT,
            protocol=constants.SECURED_PROTOCOL,
            headers=util.get_auth_header(username=TEST_CFY_USERNAME,
                                         password=TEST_CFY_PASSWORD),
            trust_all=True)

    def _running_env_setup(self):
        self.env.management_ip = self.cfy.get_management_ip()
        self.set_rest_client()

        def clean_mgmt_ip():
            self.env.management_ip = None
        self.addCleanup(clean_mgmt_ip)

    def get_security_settings(self):
        security_settings_with_ssl = \
            super(SSLTests, self).get_security_settings()
        security_settings_with_ssl['ssl'] = {
            constants.SLL_ENABLED_PROPERTY_NAME: self.get_ssl_enabled(),
            constants.CERTIFICATE_PATH_PROPERTY_NAME: self.get_cert_path(),
            constants.PRIVATE_KEY_PROPERTY_NAME: self.get_key_path()
        }
        return security_settings_with_ssl

    def get_ssl_enabled(self):
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

        return floating_ip['floating_ip_address'], floating_ip['id']

    @staticmethod
    def create_self_signed_certificate(target_certificate_path,
                                       target_key_path,
                                       common_name):
        from OpenSSL import crypto
        from os import path

        key = crypto.PKey()
        key.generate_key(crypto.TYPE_RSA, 2048)
        certificate = crypto.X509()
        subject = certificate.get_subject()
        subject.commonName = common_name
        certificate.gmtime_adj_notBefore(0)
        certificate.gmtime_adj_notAfter(10 * 365 * 24 * 60 * 60)
        certificate.set_issuer(subject)
        certificate.set_pubkey(key)
        certificate.sign(key, 'SHA1')

        with open(path.expanduser(target_certificate_path), 'w') as f:
            f.write(crypto.dump_certificate(crypto.FILETYPE_PEM, certificate))
        with open(path.expanduser(target_key_path), 'w') as f:
            f.write(crypto.dump_privatekey(crypto.FILETYPE_PEM, key))
