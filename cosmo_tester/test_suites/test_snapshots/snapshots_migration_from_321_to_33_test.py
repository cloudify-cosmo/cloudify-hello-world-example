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
import jinja2
import pkg_resources
import subprocess
import shutil

from nose.tools import nottest

import cosmo_tester
from cosmo_tester.framework.testenv import TestCase
from cosmo_tester.framework.git_helper import clone, checkout
from cosmo_tester.framework.util import create_rest_client, YamlPatcher

from cosmo_tester.framework.testenv import (initialize_without_bootstrap,
                                            clear_environment)


def setUp():
    initialize_without_bootstrap()


def tearDown():
    clear_environment()


VIRTUALENV_NAME = 'env'
HELLOWORLD_APP_NAME = 'helloworld'
SNAPSHOT_NAME = 'snap'
MANAGER_KEY_FILE_NAME = 'manager_kp.pem'
AGENTS_KEY_FILE_NAME = 'agents_kp.pem'
RUNTIME_PROPERTY_NAME = 'rpvalue'

PREPARE_TEMPLATE_NAME = 'prepare_cli_3_2_1.template'
PREPARE_SCRIPT_NAME = 'prepare_old_cli.sh'

HELLOWORLD_TEMPLATE_NAME = 'helloworld_inputs.template'
HELLOWORLD_INPUTS_NAME = 'helloworld_inputs.yaml'

INSTALL_TEMPLATE_NAME = 'install_helloworld_3_2_1.template'
INSTALL_SCRIPT_NAME = 'install_helloworld.sh'

SNAPSHOT_TEMPLATE_NAME = 'create_and_download_snapshot_3_2_1.template'
SNAPSHOT_SCRIPT_NAME = 'create_and_download_snapshot.sh'

RUN_PYTHON_TEMPLATE_NAME = 'update_user_and_credentials_3_2_1.template'
RUN_PYTHON_SCRIPT_NAME = 'update_user_and_credentials_3_2_1.sh'

CLEAR_TEMPLATE_NAME = 'clear_manager_3_2_1.template'
CLEAR_SCRIPT_NAME = 'clear_manager_3_2_1.sh'

BOOTSTRAP_TEMPLATE_NAME = 'bootstrap_manager_3_2_1.template'
BOOTSTRAP_SCRIPT_NAME = 'bootstrap_manager_3_2_1.sh'

TEARDOWN_TEMPLATE_NAME = 'teardown_manager_3_2_1.template'
TEARDOWN_SCRIPT_NAME = 'teardown_manager_3_2_1.sh'

OLD_MANAGER_TEMPLATE_NAME = 'manager_3_2_1_inputs.template'
OLD_MANAGER_INPUTS_NAME = 'manager_3_2_1_inputs.yaml'

NEW_MANAGER_TEMPLATE_NAME = 'manager_3_3_inputs.template'
NEW_MANAGER_INPUTS_NAME = 'manager_3_3_inputs.yaml'

UPDATE_SCRIPT_NAME = 'update_user_and_credentials_3_2_1.py'


