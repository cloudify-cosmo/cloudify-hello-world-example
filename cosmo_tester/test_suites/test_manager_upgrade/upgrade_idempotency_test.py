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

import sh
import StringIO
from mock import patch

from manager_upgrade_base import BaseManagerUpgradeTest


class ManagerUpgradeIdempotencyTest(BaseManagerUpgradeTest):

    def test_manager_upgrade(self):
        """Bootstrap a manager, upgrade it and fail the upgrade at the last
        node, upgrade again (without failure), examine the results.
        """

        self.prepare_manager()
        preupgrade_deployment_id = self.deploy_hello_world('pre-')

        test_stdout = StringIO.StringIO()

        with patch('sys.stdout', test_stdout):
            try:
                self.fail_upgrade_manager()
                self.fail(msg='Upgrade expected to fail')
            except sh.ErrorReturnCode:
                test_stdout.getvalue()
                error_msg = "fake_path.tar.gz': No such file or directory"
                if error_msg not in self.replace_illegal_chars(
                        test_stdout.getvalue()):
                    self.fail(msg="Upgrade didn't fail on expected reason")
            except:
                self.fail(msg="Upgrade didn't fail on expected reason")
            finally:
                self.logger.info(
                    'Upgrade output: {0}'.format(
                        self.replace_illegal_chars(
                            test_stdout.getvalue())))

        self.upgrade_manager()
        self.post_upgrade_checks(preupgrade_deployment_id)
        self.teardown_manager()
        return

    def fail_upgrade_manager(self):
        blueprint_path = self.get_upgrade_blueprint()
        upgrade_inputs = self._get_fail_upgrade_inputs()
        self.upgrade_manager(blueprint=blueprint_path,
                             inputs=upgrade_inputs)

    def _get_fail_upgrade_inputs(self):
        # The fake sanity app url will cause the upgrade to fail
        return {
            'private_ip': self.manager_private_ip,
            'public_ip': self.upgrade_manager_ip,
            'ssh_key_filename': self.manager_inputs['ssh_key_filename'],
            'ssh_user': self.manager_inputs['ssh_user'],
            'sanity_app_source_url': 'fake_path.tar.gz'
        }
