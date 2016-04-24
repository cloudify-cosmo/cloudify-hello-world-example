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

import sh
import os
from path import path

from cloudify_rest_client.client import CloudifyClient
from cosmo_tester.framework import util

from cosmo_tester.framework.testenv import TestCase


class BrokerSecurityTestBase(TestCase):

    def setup_manager_with_secured_broker(self):
        self._copy_manager_blueprint()
        self._handle_ssl_files()
        self._update_manager_blueprint()
        self._bootstrap()
        self._running_env_setup()

    def _handle_ssl_files(self):
        ssl_dir = os.path.join(self.workdir, 'broker_ssl_test')
        if not os.path.isdir(ssl_dir):
            os.mkdir(ssl_dir)
        self.cert_path = os.path.join(ssl_dir, 'broker.crt')
        self.key_path = os.path.join(ssl_dir, 'broker.key')
        self.wrong_cert_path = os.path.join(ssl_dir, 'invalid.crt')
        self.wrong_key_path = os.path.join(ssl_dir, 'invalid.key')
        # create floating ip
        self.floating_ip = self.create_floating_ip()
        # create certificate with the ip intended to be used for this manager
        self.create_self_signed_certificate(
            target_certificate_path=self.cert_path,
            target_key_path=self.key_path,
            common_name=self.floating_ip,
        )

        # create invalid certificate to test that invalid certs aren't allowed
        self.create_self_signed_certificate(
            target_certificate_path=self.wrong_cert_path,
            target_key_path=self.wrong_key_path,
            common_name='invalid',
        )

    def _copy_manager_blueprint(self):
        inputs_path, mb_path = util.generate_unique_configurations(
            workdir=self.workdir,
            original_inputs_path=self.env.cloudify_config_path,
            original_manager_blueprint_path=self.env._manager_blueprint_path)
        self.test_manager_blueprint_path = path(mb_path)
        self.test_inputs_path = path(inputs_path)
        self.test_manager_types_path = os.path.join(
            self.workdir, 'manager-blueprint/types/manager-types.yaml')

    def _update_manager_blueprint(self):
        props = self.get_manager_blueprint_additional_props_override()
        with util.YamlPatcher(self.test_manager_blueprint_path) as patch:
            for key, value in props.items():
                patch.set_value(key, value)

    def get_manager_blueprint_additional_props_override(self):
        return {}

    def _bootstrap(self):
        self.addCleanup(self.cfy.teardown)
        self.cfy.bootstrap(blueprint_path=self.test_manager_blueprint_path,
                           inputs_file=self.test_inputs_path,
                           task_retries=5,
                           install_plugins=self.env.install_plugins)

    def set_rest_client(self):
        self.client = CloudifyClient(
            host=self.env.management_ip)

    def _running_env_setup(self):
        def clean_mgmt_ip():
            self.env.management_ip = None
        self.addCleanup(clean_mgmt_ip)
        self.env.management_ip = self.cfy.get_management_ip()
        self.set_rest_client()

        response = self.client.manager.get_status()
        if not response['status'] == 'running':
            raise RuntimeError('Manager at {0} is not running.'
                               .format(self.env.management_ip))

    @staticmethod
    def create_self_signed_certificate(target_certificate_path,
                                       target_key_path,
                                       common_name):
        openssl = util.sh_bake(sh.openssl)
        # Includes SAN to allow this cert to be valid for localhost (by name),
        # 127.0.0.1 (IP), and including the CN in the IP list, as some clients
        # ignore the CN when SAN is present. While this may only apply to
        # HTTPS (RFC 2818), including it here is probably best in case of SSL
        # library implementation 'fun'.
        openssl.req(
            '-x509', '-newkey', 'rsa:2048', '-sha256',
            '-keyout', target_key_path,
            '-out', target_certificate_path,
            '-days', '365', '-nodes',
            '-subj',
            '/CN={ip} '
            '/subjectAltName=IP:127.0.0.1,DNS:localhost,IP:{ip}'.format(
                ip=common_name,
            ),
        ).wait()

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
