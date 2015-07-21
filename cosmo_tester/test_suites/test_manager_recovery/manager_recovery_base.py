########
# Copyright (c) 2014 GigaSpaces Technologies Ltd. All rights reserved
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
from path import path

from fabric.api import sudo
from fabric.api import settings
from cloudify_rest_client import CloudifyClient

from cosmo_tester.framework.testenv import TestCase
from cosmo_tester.resources import blueprints
from cosmo_tester.framework import util
from cosmo_tester.framework.cfy_helper import cfy as cli


class BaseManagerRecoveryTest(TestCase):

    def _test_manager_recovery_impl(self):

        self._copy_manager_blueprint()

        # bootstrap and install
        self.bootstrap()
        self._install_blueprint()
        self.wait_for_stop_dep_env_execution_to_end(self.deployment_id)

        # this will verify that all the data is actually persisted.
        before, after = self._kill_and_recover_manager()
        self.assertEqual(before, after)

        # make sure we can still execute operation on agents.
        # this will verify that the private ip of the manager remained
        # the same. this will also test that the workflows worker is still
        # responding to tasks.
        cli.executions.start(
            workflow='execute_operation',
            parameters={
                'operation': 'cloudify.interfaces.greet.hello'
            },
            deployment_id=self.deployment_id
        ).wait()

        # there is only one node instance in the blueprint
        node_instance = self.client.node_instances.list()[0]

        # make sure the operation was indeed executed
        self.assertEqual(node_instance['runtime_properties']['greet'],
                         'hello')

        # this will test that the operations worker is still responsive
        self.execute_uninstall(self.deployment_id)

        # this will test the management worker is still responding
        self.cfy.delete_deployment(self.deployment_id)

    def _copy_manager_blueprint(self):
        inputs_path, mb_path = util.generate_unique_configurations(
            workdir=self.workdir,
            original_inputs_path=self.env.cloudify_config_path,
            original_manager_blueprint_path=self.env._manager_blueprint_path)
        self.test_manager_blueprint_path = path(mb_path)
        self.test_inputs_path = path(inputs_path)

    def _install_blueprint(self):
        self.blueprint_yaml = os.path.join(
            os.path.dirname(blueprints.__file__),
            'recovery',
            'blueprint.yaml'
        )

        inputs = {
            'image': self.env.ubuntu_image_id,
            'flavor': self.env.small_flavor_id
        }

        blueprint_id = 'recovery-{0}'.format(self.test_id)
        self.deployment_id = blueprint_id
        self.upload_deploy_and_execute_install(
            inputs=inputs,
            deployment_id=self.deployment_id,
            blueprint_id=blueprint_id
        )
        self.fabric_env = self._setup_fabric_env()

    def _setup_fabric_env(self):
        return {
            'host_string': self.cfy.get_management_ip(),
            'port': 22,
            'user': self.env.management_user_name,
            'key_filename': util.get_actual_keypath(
                self.env,
                self.env.management_key_path
            ),
            'connection_attempts': 5
        }

    def _kill_and_recover_manager(self):

        def _kill_and_recover():
            with settings(**self.fabric_env):
                sudo('docker kill cfy')
            self.cfy.recover(task_retries=10)

        return self._make_operation_with_before_after_states(
            _kill_and_recover,
            fetch_state=True)

    def bootstrap(self):
        self.cfy.bootstrap(blueprint_path=self.test_manager_blueprint_path,
                           inputs_file=self.test_inputs_path,
                           task_retries=5,
                           install_plugins=self.env.install_plugins)

        # override the client instance to use the correct ip
        self.client = CloudifyClient(self.cfy.get_management_ip())

        self.addCleanup(self.cfy.teardown)
