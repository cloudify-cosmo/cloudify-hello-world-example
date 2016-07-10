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
import subprocess
from requests.exceptions import SSLError

from cloudify_cli import constants
from cloudify_rest_client import CloudifyClient

from cosmo_tester.framework import util
from cosmo_tester.framework.util import YamlPatcher
from cosmo_tester.test_suites.test_blueprints.nodecellar_test import \
    OpenStackNodeCellarTestBase
from cosmo_tester.test_suites.test_security.security_ssl_test_base import \
    SSLTestBase

USE_EXISTING_FLOATING_IP_INPUT_PROP = 'inputs.use_existing_floating_ip'
USE_EXISTING_FLOATING_IP_INPUT = 'use_existing_floating_ip'
FLOATING_IP_INPUT_PROP = 'inputs.floating_ip'
FLOATING_IP_INPUT = 'floating_ip'
MANAGER_SERVER_NAME_INPUT = 'manager_server_name'

USE_EXTERNAL_RESOURCE_PROPERTY = \
    'node_templates.manager_server_ip.properties.use_external_resource'
RESOURCE_ID_PROPERTY = \
    'node_templates.manager_server_ip.properties.resource_id'
PUBLIC_IP_PROPERTY = \
    'node_templates.manager_configuration.relationships[0].' \
    'target_interfaces.cloudify\.interfaces\.relationship_lifecycle.' \
    'postconfigure.inputs.public_ip'


class SecuredSSLVerifyUserHostnameCertOpenstackNodecellarTest(
      OpenStackNodeCellarTestBase, SSLTestBase):

    @staticmethod
    def _get_user_data_etc_hosts_text(ip_address, hostname):
        return """#!/bin/bash -ex grep -q "{1}" /etc/hosts ||
        echo "{0} {1}" >> /etc/hosts"""\
            .format(ip_address, hostname)

    @staticmethod
    def _get_etc_hosts_update_text(ip_address, hostname):
        return """grep -q "{1}" /etc/hosts || echo "{0} {1}" |
        sudo tee -a /etc/hosts"""\
            .format(ip_address, hostname)

    @staticmethod
    def run_command(command):
        proc = subprocess.Popen(command, stdout=subprocess.PIPE, shell=True)
        return proc.communicate()

    def test_secured_ssl_verify_user_hostname_cert_openstack_nodecellar(self):
        self.setup_secured_manager()
        self._test_openstack_nodecellar('openstack-blueprint.yaml')

    def modify_blueprint(self):
        rest_host_name = 'rest_host'
        rest_private_ip = self.env.cloudify_config['manager_server_name']
        userdata = self._get_user_data_etc_hosts_text(rest_private_ip,
                                                      rest_host_name)
        with YamlPatcher(self.blueprint_yaml) as blueprint:
            for node_name in ('mongod_host', 'nodejs_host'):
                host = blueprint.obj['node_templates'][node_name]
                server_props = host['properties']['server']
                server_props['userdata'] = userdata
            self.logger.warning('modified blueprint: {0}\n'.format(blueprint))

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
            },
            PUBLIC_IP_PROPERTY: {
                'get_input': MANAGER_SERVER_NAME_INPUT
            }
        }

    def get_manager_blueprint_inputs_override(self):
        inputs = \
            super(SecuredSSLVerifyUserHostnameCertOpenstackNodecellarTest,
                  self).get_manager_blueprint_inputs_override()
        inputs['agent_verify_rest_certificate'] = True
        inputs['rest_host_internal_endpoint_type'] = 'public_ip'
        inputs['rest_host_external_endpoint_type'] = 'public_ip'
        return inputs

    def _handle_ssl_files(self):
        ssl_dir = os.path.join(self.workdir, 'manager-blueprint/resources/ssl')
        if not os.path.isdir(ssl_dir):
            os.mkdir(ssl_dir)
        self.cert_path = os.path.join(ssl_dir, 'external_rest_host.crt')
        self.key_path = os.path.join(ssl_dir, 'external_rest_host.key')
        self.floating_ip = self.create_floating_ip()
        self.server_host_name = 'noak-cloudify-manager'
        command = self._get_etc_hosts_update_text(self.floating_ip,
                                                  self.server_host_name)
        print 'running command {0}'.format(command)
        (out, err) = self.run_command(command)
        if out:
            print 'command output: {0}'.format(out)
        if err:
            print 'command error: {0}'.format(err)

        # create certificate with the ip intended to be used for this manager
        SSLTestBase.create_self_signed_certificate(
            target_certificate_path=self.cert_path,
            target_key_path=self.key_path,
            common_name=self.server_host_name)

    def _test_try_to_connect_to_manager_on_non_secured_port(self):
        client = CloudifyClient(
            host=self.env.management_ip,
            port=constants.DEFAULT_REST_PORT,
            protocol=constants.DEFAULT_PROTOCOL,
            headers=util.get_auth_header(username=self.TEST_CFY_USERNAME,
                                         password=self.TEST_CFY_PASSWORD),
            cert=self.cert_path,
            trust_all=False)

        response = client.manager.get_status()
        if not response['status'] == 'running':
            raise RuntimeError('Failed to get server status from {0}://{1}:{2}'
                               .format(constants.DEFAULT_PROTOCOL,
                                       self.env.management_ip,
                                       constants.DEFAULT_REST_PORT))

    def _test_no_verify_cert(self):
        client = CloudifyClient(
            host=self.env.management_ip,
            port=constants.SECURED_REST_PORT,
            protocol=constants.SECURED_PROTOCOL,
            headers=util.get_auth_header(username=self.TEST_CFY_USERNAME,
                                         password=self.TEST_CFY_PASSWORD),
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
            headers=util.get_auth_header(username=self.TEST_CFY_USERNAME,
                                         password=self.TEST_CFY_PASSWORD),
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
            headers=util.get_auth_header(username=self.TEST_CFY_USERNAME,
                                         password=self.TEST_CFY_PASSWORD),
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
            headers=util.get_auth_header(username=self.TEST_CFY_USERNAME,
                                         password=self.TEST_CFY_PASSWORD),
            cert=self.cert_path,
            trust_all=False)

        response = client.manager.get_status()
        if not response['status'] == 'running':
            raise RuntimeError('Manager at {0} is not running.'
                               .format(self.env.management_ip))
