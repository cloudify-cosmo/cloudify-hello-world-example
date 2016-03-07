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
import time
from operator import itemgetter
from path import path

from cloudify_rest_client import CloudifyClient

from cosmo_tester.framework.testenv import TestCase
from cosmo_tester.resources import blueprints
from cosmo_tester.framework import util


class BaseManagerRecoveryTest(TestCase):

    def _get_snapshot_id(self):
        pass

    def _bootstrap_and_install(self):
        self._copy_manager_blueprint()

        # bootstrap and install
        self.bootstrap()
        self._install_blueprint()

    def _pre_recover_actions(self):
        self.snapshot_id = self._get_snapshot_id()
        self.snapshot_file_path = '{0}.zip'.format(
            os.path.join(self.workdir, self.snapshot_id))
        self.cfy.create_snapshot(self.snapshot_id)

        # waiting for snapshot file to be created on the manager
        start_time = time.time()
        snapshot_created = False
        while time.time() < start_time + 30 and not snapshot_created:
            for snapshot in self.client.snapshots.list():
                if self.snapshot_id == snapshot.id \
                        and snapshot.status == 'created':
                    snapshot_created = True
                    break

        self.cfy.download_snapshot(self.snapshot_id, self.snapshot_file_path)

    def _sort_workflows_list_in_state_by_name(self, state):
        for deployment in state['deployments'].values():
            sorted_list = sorted(
                deployment['workflows'], key=itemgetter('name'))
            deployment['workflows'] = sorted_list

    def _add_agent_migration_props(self,
                                   old_state,
                                   new_state,
                                   properties_to_add_list):
        for deployment_id, deployment in new_state['node_state'].items():
            for instance_id, node in deployment.items():
                if 'cloudify_agent' not in node['runtime_properties']:
                    continue
                after_agent = node['runtime_properties']['cloudify_agent']
                instance1 = old_state['node_state'][deployment_id][instance_id]
                instance2 = old_state['nodes'][instance_id]
                for instance in old_state['deployment_nodes'][deployment_id]:
                    if instance['id'] == instance_id:
                        instance3 = instance
                        break
                else:
                    self.fail('Failed finding: {0}'.format(instance_id))
                for instance in [instance1, instance2, instance3]:
                    before_agent = instance['runtime_properties'][
                        'cloudify_agent']
                    for prop in properties_to_add_list:
                        before_agent[prop] = after_agent[prop]

    def _assert_before_after_states(self, after, before):
        # for some reason, the workflow order changes
        self._sort_workflows_list_in_state_by_name(before)
        self._sort_workflows_list_in_state_by_name(after)

        # some cloudify agent properties are added during the
        # snapshot creation, so they're added to the before state here
        properties_to_add = [
            u'version',
            u'broker_config'
        ]

        self._add_agent_migration_props(before, after, properties_to_add)

        self.assertEqual(before, after)

    def _test_manager_recovery_impl(self):

        self._bootstrap_and_install()

        self._pre_recover_actions()
        # this will verify that all the data is actually persisted.
        before, after = self._recover_manager()

        self._assert_before_after_states(after, before)

        # make sure we can still execute operation on agents.
        # this will verify that the private ip of the manager remained
        # the same. this will also test that the workflows worker is still
        # responding to tasks.

        self.cfy.execute_workflow(
            'execute_operation',
            self.deployment_id,
            parameters={
                'operation': 'cloudify.interfaces.greet.hello'
            }
        )

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
            'image': self.env.ubuntu_trusty_image_id,
            'flavor': self.env.small_flavor_id
        }

        blueprint_id = 'recovery-{0}'.format(self.test_id)
        self.deployment_id = blueprint_id
        self.upload_deploy_and_execute_install(
            inputs=inputs,
            deployment_id=self.deployment_id,
            blueprint_id=blueprint_id
        )

    def _recover_manager(self):

        def recover():
            snapshot_path = self.snapshot_file_path
            self.cfy.recover(task_retries=10, snapshot_path=snapshot_path)

        return self._make_operation_with_before_after_states(
            recover,
            fetch_state=True)

    def bootstrap(self):
        self.cfy.bootstrap(blueprint_path=self.test_manager_blueprint_path,
                           inputs_file=self.test_inputs_path,
                           task_retries=5,
                           install_plugins=self.env.install_plugins)

        # override the client instance to use the correct ip
        self.client = CloudifyClient(self.cfy.get_management_ip())

        self.addCleanup(self.cfy.teardown)
