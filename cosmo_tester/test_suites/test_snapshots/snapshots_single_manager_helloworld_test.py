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

import json
import os

from cosmo_tester.test_suites.test_blueprints.hello_world_bash_test \
    import clone_hello_world
from cosmo_tester.framework.testenv import TestCase, bootstrap, teardown


EXECUTION_TIMEOUT = 120


def setUp():
    bootstrap()


def tearDown():
    teardown()


class SnapshotsHelloWorldTest(TestCase):

    def _assert_manager_clean(self):
        state = self.get_manager_state()
        for v in state.itervalues():
            self.assertFalse(bool(v), 'Manager is not clean')

    def _assert_manager_state(self, blueprints_ids, deployments_ids):
        state = self.get_manager_state()
        self.assertEquals(set(blueprints_ids), set(state['blueprints'].keys()))
        self.assertEquals(set(deployments_ids),
                          set(state['deployments'].keys()))

    def setUp(self):
        super(SnapshotsHelloWorldTest, self).setUp()
        self._assert_manager_clean()
        self.repo_dir = clone_hello_world(self.workdir)
        self.blueprint_yaml = os.path.join(self.repo_dir, 'blueprint.yaml')
        self.counter = 0

    def tearDown(self):
        state = self.get_manager_state()
        for d in state['deployments']:
            self.wait_until_all_deployment_executions_end(d)
            self.client.deployments.delete(d)
        for b in state['blueprints']:
            self.client.blueprints.delete(b)
        for snapshot in self.client.snapshots.list():
            self.client.snapshots.delete(snapshot.id)
        super(SnapshotsHelloWorldTest, self).tearDown()

    def _deploy(self, deployment_id, blueprint_id=None):
        if blueprint_id is None:
            blueprint_id = deployment_id
        self.upload_blueprint(blueprint_id)
        inputs = {
            'agent_user': self.env.cloudify_agent_user,
            'image': self.env.ubuntu_trusty_image_name,
            'flavor': self.env.flavor_name
        }
        self.create_deployment(blueprint_id, deployment_id, inputs=inputs)
        self.wait_until_all_deployment_executions_end(deployment_id)

    def _delete(self, deployment_id, blueprint_id=None):
        if blueprint_id is None:
            blueprint_id = deployment_id
        self.client.deployments.delete(deployment_id)
        self.client.blueprints.delete(blueprint_id)

    def _uuid(self):
        self.counter += 1
        return '{0}_{1}'.format(self.test_id, self.counter)

    def _create_snapshot(self, snapshot_id):
        self.logger.info('Creating snapshot {0}'.format(snapshot_id))
        execution = self.client.snapshots.create(snapshot_id,
                                                 include_metrics=False,
                                                 include_credentials=False)
        self.wait_for_execution(execution, timeout=EXECUTION_TIMEOUT)

    def _restore_snapshot(self, snapshot_id, force=False, assert_success=True):
        self.logger.info('Restoring snapshot {0}'.format(snapshot_id))
        execution = self.client.snapshots.restore(snapshot_id, force=force)
        self.wait_for_execution(execution, timeout=EXECUTION_TIMEOUT,
                                assert_success=assert_success)
        return self.client.executions.get(execution_id=execution.id)

    def _restore_snapshot_failure_expected(self, snapshot_id, force=False):
        old_state = self.get_manager_state()
        execution = self._restore_snapshot(snapshot_id, force=force,
                                           assert_success=False)
        self.assertEquals(execution.status, 'failed')
        new_state = self.get_manager_state()
        for k in ['blueprints', 'deployments', 'nodes']:
            error_msg = ('State changed for key {0}\nBefore:\n'
                         '{1}\nAfter:\n{2}').format(
                k,
                json.dumps(old_state[k], indent=2),
                json.dumps(new_state[k], indent=2)
            )
            self.assertEquals(old_state[k], new_state[k], error_msg)
        self.logger.info('Restoring snapshot {0} failed as expected'.format(
                         snapshot_id))
        return execution

    def test_simple(self):
        dep = self._uuid()
        self._deploy(dep)
        self._create_snapshot(dep)
        self._delete(dep)
        self._assert_manager_clean()
        self._restore_snapshot(dep)
        self._assert_manager_state(blueprints_ids={dep},
                                   deployments_ids={dep})
        self.client.snapshots.delete(dep)
        self._delete(dep)

    def test_not_clean(self):
        dep = self._uuid()
        self._deploy(dep)
        self._create_snapshot(dep)
        self._restore_snapshot_failure_expected(dep)

    def test_force_with_conflict(self):
        dep = self._uuid()
        snapshot = self._uuid()
        self._deploy(dep)
        self._create_snapshot(snapshot)
        execution = self._restore_snapshot_failure_expected(snapshot,
                                                            force=True)
        self.assertIn(dep, execution.error)

    def test_force_with_deployment_conflict(self):
        deployment = self._uuid()
        blueprint = self._uuid()
        snapshot = self._uuid()
        self._deploy(deployment_id=deployment, blueprint_id=blueprint)
        self._assert_manager_state(blueprints_ids={blueprint},
                                   deployments_ids={deployment})
        self._create_snapshot(snapshot)
        self._delete(deployment_id=deployment, blueprint_id=blueprint)
        new_blueprint = self._uuid()
        self._deploy(deployment_id=deployment, blueprint_id=new_blueprint)
        self._assert_manager_state(blueprints_ids={new_blueprint},
                                   deployments_ids={deployment})
        execution = self._restore_snapshot_failure_expected(snapshot,
                                                            force=True)
        self.assertIn(deployment, execution.error)

    def test_force_with_blueprint_conflict(self):
        blueprint = self._uuid()
        self.upload_blueprint(blueprint)
        snapshot = self._uuid()
        self._create_snapshot(snapshot)
        execution = self._restore_snapshot_failure_expected(snapshot,
                                                            force=True)
        self.assertIn(blueprint, execution.error)

    def test_force_no_conflict(self):
        dep = self._uuid()
        self._deploy(dep)
        self._create_snapshot(dep)
        self._delete(dep)
        self._assert_manager_clean()
        dep2 = self._uuid()
        self._deploy(dep2)
        self._restore_snapshot(dep, force=True)
        self._assert_manager_state(blueprints_ids={dep, dep2},
                                   deployments_ids={dep, dep2})
        self.client.snapshots.delete(dep)
        self._delete(dep)
        self._delete(dep2)
