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

from contextlib import contextmanager
from cStringIO import StringIO
import json
import sh
from path import path


from manager_upgrade_base import BaseManagerUpgradeTest


class ManagerRollbackIdempotencyTest(BaseManagerUpgradeTest):
    """Rollback is idempotent - nothing will break if we run it several times.

    In case of rollback breaking (randomly, due to eg. network outages),
    we should be able to simply re-run it to finish the rollback procedure.
    """

    @contextmanager
    def break_rollback(self):
        """Make sure the sanity test on the manager fails during rollback.

        To do this, we'd like to change the sanity app url to a nonexistent
        one. Note however that rollback will use the url that is stored
        on the manager in the rollback properties file, so we need to
        alter that file.
        """
        base_dir = path('/opt/cloudify/sanity')
        fetched_properties = StringIO()
        fetched_resources = StringIO()

        properties_path = base_dir / 'node_properties_rollback/properties.json'
        resources_path = base_dir / 'resources_rollback/__resources.json'

        with self._manager_fabric_env() as fabric:
            fabric.get(properties_path, fetched_properties)
            properties = json.loads(fetched_properties.getvalue())

            fabric.get(resources_path, fetched_resources)
            resources = json.loads(fetched_resources.getvalue())

            properties['sanity_app_source_url'] = 'fake.tar.gz'
            resources['fake.tar.gz'] = 'fake.tar.gz'

            fabric.put(StringIO(json.dumps(properties)), properties_path)
            fabric.put(StringIO(json.dumps(resources)), resources_path)

        try:
            yield
        finally:
            # now we need to restore the original, correct values: but by
            # this time, the properties were moved to the non-rollback
            # storage directories
            with self._manager_fabric_env() as fabric:
                fabric.put(fetched_properties,
                           base_dir / 'node_properties/properties.json')
                fabric.put(fetched_resources,
                           base_dir / 'resources/__resources.json')

    def fail_rollback_manager(self):
        """Run a rollback, ensuring it will fail on the sanity test phase."""
        with self.break_rollback():
            self.rollback_manager()

    def test_rollback_failure(self):
        """Upgrade, run rollback, fail in the middle, run rollback again
        and verify rollback complete.
        """
        self.prepare_manager()
        preupgrade_deployment_id = self.deploy_hello_world('pre-')

        self.upgrade_manager()
        self.post_upgrade_checks(preupgrade_deployment_id)

        try:
            self.fail_rollback_manager()
        except sh.ErrorReturnCode as e:
            error_msg = "fake.tar.gz': no such file or directory"
            stdout = e.stdout.lower().decode('utf-8')
            self.assertIn(error_msg,
                          self.replace_illegal_chars(stdout))
        else:
            self.fail(msg='Rollback expected to fail')

        self.rollback_manager()
        self.post_rollback_checks(preupgrade_deployment_id)
        self.teardown_manager()

    def test_rollback_twice(self):
        """Upgrade, run rollback, finish, run rollback again and see that
        nothing changed.
        """
        self.prepare_manager()
        preupgrade_deployment_id = self.deploy_hello_world('pre-')

        self.upgrade_manager()
        self.post_upgrade_checks(preupgrade_deployment_id)

        self.rollback_manager()
        self.post_rollback_checks(preupgrade_deployment_id)
        self.rollback_manager()
        self.post_rollback_checks(preupgrade_deployment_id)

        self.teardown_manager()
