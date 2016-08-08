########
# Copyright (c) 2016 GigaSpaces Technologies Ltd. All rights reserved
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

from cosmo_tester.test_suites.test_security.security_ssl_test_base import \
    SSLTestBase, openssl
from cosmo_tester.test_suites.test_blueprints.hello_world_bash_test import \
    clone_hello_world
from cosmo_tester.framework.util import YamlPatcher

agent_prop_path = \
    'node_templates.vm.properties.cloudify_agent.agent_rest_cert_path'
broker_prop_path = \
    'node_templates.vm.properties.cloudify_agent.broker_ssl_cert_path'


class CertsLocationTestBase(SSLTestBase):

    def prepare_app(self, blueprint_overrides=None):
        self.setup_secured_manager()

        inputs = {
            'agent_user': 'centos',
            'server_ip': '127.0.0.1',
            'agent_private_key_path': '/root/.ssh/agent_key.pem'
        }

        self.repo_dir = clone_hello_world(self.workdir)
        self.blueprint_yaml = self.repo_dir / 'singlehost-blueprint.yaml'

        if blueprint_overrides:
            with YamlPatcher(self.blueprint_yaml) as patch:
                for k, v in blueprint_overrides:
                    patch.set_value(k, v)

        self.upload_deploy_and_execute_install(
            fetch_state=False,
            inputs=inputs)

    def _handle_ssl_files(self):
        ssl_dir = os.path.join(self.workdir, 'broker-cert')
        if not os.path.isdir(ssl_dir):
            os.mkdir(ssl_dir)
        cert_path = os.path.join(ssl_dir, 'broker.crt')
        key_path = os.path.join(ssl_dir, 'broker.key')

        openssl.req(
            '-x509', '-newkey', 'rsa:2048',
            '-keyout', key_path,
            '-out', cert_path,
            '-days', '365', '-nodes',
            '-subj', '/').wait()

        cert_content = open(cert_path, 'r').read()
        key_content = open(key_path, 'r').read()

        with YamlPatcher(self.test_inputs_path) as patch:
            patch.set_value('rabbitmq_cert_public', cert_content)
            patch.set_value('rabbitmq_cert_private', key_content)

    def check_if_exists(self, path):
        with self.manager_env_fabric() as api:
            api.run('cat {0}'.format(path))


class CloudifyAgentCertsLocationTest(CertsLocationTestBase):

    def test_certs_location_default(self):
        self.prepare_app()
        self.check_if_exists('~/.cloudify/certs/rest.crt')
        self.check_if_exists('~/.cloudify/certs/broker.crt')

    def test_certs_location_absolute(self):
        rest_path = '/home/centos/MyRest.cert'
        broker_path = '/home/centos/asd/MyBroker.cert'
        self.prepare_app([(agent_prop_path, rest_path),
                          (broker_prop_path, broker_path)])
        self.check_if_exists(rest_path)
        self.check_if_exists(broker_path)

    def test_certs_location_relative(self):
        rest_path = '~/MyRest2.cert'
        broker_path = '~/some_dir/asd/MyBroker2.cert'
        self.prepare_app([(agent_prop_path, rest_path),
                          (broker_prop_path, broker_path)])
        self.check_if_exists(rest_path)
        self.check_if_exists(broker_path)


class ManagerInputsCertsLocationTest(CertsLocationTestBase):

    def setUp(self):
        super(ManagerInputsCertsLocationTest, self).setUp()
        self.manager_inputs_overrides = {}

    def get_manager_blueprint_inputs_override(self):
        orig = super(ManagerInputsCertsLocationTest, self)\
            .get_manager_blueprint_inputs_override()
        orig.update(self.manager_inputs_overrides)
        return orig

    def test_certs_location_from_manager_inputs(self):
        rest_path = '~/asd/MyRest3.cert'
        broker_path = '/home/centos/MyBroker3.cert'

        self.manager_inputs_overrides = {
            'agent_rest_cert_path': rest_path,
            'broker_ssl_cert_path': broker_path
        }

        self.prepare_app()
        self.check_if_exists(rest_path)
        self.check_if_exists(broker_path)
