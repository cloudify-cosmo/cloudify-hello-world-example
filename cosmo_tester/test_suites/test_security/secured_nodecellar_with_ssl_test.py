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
from requests.exceptions import SSLError, ConnectionError
from cloudify_cli import constants
from cloudify_rest_client import CloudifyClient

from cosmo_tester.framework import util
from cosmo_tester.test_suites.test_blueprints.nodecellar_test import \
    OpenStackNodeCellarTestBase
from cosmo_tester.test_suites.test_security.security_ssl_test_base import \
    SSLTests
from cosmo_tester.test_suites.test_security.security_test_base import \
    TEST_CFY_USERNAME, TEST_CFY_PASSWORD


class SecuredWithSSLManagerTests(OpenStackNodeCellarTestBase,
                                 SSLTests):

    def _update_manager_blueprint(self, props):
        props['inputs.use_existing_floating_ip'] = {
            'default': 'true',
            'type': 'boolean'
        }
        props['inputs.floating_ip_id'] = {
            'default': self.floating_ip_id,
            'type': 'string'
        }
        props[
            'node_templates.manager_server_ip.properties.use_external_resource'] = \
            '{ get_input: use_existing_floating_ip }'
        props['node_templates.manager_server_ip.properties.resource_id'] = \
            '{ get_input: floating_ip_id }'

        super(SSLTests, self)._update_manager_blueprint(props)

    def test_ssl_manager(self):
        # setup and bootstrap manager with ssl enabled configured
        self._setup_secured_manager_with_ssl()
        # send request and verify certificate
        self._test_verify_cert()
        # send request without certificate verification
        self._test_no_verify_cert()
        # send request that is missing a certificate
        self._test_verify_missing_cert()
        # send request with wrong certificate
        self._test_verify_wrong_cert()
        # send request to non secured port
        self._test_try_to_connect_to_manager_on_non_secured_port()
        # test nodecellar without certificate verification
        os.environ[constants.CLOUDIFY_SSL_TRUST_ALL] = 'true'
        self._test_openstack_nodecellar('openstack-blueprint.yaml')

    def _setup_secured_manager_with_ssl(self):
        ssl_dir = os.path.join(self.workdir, 'ssl')
        os.mkdir(ssl_dir)
        self.cert_path = os.path.join(ssl_dir, 'server.cert')
        self.key_path = os.path.join(ssl_dir, 'server.key')

        # create floating ip
        floating_ip, floating_ip_id = self.create_floating_ip()
        self.floating_ip_id = floating_ip_id

        # create certificate with the ip intended to be used for this manager
        SSLTests.create_self_signed_certificate(
            target_certificate_path=self.cert_path,
            target_key_path=self.key_path,
            common_name=floating_ip)

        # bootstrap
        self.setup_secured_manager()

    def _test_try_to_connect_to_manager_on_non_secured_port(self):
        try:
            client = CloudifyClient(
                host=self.env.management_ip,
                port=constants.DEFAULT_REST_PORT,
                protocol=constants.DEFAULT_PROTOCOL,
                headers=util.get_auth_header(username=TEST_CFY_USERNAME,
                                             password=TEST_CFY_PASSWORD))
            client.manager.get_status()
            self.fail(
                'manager should not be available on port '
                .format(constants.DEFAULT_REST_PORT))
        except ConnectionError as e:
            self.assertIn('Connection refused', str(e.message))

    def _test_no_verify_cert(self):
        client = CloudifyClient(
            host=self.env.management_ip,
            port=constants.SECURED_REST_PORT,
            protocol=constants.SECURED_PROTOCOL,
            headers=util.get_auth_header(username=TEST_CFY_USERNAME,
                                         password=TEST_CFY_PASSWORD),
            trust_all=True)

        response = client.manager.get_status()
        if not response['status'] == 'running':
            raise RuntimeError('Manager at {0} is not running.'
                               .format(self.env.management_ip))

    def _test_verify_missing_cert(self):
        client = CloudifyClient(
            host=self.env.management_ip,
            port=constants.SECURED_REST_PORT,
            protocol=constants.SECURED_PROTOCOL,
            headers=util.get_auth_header(username=TEST_CFY_USERNAME,
                                         password=TEST_CFY_PASSWORD),
            trust_all=False)
        try:
            client.manager.get_status()
            self.fail('certification verification expected to fail')
        except SSLError as e:
            self.assertIn('certificate verify failed', str(e.message))

    def _test_verify_wrong_cert(self):
        cert_path = os.path.join(self.workdir, 'test.cert')
        key_path = os.path.join(self.workdir, 'test.key')
        self.create_self_signed_certificate(cert_path, key_path, 'test')
        client = CloudifyClient(
            host=self.env.management_ip,
            port=constants.SECURED_REST_PORT,
            protocol=constants.SECURED_PROTOCOL,
            headers=util.get_auth_header(username=TEST_CFY_USERNAME,
                                         password=TEST_CFY_PASSWORD),
            cert=util.get_resource_path(cert_path),
            trust_all=False)
        try:
            client.manager.get_status()
            self.fail('certification verification expected to fail')
        except SSLError as e:
            self.assertIn('certificate verify failed', str(e.message))

    def _test_verify_cert(self):
        client = CloudifyClient(
            host=self.env.management_ip,
            port=constants.SECURED_REST_PORT,
            protocol=constants.SECURED_PROTOCOL,
            headers=util.get_auth_header(username=TEST_CFY_USERNAME,
                                         password=TEST_CFY_PASSWORD),
            cert=self.cert_path,
            trust_all=False)

        response = client.manager.get_status()
        if not response['status'] == 'running':
            raise RuntimeError('Manager at {0} is not running.'
                               .format(self.env.management_ip))
