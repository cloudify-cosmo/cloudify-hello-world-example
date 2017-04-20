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

import json
import os
import subprocess
import tempfile

import pkg_resources

import cosmo_tester
from cosmo_tester.framework.git_helper import clone
from cosmo_tester.framework.testenv import (
    TestCase, initialize_without_bootstrap, clear_environment)
from cosmo_tester.framework.util import YamlPatcher

MANAGER_KEY_FILE_NAME = 'manager_kp.pem'
AGENTS_KEY_FILE_NAME = 'agents_kp.pem'
BLUEPRINTS_REPO = 'https://github.com/cloudify-cosmo/' \
                  'cloudify-manager-blueprints.git'
CLI_REPO = 'https://github.com/cloudify-cosmo/cloudify-cli.git'
HELLO_WORLD_REPO = 'https://github.com/cloudify-cosmo/' \
                   'cloudify-hello-world-example'
SNAPSHOT_TOOL_REPO = 'https://github.com/cloudify-cosmo/' \
                     'cloudify-3.2.1-snapshots-tool'
V3_3_1 = '3.3.1'
V3_2_1 = '3.2.1'
V3_4 = '3.4'


def setUp():
    initialize_without_bootstrap()


def tearDown():
    clear_environment()


class HelloWorldSnapshotMigrationTest(TestCase):
    def _bootstrap_manager(self, version):
        manager_dir = self._get_manager_dir(version)
        cli_repo_dir = clone(CLI_REPO, manager_dir, version)
        blueprint_path = self._prepare_manager_blueprint(version)

        arguments = {
            'manager_dir': manager_dir,
            'venv_dir': self._get_venv_dir(version),
            'activate_path': self._get_activate_path(version),
            'cli_repo_dir': cli_repo_dir,
            'cli_requirements_path': os.path.join(cli_repo_dir,
                                                  'dev-requirements.txt'),
            'blueprint_path': blueprint_path,
            'inputs_path': self._prepare_manager_inputs(
                os.path.dirname(blueprint_path), version)
        }

        self._run_script('bootstrap_manager.sh', arguments)

    def _prepare_manager_blueprint(self, version):
        blueprints_repo_path = clone(BLUEPRINTS_REPO,
                                     self._get_manager_dir(version), version)

        if version == V3_2_1:
            blueprint_path = os.path.join(blueprints_repo_path, 'openstack',
                                          'openstack-manager-blueprint.yaml')
        else:
            blueprint_path = os.path.join(blueprints_repo_path,
                                          'openstack-manager-blueprint.yaml')

        external_resources = [
            'node_templates.management_network.properties',
            'node_templates.management_subnet.properties',
            'node_templates.router.properties',
            'node_templates.agents_security_group.properties',
            'node_templates.management_security_group.properties',
        ]

        with YamlPatcher(blueprint_path) as patch:
            patch.merge_obj(
                'node_templates.management_subnet.properties.subnet',
                {'dns_nameservers': ['8.8.8.8', '8.8.4.4']}
            )

            for prop in external_resources:
                patch.merge_obj(prop, {'use_external_resource': True})

        return blueprint_path

    def _prepare_manager_inputs(self, blueprints_repo_path, version):
        inputs_path = os.path.join(blueprints_repo_path,
                                   'openstack-manager-blueprint-inputs')

        safe_version = version.replace('.', '').replace('-', '_')

        manager_public_key_name = 'manager_{}_{}_kp'.format(self.test_id,
                                                            safe_version)
        agent_public_key_name = 'agents_{}_{}_kp'.format(self.test_id,
                                                         safe_version)

        inputs = {
            'keystone_username': self.env.keystone_username,
            'keystone_password': self.env.keystone_password,
            'keystone_tenant_name': self.env.keystone_tenant_name,
            'keystone_url': self.env.keystone_url,
            'region': self.env.region,
            'use_existing_manager_keypair': False,
            'use_existing_agent_keypair': False,
            'agent_private_key_path': os.path.join(
                self._get_manager_dir(version), 'agents_kp.pem'),
            'manager_public_key_name': manager_public_key_name,
            'agent_public_key_name': agent_public_key_name,
            'flavor_id': self.env.medium_flavor_id,
            'external_network_name': self.env.external_network_name,
            'manager_server_name': 'manager-{}-{}'.format(self.test_id,
                                                          safe_version),
            'management_network_name': self.env.management_network_name,
            'management_subnet_name': self.env.management_subnet_name,
            'management_router': self.env.management_router_name,
            'manager_security_group_name':
                self.env.management_security_group,
            'agents_security_group_name': self.env.agents_security_group,
            'manager_port_name': 'manager-port-{}-{}'.format(self.test_id,
                                                             safe_version),
            'agents_user': 'ubuntu',
        }

        if version == V3_2_1:
            inputs['manager_private_key_path'] = os.path.join(
                        self._get_manager_dir(version), 'manager_kp.pem')
            inputs['manager_server_user'] = 'ubuntu'
            inputs['image_id'] = self.env.ubuntu_trusty_image_id
        else:
            inputs['ssh_key_filename'] = os.path.join(
                    self._get_manager_dir(version), 'manager_kp.pem')
            inputs['ssh_user'] = 'centos'
            inputs['image_id'] = self.env.centos_7_image_id
            inputs['install_python_compilers'] = True

        with open(inputs_path, 'w') as f:
            f.write(json.dumps(inputs))

        self.addCleanup(self.env.handler.remove_keypair,
                        manager_public_key_name)
        self.addCleanup(self.env.handler.remove_keypair,
                        agent_public_key_name)

        return inputs_path

    def _create_and_download_snapshot(self, version):
        manager_dir = self._get_manager_dir(version)

        arguments = {
            'manager_dir': self._get_manager_dir(version),
            'activate_path': os.path.join(
                self._get_activate_path(version)),
            'snapshot_path': self._get_snapshots_path(version)
        }

        if version == V3_2_1:
            arguments['snapshot_tool_dir'] = clone(SNAPSHOT_TOOL_REPO,
                                                   manager_dir)
            self._run_script('download_snapshot_321.sh', arguments)
        else:
            self._run_script('download_snapshot_33plus.sh', arguments)

    def _upload_snapshot(self, from_version, to_version):
        arguments = {
            'manager_dir': self._get_manager_dir(to_version),
            'activate_path': os.path.join(self._get_activate_path(to_version)),
            'snapshot_path': self._get_snapshots_path(from_version)
        }

        self._run_script('upload_snapshot.sh', arguments)

    def _restore_snapshot_and_install_agents(self, version):
        arguments = {
            'manager_dir': self._get_manager_dir(version),
            'activate_path': os.path.join(self._get_activate_path(version)),
        }

        self._run_script('restore_snapshot.sh', arguments)

    def _install_hello_world(self, version):
        manager_dir = self._get_manager_dir(version)

        hello_repo_dir = clone(HELLO_WORLD_REPO, manager_dir, version)
        hello_blueprint_path = os.path.join(hello_repo_dir, 'blueprint.yaml')

        with YamlPatcher(hello_blueprint_path) as patch:
            patch.merge_obj(
                'node_templates.security_group.interfaces',
                {'cloudify.interfaces.lifecycle': {
                    'create': {
                        'inputs': {
                            'args': {'description': 'hello security group'}
                        }
                    }
                }}
            )

        arguments = {
            'manager_dir': manager_dir,
            'activate_path': os.path.join(self._get_activate_path(version)),
            'hello_blueprint_path': hello_blueprint_path,
            'inputs_path': self._prepare_hello_world_inputs()
        }

        self._run_script('install_hello_world.sh', arguments)

    def _store_server_url(self, version):
        arguments = {
            'manager_dir': self._get_manager_dir(version),
            'activate_path': os.path.join(self._get_activate_path(version)),
            'server_url_file_path': self._get_server_url_file_path(version)
        }

        self._run_script('store_server_address.sh', arguments)

    def _assert_server_running(self, version):
        arguments = {
            'server_url': self._get_server_url_file_path(version)
        }

        self._run_script('assert_server_running.sh', arguments)

    def _uninstall_hello_world(self, version):
        arguments = {
            'manager_dir': self._get_manager_dir(version),
            'activate_path': os.path.join(self._get_activate_path(version)),
        }

        self._run_script('uninstall_hello_world.sh', arguments)

    def _stop_hello_world(self, version):
        arguments = {
            'manager_dir': self._get_manager_dir(version),
            'activate_path': os.path.join(self._get_activate_path(version)),
        }

        self._run_script('stop_server.sh', arguments)

    def _assert_server_not_running(self, version):
        arguments = {
            'server_url': self._get_server_url_file_path(version)
        }

        self._run_script('assert_server_not_running.sh', arguments)

    @staticmethod
    def _get_manager_name(version):
        return 'manager-{0}'.format(version)

    def _get_manager_dir(self, version):
        return os.path.join(self.workdir, version.replace('.', ''))

    def _get_venv_dir(self, version):
        return os.path.join(self._get_manager_dir(version), 'venv')

    def _get_activate_path(self, version):
        return os.path.join(self._get_venv_dir(version), 'bin', 'activate')

    def _get_snapshots_path(self, version):
        return os.path.join(self._get_manager_dir(version), 'snapshot')

    def _get_blueprints_dir(self, version):
        return os.path.join(self._get_manager_dir(version), 'blueprints')

    def _get_server_url_file_path(self, version):
        return os.path.join(self._get_manager_dir(version), 'webserver_url')

    def _prepare_hello_world_inputs(self):
        inputs = {
            'agent_user': self.env.cloudify_agent_user,
            'image': self.env.ubuntu_trusty_image_name,
            'flavor': self.env.flavor_name
        }

        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(json.dumps(inputs))

            return f.name

    def _run_script(self, name, arguments):
        script_path = pkg_resources.resource_filename(
            cosmo_tester.__name__,
            'resources/scripts/snapshots_migration_scripts/{0}'.format(
                name)
        )

        command = 'bash "{0}"'.format(script_path)
        rc = subprocess.call(command, shell=True, env=arguments)

        if rc:
            self.fail('Running script {0} failed (return code = {1})'.format(
                name, rc))

    def _test_migration(self, source, destination):
        self._bootstrap_manager(source)
        self._install_hello_world(source)
        self._store_server_url(source)
        self._create_and_download_snapshot(source)
        self._bootstrap_manager(destination)
        self._upload_snapshot(source, destination)
        self._restore_snapshot_and_install_agents(destination)
        self._assert_server_running(source)
        self._stop_hello_world(destination)
        self._assert_server_not_running(source)
        self._uninstall_hello_world(destination)

    def test_migration_331_34(self):
        self._test_migration(V3_3_1, V3_4)

    def test_migration_321_34(self):
        self._test_migration(V3_2_1, V3_4)
