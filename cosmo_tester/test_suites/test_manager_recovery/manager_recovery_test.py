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

from fabric.api import sudo
from fabric.api import settings

from cosmo_tester.framework.testenv import TestCase
from cosmo_tester.resources import blueprints
from cosmo_tester.framework.cfy_helper import cfy as cli
from cosmo_tester.framework import util


class ManagerRecoveryTest(TestCase):

    def setUp(self):
        super(ManagerRecoveryTest, self).setUp()
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
            'host_string': self.env.management_ip,
            'port': 22,
            'user': self.env.management_user_name,
            'key_filename': util.get_actual_keypath(
                self.env,
                self.env.management_key_path
            ),
            'connection_attempts': 5
        }

    def test_manager_recovery(self):

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

    def _kill_and_recover_manager(self):

        def _kill_and_recover():
            self.cfy.use(management_ip=self.env.management_ip,
                         provider=False)
            with settings(**self.fabric_env):
                sudo('docker kill cfy')
            self.cfy.recover()
            self._fix_servers_state()

        return self._make_operation_with_before_after_states(
            _kill_and_recover,
            fetch_state=True)

    def _fix_servers_state(self):

        # retrieve the id of the new management server
        nova, _, _ = self.env.handler.openstack_clients()
        management_server_name = self.env.management_server_name
        managers = nova.servers.list(
            search_opts={'name': management_server_name})
        if len(managers) > 1:
            raise RuntimeError(
                'Expected 1 manager with name {0}, but found '
                '{1}'.format(management_server_name, len(managers)))

        new_manager_id = managers[0].id

        # retrieve the id of the old management server
        old_manager_id = None
        servers = self._test_cleanup_context.before_run['servers']
        for server_id, server_name in servers.iteritems():
            if server_name == management_server_name:
                old_manager_id = server_id
                break
        if old_manager_id is None:
            raise RuntimeError(
                'Could not find a server with name {0} '
                'in the internal cleanup context state'
                .format(management_server_name))

        # replace the id in the internal state
        servers[new_manager_id] = servers.pop(old_manager_id)
