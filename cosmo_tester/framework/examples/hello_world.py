########
# Copyright (c) 2017 GigaSpaces Technologies Ltd. All rights reserved
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

import re

from fabric import api as fabric_api
from fabric import context_managers as fabric_context_managers
import pytest
import requests
from retrying import retry

from cosmo_tester.framework.util import (
    is_community,
    prepare_and_get_test_tenant,
)

from . import AbstractExample


class HelloWorldExample(AbstractExample):

    REPOSITORY_URL = 'https://github.com/cloudify-cosmo/cloudify-hello-world-example.git'  # noqa

    def __init__(self, *args, **kwargs):
        super(HelloWorldExample, self).__init__(*args, **kwargs)
        self.disable_iptables = False

    @property
    def inputs(self):
        if not self._inputs:
            if 'openstack' in self._blueprint_file:
                self._inputs = {
                    'floating_network_id': self.attributes.floating_network_id,
                    'key_pair_name': self.attributes.keypair_name,
                    'private_key_path': self.manager.remote_private_key_path,
                    'flavor': self.attributes.small_flavor_name,
                    'network_name': self.attributes.network_name
                }
            elif self._blueprint_file == 'singlehost-blueprint.yaml':
                self._inputs = {
                    'server_ip': self.manager.ip_address,
                    'agent_user': self.attributes.default_linux_username,
                    'agent_private_key_path':
                        self.manager.remote_private_key_path,
                }
            else:
                self._inputs = {}
        return self._inputs

    def verify_installation(self):
        super(HelloWorldExample, self).verify_installation()
        http_endpoint = self.outputs['http_endpoint']
        if self.disable_iptables:
            self._disable_iptables(http_endpoint)
        self.assert_webserver_running(http_endpoint)

    @retry(stop_max_attempt_number=3, wait_fixed=10000)
    def _disable_iptables(self, http_endpoint):
        self.logger.info('Disabling iptables on hello world vm..')
        ip = re.findall(r'[0-9]+(?:\.[0-9]+){3}', http_endpoint)[0]
        self.logger.info('Hello world vm IP address is: %s', ip)
        with fabric_context_managers.settings(
                host_string=ip,
                user=self.inputs['agent_user'],
                key_filename=self._ssh_key.private_key_path,
                connections_attempts=3,
                abort_on_prompts=True):
            fabric_api.sudo('sudo service iptables save')
            fabric_api.sudo('sudo service iptables stop')
            fabric_api.sudo('sudo chkconfig iptables off')

    @retry(stop_max_attempt_number=10, wait_fixed=5000)
    def assert_webserver_running(self, http_endpoint):
        self.logger.info(
                'Verifying web server is running on: {0}'.format(
                        http_endpoint))
        server_response = requests.get(http_endpoint, timeout=15)
        if server_response.status_code != 200:
            pytest.fail('Unexpected status code: {}'.format(
                    server_response.status_code))

    def run_cfy_install_command(self):
        self.clone_example()
        blueprint_file = self._cloned_to / self.blueprint_file
        inputs = self._create_inputs_file()
        self.logger.info(
            'Running command:'
            ' cfy install -b {0} -n {1} -d {2} -i {3} -t {4} {5}'.format(
                self.blueprint_id,
                self.blueprint_file,
                self.deployment_id,
                inputs,
                self.tenant,
                blueprint_file
            ))

        self.cfy.install(['-b', self.blueprint_id,
                          '-n', self.blueprint_file,
                          '-d', self.deployment_id,
                          '-i', inputs,
                          '-t', self.tenant,
                          blueprint_file])

    def run_cfy_uninstall_command(self):
        self.cfy.uninstall(['-t', self.tenant,
                            self.deployment_id])

    def _create_inputs_file(self):
        path = self._cloned_to / 'inputs'
        with open(path, 'w+') as f:
            for key in self.inputs:
                f.write('{0}: {1}\n'.format(key, self.inputs[key]))
        return path


def centos_hello_world(cfy, manager, attributes, ssh_key, logger, tmpdir,
                       tenant='default_tenant', suffix=''):
    hello = HelloWorldExample(
        cfy, manager, attributes, ssh_key, logger, tmpdir,
        tenant=tenant, suffix=suffix)
    hello.blueprint_file = 'openstack-blueprint.yaml'
    hello.inputs.update({
        'agent_user': attributes.centos_7_username,
        'image': attributes.centos_7_image_name,
    })
    return hello


@pytest.fixture(scope='function')
def hello_worlds(cfy, manager, attributes, ssh_key, tmpdir,
                 logger):
    hellos = get_hello_worlds(cfy, manager, attributes, ssh_key, tmpdir,
                              logger)
    yield hellos
    for hello in hellos:
        hello.cleanup()


def get_hello_worlds(cfy, manager, attributes, ssh_key, tmpdir, logger):
    if is_community():
        tenants = ['default_tenant']
    else:
        tenants = [
            prepare_and_get_test_tenant(name, manager, cfy)
            for name in ('hello1', 'hello2')
        ]
    hellos = []
    for tenant in tenants:
        hello = centos_hello_world(cfy, manager, attributes, ssh_key,
                                   logger, tmpdir, tenant, suffix=tenant)
        hellos.append(hello)
    return hellos
