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

import logging
import pika
import socket
import ssl
import time

from cosmo_tester.test_suites.test_blueprints.nodecellar_test import \
    OpenStackNodeCellarTestBase
from cosmo_tester.test_suites.test_broker_security import (
    inputs,
    broker_security_test_base,
)

# Enable pika to state the nature of connection issues, and stop it
# complaining about missing loggers
logging.basicConfig()


BROKER_SSL_ENABLED_INPUT = 'inputs.rabbitmq_ssl_enabled'
BROKER_SSL_CERT_PUBLIC_INPUT = 'inputs.rabbitmq_cert_public'
BROKER_SSL_CERT_PRIVATE_INPUT = 'inputs.rabbitmq_cert_private'
BROKER_USERNAME_INPUT = 'inputs.rabbitmq_username'
BROKER_PASSWORD_INPUT = 'inputs.rabbitmq_password'
USE_EXISTING_FLOATING_IP_INPUT_PROP = 'inputs.use_existing_floating_ip'
USE_EXISTING_FLOATING_IP_INPUT = 'use_existing_floating_ip'
FLOATING_IP_INPUT_PROP = 'inputs.floating_ip'
FLOATING_IP_INPUT = 'floating_ip'
USE_EXTERNAL_RESOURCE_PROPERTY = \
    'node_templates.manager_server_ip.properties.use_external_resource'
RESOURCE_ID_PROPERTY = \
    'node_templates.manager_server_ip.properties.resource_id'


class SecuredBrokerManagerTests(
    OpenStackNodeCellarTestBase,
    broker_security_test_base.BrokerSecurityTestBase,
):

    def get_manager_blueprint_additional_props_override(self):
        self.broker_security_inputs = inputs.BrokerSecurity(
            cert_path=self.cert_path,
            key_path=self.key_path,
        )
        return {
            BROKER_SSL_ENABLED_INPUT: {
                'default': True,
                'type': 'boolean'
            },
            BROKER_SSL_CERT_PUBLIC_INPUT: {
                'default': self.broker_security_inputs.public_cert,
                'type': 'string'
            },
            BROKER_SSL_CERT_PRIVATE_INPUT: {
                'default': self.broker_security_inputs.private_key,
                'type': 'string'
            },
            BROKER_USERNAME_INPUT: {
                'default': self.broker_security_inputs.username,
                'type': 'string'
            },
            BROKER_PASSWORD_INPUT: {
                'default': self.broker_security_inputs.password,
                'type': 'string'
            },
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
        }

    def test_secured_manager_with_certificate(self):
        # setup and bootstrap manager with broker security enabled
        self.setup_manager_with_secured_broker()

        # Permit access for the tests
        self._enable_external_testing_access()

        # send request and verify certificate
        self._test_verify_cert()
        # send request that is missing a certificate
        self._test_verify_missing_cert_fails()
        # send request with wrong certificate
        self._test_verify_wrong_cert_fails()
        # Check we can connect to the non secure port still
        # This is required until Riemann, Logstash, and the manager's diamond
        # can be made to work with tlsv1.2 and with a cert verification using
        # the pinned certificate
        self._test_non_secured_port_still_usable()

        # test nodecellar deployment
        self._test_openstack_nodecellar('openstack-blueprint.yaml')

    def _can_get_broker_connection(self,
                                   username,
                                   password,
                                   host,
                                   port=5672,
                                   cert_path='',
                                   ssl_enabled=False):
        conn_params = {
            'host': host,
            'port': port,
            'credentials': pika.credentials.PlainCredentials(
                username=username,
                password=password,
            ),
        }

        if ssl_enabled:
            ssl_params = {
                'ssl': ssl_enabled,
                'ssl_options': {
                    'ca_certs': cert_path,
                    'cert_reqs': ssl.CERT_REQUIRED,
                },
            }
            conn_params.update(ssl_params)

        conn_params = pika.ConnectionParameters(**conn_params)

        conn = pika.BlockingConnection(conn_params)
        return conn

    def _test_verify_cert(self):
        conn = self._can_get_broker_connection(
            username=self.broker_security_inputs.username,
            password=self.broker_security_inputs.password,
            host=self.floating_ip,
            port=5671,
            ssl_enabled=True,
            cert_path=self.cert_path,
        )
        # If we got a connection we can close it
        conn.close()

    def _test_verify_missing_cert_fails(self):
        try:
            self._can_get_broker_connection(
                username=self.broker_security_inputs.username,
                password=self.broker_security_inputs.password,
                host=self.floating_ip,
                port=5671,
                ssl_enabled=True,
                cert_path='',
            )
            self.fail('SSL connection should fail without cert')
        except pika.exceptions.AMQPConnectionError as err:
            self.assertIn(
                'error:0B084002:x509 certificate routines',
                str(err.message),
            )

    def _test_verify_wrong_cert_fails(self):
        try:
            self._can_get_broker_connection(
                username=self.broker_security_inputs.username,
                password=self.broker_security_inputs.password,
                host=self.floating_ip,
                port=5671,
                ssl_enabled=True,
                cert_path=self.wrong_cert_path,
            )
            self.fail('SSL connection should fail with wrong cert')
        except pika.exceptions.AMQPConnectionError as err:
            self.assertIn(
                'certificate verify failed',
                str(err.message),
            )

    def _test_non_secured_port_still_usable(self):
        conn = self._can_get_broker_connection(
            username=self.broker_security_inputs.username,
            password=self.broker_security_inputs.password,
            host=self.floating_ip,
            port=5672,
            ssl_enabled=False,
            cert_path='',
        )
        # If we got a connection we can close it
        conn.close()

    def _allow_port_on_security_group(self, group_id, port, proto='tcp'):
        nova, neutron, cinder = self.env.handler.openstack_clients()

        nova.security_group_rules.create(
            parent_group_id=group_id,
            from_port=port,
            to_port=port,
            ip_protocol=proto,
        )
        # Don't continue until the rule is actually active
        for attempt in range(1, 4):
            try:
                socket.create_connection((
                    self.floating_ip,
                    port
                ))
            except socket.error:
                # Port is not yet active
                if attempt == 3:
                    # Maximum attempts reached, something is probably wrong
                    raise
                else:
                    # Try again soon
                    time.sleep(3)

    def _enable_external_testing_access(self):
        nova, neutron, cinder = self.env.handler.openstack_clients()

        # Get the manager security group
        manager_sec_group = self.env.cloudify_config[
            'manager_security_group_name']
        group_id = nova.security_groups.find(name=manager_sec_group).id

        # Allow rabbitmq access for security tests (5671,5672)
        # Allow influxdb access to test monitoring for nodecellar (8086)
        # Access through 8086 is already available.. (sys tests framework).
        for port in (5671, 5672):
            self._allow_port_on_security_group(
                group_id=group_id,
                port=port,
            )
