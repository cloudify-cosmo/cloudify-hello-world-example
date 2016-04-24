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

from fabric import api as fabric_api

from cloudify.workflows import local
from cloudify_cli import constants as cli_constants
from cosmo_tester.framework.git_helper import clone
from cosmo_tester.framework.util import create_rest_client

MANAGER_BLUEPRINTS_REPO_URL = 'https://github.com/cloudify-cosmo/' \
                              'cloudify-manager-blueprints.git'


class AbstractSingleHostTest(object):

    def setup_simple_manager_env(self):
        blueprint_path = self.copy_blueprint('openstack-start-vm')
        self.blueprint_yaml = blueprint_path / 'blueprint.yaml'
        self.prefix = 'simple-host-{0}'.format(self.test_id)
        self.manager_blueprint_overrides = {}
        self.remote_manager_key_path = '/home/{0}/manager_key.pem'.format(
            self.env.centos_7_image_user)

        self.inputs = {
            'prefix': self.prefix,
            'external_network': self.env.external_network_name,
            'os_username': self.env.keystone_username,
            'os_password': self.env.keystone_password,
            'os_tenant_name': self.env.keystone_tenant_name,
            'os_region': self.env.region,
            'os_auth_url': self.env.keystone_url,
            'image_id': self.env.centos_7_image_name,
            'flavor': self.env.medium_flavor_id,
            'key_pair_path': '{0}/{1}-keypair.pem'.format(self.workdir,
                                                          self.prefix)
        }

        self.logger.info('initialize local env for running the '
                         'blueprint that starts a vm')
        self.local_env = local.init_env(
            self.blueprint_yaml,
            inputs=self.inputs,
            name=self._testMethodName,
            ignored_modules=cli_constants.IGNORED_LOCAL_WORKFLOW_MODULES)

        self.addCleanup(self.uninstall_client)
        self.addCleanup(self.env.handler.remove_keypairs_from_local_env,
                        self.local_env)

        self.logger.info('starting vm to serve as the management vm')
        self.local_env.execute('install',
                               task_retries=10,
                               task_retry_interval=30)
        self.public_ip_address = \
            self.local_env.outputs()['simple_vm_public_ip_address']
        self.private_ip_address = \
            self.local_env.outputs()['simple_vm_private_ip_address']

    def bootstrap_simple_manager_blueprint(self, override_inputs=None):
        self.manager_blueprints_repo_dir = clone(MANAGER_BLUEPRINTS_REPO_URL,
                                                 self.workdir)
        self.test_manager_blueprint_path = \
            os.path.join(self.manager_blueprints_repo_dir,
                         'simple-manager-blueprint.yaml')

        self.bootstrap_inputs = {
            'public_ip': self.public_ip_address,
            'private_ip': self.private_ip_address,
            'ssh_user': self.env.centos_7_image_user,
            'ssh_key_filename': self.inputs['key_pair_path'],
            'agents_user': self.env.centos_7_image_user,
            'resources_prefix': ''
        }

        if override_inputs is not None:
            self.bootstrap_inputs.update(override_inputs)

        # preparing inputs file for bootstrap
        self.test_inputs_path = \
            self.cfy._get_inputs_in_temp_file(self.bootstrap_inputs,
                                              self._testMethodName)
        self._bootstrap()
        self._running_env_setup(self.public_ip_address)

        self.logger.info('Uploading key file to manager...')
        with fabric_api.settings(host_string=self.public_ip_address,
                                 user=self.env.centos_7_image_user,
                                 key_filename=self.inputs['key_pair_path']):
            fabric_api.put(self.inputs['key_pair_path'],
                           self.remote_manager_key_path)

    def _bootstrap(self):
        self.addCleanup(self.cfy.teardown)
        self.cfy.bootstrap(blueprint_path=self.test_manager_blueprint_path,
                           inputs_file=self.test_inputs_path,
                           task_retries=5)

    def _running_env_setup(self, management_ip):
        self.addCleanup(self.clear_management_ip)
        self.env.management_ip = management_ip
        self.client = create_rest_client(management_ip)
        response = self.client.manager.get_status()
        if not response['status'] == 'running':
            raise RuntimeError('Manager at {0} is not running.'
                               .format(management_ip))

    def uninstall_client(self):
        self.local_env.execute('uninstall',
                               task_retries=40,
                               task_retry_interval=30)

    def clear_management_ip(self):
        self.env.management_ip = None

    @property
    def access_credentials(self):
        return {
            'agent_user': self.env.centos_7_image_user,
            'agent_private_key_path': self.remote_manager_key_path
        }
