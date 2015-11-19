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

from cosmo_tester.test_suites.test_blueprints.nodecellar_test import \
    OpenStackNodeCellarTestBase
from cloudify_rest_client.executions import Execution


class SnapshotsSingleManagerTest(OpenStackNodeCellarTestBase):
    """
    This test deploys nodecellar, creates an additional deployment and a
    snapshot, deletes both deployments and the corresponding blueprint,
    restores the snapshot and validates that the manager is consistent
    and operational - uninstalling nodecellar, deleting both deployments
    and deleting the blueprint should succeed.
    """

    def test_openstack_nodecellar(self):
        self.blueprint_id = self.test_id
        self.deployment_id = self.test_id
        self.additional_dep_id = self.deployment_id + '_2'

        self._test_openstack_nodecellar('openstack-blueprint.yaml')

        self.wait_for_stop_dep_env_execution_to_end(self.deployment_id)
        self.client.deployments.delete(self.deployment_id)
        self.client.blueprints.delete(self.deployment_id)

    def on_nodecellar_installed(self):
        snapshot_id = 'nodecellar_sn-{0}'.format(time.strftime("%Y%m%d-%H%M"))

        self.cfy.create_deployment(self.blueprint_id, self.additional_dep_id,
                                   inputs=self.get_inputs())
        self.wait_until_all_deployment_executions_end(self.additional_dep_id)

        self.wait_for_stop_dep_env_execution_to_end(self.deployment_id)
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

        self.cfy.delete_deployment(self.deployment_id, ignore_live_nodes=True)
        self.cfy.delete_deployment(self.additional_dep_id)
        self.client.blueprints.delete(self.blueprint_id)

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
        # Throws if not found
        self.client.deployments.delete(self.additional_dep_id)
