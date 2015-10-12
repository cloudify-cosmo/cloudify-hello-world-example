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
    SSLTestBase
from cosmo_tester.test_suites.test_security.security_test_base import \
    TEST_CFY_USERNAME, TEST_CFY_PASSWORD

USE_EXISTING_FLOATING_IP_INPUT_PROP = 'inputs.use_existing_floating_ip'
USE_EXISTING_FLOATING_IP_INPUT = 'use_existing_floating_ip'
FLOATING_IP_INPUT_PROP = 'inputs.floating_ip'
FLOATING_IP_INPUT = 'floating_ip'

USE_EXTERNAL_RESOURCE_PROPERTY = \
    'node_templates.manager_server_ip.properties.use_external_resource'
RESOURCE_ID_PROPERTY = \
    'node_templates.manager_server_ip.properties.resource_id'


class SecuredWithSSLManagerTests(OpenStackNodeCellarTestBase,
                                 SSLTestBase):

    def get_manager_blueprint_additional_props_override(self):
        return {
            USE_EXISTING_FLOATING_IP_INPUT_PROP: {
                'default': True,
                'type': 'boolean'
            },
            FLOATING_IP_INPUT_PROP: {
                'default': self.floating_ip,
                'type': 'string'
            },
            USE_EXTERNAL_RESOURCE_PROPERTY: {
                'get_input': USE_EXISTING_FLOATING_IP_INPUT
            },
            RESOURCE_ID_PROPERTY: {
                'get_input': FLOATING_IP_INPUT
            }
        }

    def test_secured_manager_with_certificate(self):
        # setup and bootstrap manager with ssl enabled configured
        self.setup_secured_manager()
        # send request and verify certificate
        self._test_verify_cert()
        # send request without certificate verification
        self._test_no_verify_cert()
        # send request that is missing a certificate
        self._test_verify_missing_cert()
        # send request with wrong certificate
        self._test_verify_wrong_cert()
        # send request to non secured port
        # test commented out until functionality fixed
        # self._test_try_to_connect_to_manager_on_non_secured_port()
        # test nodecellar without certificate verification
        os.environ[constants.CLOUDIFY_SSL_TRUST_ALL] = 'true'
        self._test_openstack_nodecellar('openstack-blueprint.yaml')

    def _handle_ssl_files(self):
        ssl_dir = os.path.join(self.workdir, 'manager-blueprint/resources/ssl')
        if not os.path.isdir(ssl_dir):
            os.mkdir(ssl_dir)
        self.cert_path = os.path.join(ssl_dir, 'server.crt')
        self.key_path = os.path.join(ssl_dir, 'server.key')
        # create floating ip
        self.floating_ip = self.create_floating_ip()
        # create certificate with the ip intended to be used for this manager
        SSLTestBase.create_self_signed_certificate(
            target_certificate_path=self.cert_path,
            target_key_path=self.key_path,
            common_name=self.floating_ip)

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
        cert_path = os.path.join(self.workdir, 'wrong.cert')
        key_path = os.path.join(self.workdir, 'wrong.key')
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
