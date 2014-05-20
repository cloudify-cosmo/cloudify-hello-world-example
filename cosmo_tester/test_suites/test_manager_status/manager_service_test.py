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

from cosmo_tester.framework.testenv import TestCase
from fabric.api import env, reboot


class RebootManagerTest(TestCase):
    def _reboot_server(self):
        env.update({
            'user': self.env.managment_user_name,
            'key_filename': self.env.management_key_path,
            'host_string': self.env.management_ip,
        })
        reboot()

    def _get_undefined_services(self):
        return [each.display_name for each in self.status if each.name is None]

    def _get_stopped_services(self):
        return [each.display_name for each in self.status
                if each and not each.instances]

    def setUp(self, *args, **kwargs):
        super(RebootManagerTest, self).setUp(*args, **kwargs)
        self.status = self.env.rest_client.list_services()

    def test_00_pre_reboot(self):
        undefined = self._get_undefined_services()
        self.assertEqual(undefined, [], 'undefined services: {0}'.format(
                                        ','.join(undefined)))
        stopped = self._get_stopped_services()
        self.assertEqual(stopped, [], 'stopped services: {0}'.format(
                                      ','.join(stopped)))

    def test_01_during_reboot(self):
            pre_reboot_status = self.status
            self._reboot_server()
            post_reboot_status = self.env.rest_client.list_services()

            self.assertEqual(len(pre_reboot_status), len(post_reboot_status),
                             "number of jobs before reboot isn\'t equal to \
                              number of jobs after reboot")

            zipped = zip(pre_reboot_status, post_reboot_status)
            for pre, post in zipped:
                self.assertEqual(pre.name, post.name,
                                 'pre and post reboot status is not equal: {0} \
                                  \n {1}'.format(pre.name, post.name))

    def test_02_post_reboot(self):
        undefined = self._get_undefined_services()
        self.assertEqual(undefined, [], 'undefined services: {0}'.format(
                                        ','.join(undefined)))
        stopped = self._get_stopped_services()
        self.assertEqual(stopped, [], 'stopped services: {0}'.format(
                                      ','.join(stopped)))