class HelloWorldSnapshotMigrationFrom_3_2_1_To_3_3_Test(TestCase):

    def setUp(self):
        super(HelloWorldSnapshotMigrationFrom_3_2_1_To_3_3_Test, self).setUp()

        try:
            self.manager_3_2_1_ip = \
                self.env.handler_configuration['manager_3_2_1_ip']

            msg = "In case of using existing 3.2.1 manager, providing '{0}' " \
                  "is also required."
            try:
                self.manager_cred_path = \
                    self.env.handler_configuration[
                        'manager_3_2_1_credentials_path'
                    ]
            except KeyError as e:
                self.fail(msg.format(e.args[0]))

            self.bootstrap_managers = False

            if not self.env.management_ip:
                self.fail('Manager 3.3 is required to be bootstrapped in case'
                          'of using existing manager 3.2.1.')

        except KeyError:
            self.manager_3_2_1_ip = None
            self.bootstrap_managers = True

        self.snapshot = None

        self.manager_public_key_name = self.test_id + '-manager-kp'
        self.agent_public_key_name = self.test_id + '-agents-kp'
        self.manager_key_path = os.path.join(self.workdir,
                                             MANAGER_KEY_FILE_NAME)
        self.agents_key_path = os.path.join(self.workdir, AGENTS_KEY_FILE_NAME)

        self.management_network_name = self.test_id + '-network'
        self.management_subnet_name = self.test_id + '-subnet'
        self.management_router = self.test_id + '-router'

        self.agents_user = 'ubuntu'

        self.repo_path = clone(
            'https://github.com/cloudify-cosmo/'
            'cloudify-manager-blueprints.git',
            self.workdir,
            '3.3'
        )

        self.runtime_property_value = self.test_id + '-runtime-property'

    def _prepare_old_cli(self):
        self.logger.info('Preparing cli 3.2.1 environment')
        template_vars = {
            'work_dir':   self.workdir,
            'venv_name':  VIRTUALENV_NAME
        }

        self._render_script(
            PREPARE_TEMPLATE_NAME,
            template_vars,
            PREPARE_SCRIPT_NAME
        )

        rc = self._run_script(PREPARE_SCRIPT_NAME)
        if rc:
            self.fail(
                'Preparing cli 3.2.1 environment failed with exit code: {0}'
                .format(rc)
            )

    def _bootstrap_manager_3_3(self):
        self.logger.info('Bootstrapping manager 3.3')

        manager_name = self.test_id + '-manager-33'

        # generate manager inputs file
        inputs_template_vars = {
            'keystone_username': self.env.keystone_username,
            'keystone_password': self.env.keystone_password,
            'keystone_tenant_name': self.env.keystone_tenant_name,
            'keystone_url': self.env.keystone_url,
            'region': self.env.region,
            'flavor_id': self.env.medium_flavor_id,
            'image_id': self.env.centos_7_image_id,

            'manager_server_user': self.env.centos_7_image_user,
            'external_network_name': self.env.external_network_name,
            'resources_prefix': self.env.resources_prefix,

            'manager_server_name': manager_name,

            # shared settings
            'manager_public_key_name': self.manager_public_key_name,
            'agent_public_key_name': self.agent_public_key_name,
            'manager_private_key_path': self.manager_key_path,
            'agent_private_key_path': self.agents_key_path,

            'management_network_name': self.management_network_name,
            'management_subnet_name': self.management_subnet_name,
            'management_router': self.management_router,

            'agents_user': self.agents_user,

            # private settings
            'manager_security_group_name': manager_name + '-m-sg',
            'agents_security_group_name': manager_name + '-a-sg',
            'manager_port_name': manager_name + '-port',
        }

        self._render_script(
            NEW_MANAGER_TEMPLATE_NAME,
            inputs_template_vars,
            NEW_MANAGER_INPUTS_NAME
        )

        blueprint_path = os.path.join(
            self.repo_path,
            'openstack-manager-blueprint.yaml')

        with YamlPatcher(blueprint_path) as patch:
            patch.merge_obj(
                'node_templates.management_subnet.properties.subnet',
                {'dns_nameservers': ['8.8.4.4', '8.8.8.8']}
            )

        self.addCleanup(self._teardown_manager_3_3)
        self.bootstrap(
            blueprint_path,
            inputs=os.path.join(self.workdir, NEW_MANAGER_INPUTS_NAME),
        )

        self.client = create_rest_client(self.get_manager_ip())

        self._run_code_on_manager_3_3('sudo yum install -y gcc python-devel')

    def _teardown_manager_3_3(self):
        self.logger.info('Tearing down manager 3.3')

        self.cfy.teardown(force=True)

    def _run_code_on_manager_3_3(self, code):
        self.logger.info("Running custom code on manager 3.3: '{0}'"
                         .format(code))
        ip = self.get_manager_ip()
        user = self.env.centos_7_image_user

        from path import path
        from distutils import spawn
        ssh_path = spawn.find_executable('ssh')

        if not ssh_path:
            self.fail('SSH command cannot be found')

        with path(self.workdir):
            rc = subprocess.call([
                ssh_path,
                '{0}@{1}'.format(user, ip),
                '-o', 'StrictHostKeyChecking=no',
                '-i', self.manager_key_path,
                '--', code
            ])

            if rc:
                self.fail('Running custom code on manager 3.3 failed with'
                          ' exit code: {0}'.format(rc))

    def _bootstrap_manager_3_2_1(self):
        self.logger.info('Bootstrapping manager 3.2.1')

        self.assertTrue(os.path.exists(self.manager_key_path))
        self.assertTrue(os.path.exists(self.agents_key_path))

        manager_name = self.test_id + '-manager-321'

        # generate manager inputs file
        inputs_template_vars = {
            'keystone_username': self.env.keystone_username,
            'keystone_password': self.env.keystone_password,
            'keystone_tenant_name': self.env.keystone_tenant_name,
            'keystone_url': self.env.keystone_url,
            'region': self.env.region,
            'flavor_id': self.env.medium_flavor_id,
            'image_id': self.env.ubuntu_trusty_image_id,
            'manager_server_user': 'ubuntu',
            'external_network_name': self.env.external_network_name,
            'resources_prefix': self.env.resources_prefix,

            'manager_server_name': manager_name,

            # shared settings
            'manager_public_key_name': self.manager_public_key_name,
            'agent_public_key_name': self.agent_public_key_name,
            'manager_private_key_path': self.manager_key_path,
            'agent_private_key_path': self.agents_key_path,

            'management_network_name': self.management_network_name,
            'management_subnet_name': self.management_subnet_name,
            'management_router': self.management_router,

            'agents_user': self.agents_user,

            # private settings
            'manager_security_group_name': manager_name + '-m-sg',
            'agents_security_group_name': manager_name + '-a-sg',
            'manager_port_name': manager_name + '-port',
            'manager_volume_name': manager_name + '-volume'
        }

        self._render_script(
            OLD_MANAGER_TEMPLATE_NAME,
            inputs_template_vars,
            OLD_MANAGER_INPUTS_NAME
        )

        checkout(self.repo_path, '3.2.1-build', force=True)

        external_resources = [
            'node_templates.management_network.properties',
            'node_templates.management_subnet.properties',
            'node_templates.router.properties',
        ]

        blueprint_path = os.path.join(
            self.repo_path,
            'openstack',
            'openstack-manager-blueprint.yaml'
        )

        with YamlPatcher(blueprint_path) as patch:
            for prop in external_resources:
                patch.merge_obj(prop, {'use_external_resource': True})

            patch.merge_obj(
                'node_templates.management_subnet.properties.subnet',
                {'dns_nameservers': ['8.8.4.4', '8.8.8.8']}
            )

        template_vars = {
            'work_dir':   self.workdir,
            'venv_name':  VIRTUALENV_NAME,
            'inputs_file': OLD_MANAGER_INPUTS_NAME,
            'repo_path': self.repo_path
        }

        self._render_script(
            BOOTSTRAP_TEMPLATE_NAME,
            template_vars,
            BOOTSTRAP_SCRIPT_NAME
        )

        self.addCleanup(self._teardown_manager_3_2_1)
        rc = self._run_script(BOOTSTRAP_SCRIPT_NAME)
        if rc:
            self.fail(
                'Bootstrapping manager 3.2.1 failed with exit code: {0}'
                .format(rc)
            )

    def _teardown_manager_3_2_1(self):
        self.logger.info('Tearing down manager 3.2.1')

        template_vars = {
            'work_dir':   self.workdir,
            'venv_name':  VIRTUALENV_NAME
        }

        self._render_script(
            TEARDOWN_TEMPLATE_NAME,
            template_vars,
            TEARDOWN_SCRIPT_NAME
        )

        rc = self._run_script(TEARDOWN_SCRIPT_NAME)
        if rc:
            self.fail(
                'Tearing down manager 3.2.1 failed with exit code: {0}'
                .format(rc)
            )

    def _set_user_and_credentials(self):
        self.logger.info('Updating user and credentials info for cli 3.2.1')
        self.assertIsNotNone(self.manager_cred_path)

        update_script = pkg_resources.resource_filename(
            cosmo_tester.__name__,
            'resources/scripts/snapshots_migration_scripts/{0}'
            .format(UPDATE_SCRIPT_NAME)
        )

        shutil.copy(update_script, self.workdir)

        command = '{0} {1}'.format(
            os.path.join(self.workdir, UPDATE_SCRIPT_NAME),
            self.manager_cred_path
        )

        template_vars = {
            'work_dir':   self.workdir,
            'venv_name':  VIRTUALENV_NAME,
            'manager_ip': self.manager_3_2_1_ip,
            'command': command
        }

        self._render_script(
            RUN_PYTHON_TEMPLATE_NAME,
            template_vars,
            RUN_PYTHON_SCRIPT_NAME
        )

        rc = self._run_script(RUN_PYTHON_SCRIPT_NAME)
        if rc:
            self.fail(
                'Updating cli 3.2.1 environment failed with exit code: {0}'
                .format(rc)
            )

    def _install_hello_world_on_3_2_1(self):
        self.logger.info('Installing HelloWorld application on manager 3.2.1')

        # generate inputs file
        inputs_template_vars = {
            'agent_user': self.env.cloudify_agent_user,
            'image':      self.env.ubuntu_trusty_image_name,
            'flavor':     self.env.flavor_name
        }

        self._render_script(
            HELLOWORLD_TEMPLATE_NAME,
            inputs_template_vars,
            HELLOWORLD_INPUTS_NAME
        )

        hello_repo_path = clone(
            'https://github.com/cloudify-cosmo/'
            'cloudify-hello-world-example.git',
            self.workdir,
            '3.2.1-build'
        )

        hello_blueprint_path = os.path.join(hello_repo_path, 'blueprint.yaml')

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

        template_vars = {
            'work_dir':   self.workdir,
            'venv_name':  VIRTUALENV_NAME,
            'repo_path': hello_repo_path,
            'helloworld_inputs_file': HELLOWORLD_INPUTS_NAME,
            'app_name': HELLOWORLD_APP_NAME,
            'runtime_property_name': RUNTIME_PROPERTY_NAME,
            'runtime_property_value': self.runtime_property_value
        }

        self._render_script(
            INSTALL_TEMPLATE_NAME,
            template_vars,
            INSTALL_SCRIPT_NAME
        )

        rc = self._run_script(INSTALL_SCRIPT_NAME)
        if rc:
            self.fail(
                'Installing HelloWorld application on manager 3.2.1 failed '
                'with exit code: {0}'.format(rc)
            )

    def _create_and_download_snapshot_on_3_2_1(self):
        self.logger.info('Creating/downloading snapshot on manager 3.2.1')
        template_vars = {
            'work_dir':   self.workdir,
            'venv_name':  VIRTUALENV_NAME
        }

        self._render_script(
            SNAPSHOT_TEMPLATE_NAME,
            template_vars,
            SNAPSHOT_SCRIPT_NAME
        )

        rc = self._run_script(SNAPSHOT_SCRIPT_NAME)
        if rc:
            self.fail(
                'Creating/downloading snapshot on manager 3.2.1 failed '
                'with exit code: {0}'.format(rc)
            )

    def _clear_manager_3_2_1(self):
        self.logger.info('Clearing manager 3.2.1')
        template_vars = {
            'work_dir':   self.workdir,
            'venv_name':  VIRTUALENV_NAME,
            'app_name':   HELLOWORLD_APP_NAME
        }

        self._render_script(
            CLEAR_TEMPLATE_NAME,
            template_vars,
            CLEAR_SCRIPT_NAME
        )

        rc = self._run_script(CLEAR_SCRIPT_NAME)
        if rc:
            self.fail(
                'Clearing manager 3.2.1 failed '
                'with exit code: {0}'.format(rc)
            )

    def _upload_snapshot_to_new_manager(self):
        self.logger.info('Uploading snapshot to manager 3.3')
        snapshot_path = os.path.join(self.workdir, 'snapshot.zip')
        self.assertTrue(os.path.exists(snapshot_path))

        snap = self.client.snapshots.upload(snapshot_path, SNAPSHOT_NAME)
        self.assertFalse(snap.error)
        self.snapshot = snap

    def _restore_snapshot(self):
        self.logger.info('Restoring snapshot on manager 3.3')
        self.assertIsNotNone(self.snapshot)

        execution = self.client.snapshots.restore(SNAPSHOT_NAME, force=True)
        self.wait_for_execution(execution, 900)

        # agents migration
        self.logger.info('-- Installing agents')
        self.cfy.agents.install(HELLOWORLD_APP_NAME)

    def _uninstall_hello_world(self):
        self.logger.info('Uninstalling Helloworld application by '
                         'using manager 3.3')
        execution = self.client.executions.start(HELLOWORLD_APP_NAME,
                                                 'uninstall')
        self.wait_for_execution(execution, 900)

    def _clear_manager(self):
        self.logger.info('Clearing manager 3.3')

        self.logger.info('-- Deleting deployment')
        self.client.deployments.delete(HELLOWORLD_APP_NAME)

        self.logger.info('-- Deleting blueprint')
        self.client.blueprints.delete(HELLOWORLD_APP_NAME)

        self.logger.info('-- Deleting snapshot')
        self.client.snapshots.delete(SNAPSHOT_NAME)

    def _check_runtime_property(self):
        self.logger.info("Checking existence and value of runtime "
                         "property '{0}'".format(RUNTIME_PROPERTY_NAME))

        node_instances = self.client.node_instances.list(HELLOWORLD_APP_NAME)
        found = False
        for ni in node_instances:
            if RUNTIME_PROPERTY_NAME in ni.runtime_properties:
                found = True
                self.assertEqual(
                    ni.runtime_properties.get(RUNTIME_PROPERTY_NAME),
                    self.runtime_property_value
                )

        if not found:
            self.fail("Runtime property '{0}' not found"
                      .format(RUNTIME_PROPERTY_NAME))

    @nottest
    def test_snapshot_from_321_to_33(self):

        # manager 3.2.1 actions
        self._prepare_old_cli()

        if self.bootstrap_managers:
            self._bootstrap_manager_3_3()
            self._bootstrap_manager_3_2_1()
        else:
            self._set_user_and_credentials()

        self._install_hello_world_on_3_2_1()
        self._create_and_download_snapshot_on_3_2_1()

        # manager 3.3 actions
        self._upload_snapshot_to_new_manager()
        self._restore_snapshot()
        self._uninstall_hello_world()
        self._check_runtime_property()

        # If we bootstrap managers then we also teardown them so we don't
        # need to clear them.
        if not self.bootstrap_managers:
            self._clear_manager()
            self._clear_manager_3_2_1()

        self.logger.info("Test finished")

    def _render_script(self, script_name, template_vars, output_name):
        shell_script_template = pkg_resources.resource_string(
            cosmo_tester.__name__,
            'resources/scripts/snapshots_migration_scripts/{0}'
            .format(script_name)
        )

        rendered_script = jinja2.Template(shell_script_template).\
            render(template_vars)
        output_script_path = os.path.join(self.workdir, output_name)
        with open(output_script_path, 'w') as f:
            f.write(rendered_script)

        # set permission to execute file
        permissions = os.stat(output_script_path)
        os.chmod(output_script_path, permissions.st_mode | 0111)

    def _run_script(self, script_name):
        self.logger.info('-- Running bash script: {0}'.format(script_name))
        return subprocess.call(
            'bash {0}'.format(os.path.join(self.workdir, script_name)),
            shell=True
        )
