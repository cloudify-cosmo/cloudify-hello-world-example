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

import time

from cosmo_tester.test_suites.test_blueprints.hello_world_bash_test import \
    HelloWorldBashTest
from cloudify_rest_client.executions import Execution
from cosmo_tester.framework.testenv import bootstrap, teardown


def setUp():
    bootstrap()


def tearDown():
    teardown()


class SnapshotsSingleManagerTest(HelloWorldBashTest):
    """
    This test deploys hello world, creates an additional deployment and a
    snapshot, deletes both deployments and the corresponding blueprint,
    restores the snapshot and validates that the manager is consistent
    and operational - uninstalling hello world, deleting both deployments
    and deleting the blueprint should succeed.
    """

    def _run(self, *args, **kwargs):
        self.blueprint_id = self.test_id
        self.deployment_id = self.test_id
        self.additional_dep_id = self.deployment_id + '_2'

        super(SnapshotsSingleManagerTest, self)._run(*args, **kwargs)

        self.client.deployments.delete(self.deployment_id)
        self.client.blueprints.delete(self.deployment_id)

    def _do_post_install_assertions(self):
        context = super(SnapshotsSingleManagerTest,
                        self)._do_post_install_assertions()
        snapshot_id = 'helloworld_sn-{0}'.format(time.strftime("%Y%m%d-%H%M"))

        dep_inputs = self.client.deployments.get(self.deployment_id).inputs
        self.create_deployment(
            self.blueprint_id,
            self.additional_dep_id,
            inputs=dep_inputs
        )
        self.wait_until_all_deployment_executions_end(self.additional_dep_id)

        self.client.snapshots.create(snapshot_id, True, True)

        waited = 0
        time_between_checks = 5
        snapshot = self.client.snapshots.get(snapshot_id)
        while snapshot.status == 'creating':
            time.sleep(time_between_checks)
            waited += time_between_checks
            self.assertTrue(
                waited <= 3 * 60,
                'Waiting too long for create snapshot to finish'
            )
            snapshot = self.client.snapshots.get(snapshot_id)
        self.assertEqual('created', snapshot.status)

        self.cfy.deployments.delete(self.deployment_id, force=True)
        self.cfy.deployments.delete(self.additional_dep_id)
        self.client.blueprints.delete(self.blueprint_id)

        def get_sorted_plugins():
            return self.client.plugins.list(_sort=['id']).items
        plugins_before_restore = get_sorted_plugins()

        waited = 0
        execution = self.client.snapshots.restore(snapshot_id)
        while execution.status not in Execution.END_STATES:
            waited += time_between_checks
            time.sleep(time_between_checks)
            self.assertTrue(
                waited <= 20 * 60,
                'Waiting too long for restore snapshot to finish'
            )
            execution = self.client.executions.get(execution.id)
        if execution.status == Execution.FAILED:
            self.logger.error('Execution error: {0}'.format(execution.error))
        self.assertEqual(Execution.TERMINATED, execution.status)
        self.logger.info('Snapshot restored, deleting snapshot..')
        self.client.snapshots.delete(snapshot_id)
        self.assertEqual(plugins_before_restore, get_sorted_plugins(),
                         'Plugins should remain intact after restore..')
        # Throws if not found
        self.client.deployments.delete(self.additional_dep_id)

        return context
