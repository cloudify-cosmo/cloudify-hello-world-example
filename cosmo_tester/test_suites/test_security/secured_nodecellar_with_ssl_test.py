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
from cloudify_cli import constants
from cloudify_rest_client import CloudifyClient
from cosmo_tester.framework import util
from cosmo_tester.test_suites.test_blueprints.nodecellar_test import \
    OpenStackNodeCellarTestBase
from cosmo_tester.test_suites.test_security.security_test_base import \
    SecurityTestBase, TEST_CFY_USERNAME, TEST_CFY_PASSWORD


class SecuredWithSSLOpenstackNodecellarTest(OpenStackNodeCellarTestBase,
                                            SecurityTestBase):

    def test_secured_openstack_nodecellar_with_ssl_without_cert(self):
        os.environ[constants.CLOUDIFY_SSL_TRUST_ALL] = 'trust'
        self.setup_secured_manager()
        self._test_openstack_nodecellar('openstack-blueprint.yaml')

    def set_rest_client(self):
        self.client = CloudifyClient(
            host=self.env.management_ip,
            port=constants.SECURED_REST_PORT,
            protocol=constants.SECURED_PROTOCOL,
            headers=util.get_auth_header(username=TEST_CFY_USERNAME,
                                         password=TEST_CFY_PASSWORD),
            trust_all=True)

    def get_ssl_enabled(self):
        return True

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
                        },
                        'user2': {
                            'username': 'user2',
                            'password': 'pass2',
                            'email': 'user2@domain.dom'
                        },
                        'user3': {
                            'username': 'user3',
                            'password': 'pass3',
                            'email': 'user3@domain.dom'
                        },
                        },
                    'identifying_attribute': 'username'
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
                }
            ],
            'ssl': {
                constants.SLL_ENABLED_PROPERTY_NAME: self.get_ssl_enabled(),
                constants.CERTIFICATE_PATH_PROPERTY_NAME: self.get_cert_path(),
                constants.PRIVATE_KEY_PROPERTY_NAME: self.get_key_path()
            }
        }

    def get_cert_path(self):
        return util.get_resource_path('ssl/server.crt')

    def get_key_path(self):
        return util.get_resource_path('ssl/server.key')

    def create_floating_ip(self):
        _, neutron, _ = self.env.handler.openstack_clients()
        ext_network_id = [
            n for n in neutron.list_networks()['networks']
            if n['name'] == self.env.external_network_name][0]['id']

        floating_ip = neutron.create_floatingip({
            'floatingip': {'floating_network_id': ext_network_id}
        })['floatingip']
        return floating_ip['floating_ip_address']

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
