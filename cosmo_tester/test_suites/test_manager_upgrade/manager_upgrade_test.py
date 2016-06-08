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

from manager_upgrade_base import BaseManagerUpgradeTest


class ManagerUpgradeTest(BaseManagerUpgradeTest):

    def test_manager_upgrade(self):
        """Bootstrap a manager, upgrade it, rollback it, examine the results.

        To test the manager in-place upgrade procedure:
            - bootstrap a manager (this is part of the system under test,
              does destructive changes to the manager, and need a known manager
              version: so, can't use the testenv manager)
            - deploy the hello world app
            - upgrade the manager, changing some inputs (eg. the port that
              Elasticsearch uses)
            - check that everything still works (the previous deployment still
              reports metrics; we can install another deployment)
            - rollback the manager
            - post-rollback checks: the changed inputs are now the original
              values again, the installed app still reports metrics
        """
        self.prepare_manager()

        preupgrade_deployment_id = self.deploy_hello_world('pre-')

        self.upgrade_manager()
        self.post_upgrade_checks(preupgrade_deployment_id)

        self.rollback_manager()
        self.post_rollback_checks(preupgrade_deployment_id)

        self.teardown_manager()
