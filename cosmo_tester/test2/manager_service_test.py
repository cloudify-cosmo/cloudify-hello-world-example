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
import json
from urllib2 import urlopen
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
        return [key for key, val in self.status.iteritems() if val is None]

    def _get_stopped_services(self):
        return [key for key, val in self.status.iteritems()
                if val and not val['instances']]

    def _get_status(self):
        out = urlopen("http://{0}:8100/status".format(self.env.management_ip))
        return json.load(out)

    def setUp(self, *args, **kwargs):
        super(RebootManagerTest, self).setUp(*args, **kwargs)
        out = urlopen("http://{0}:8100/status".format(self.env.management_ip))
        self.status = json.load(out)

    def test_00_pre_reboot(self):
        undefined = self._get_undefined_services()
        self.assertEqual(undefined, [], 'undefined services: {0}'
                         .format(','.join(undefined)))
        stopped = self._get_stopped_services()
        self.assertEqual(stopped, [], 'stopped services: {0}'
                         .format(','.join(stopped)))

    def test_01_during_reboot(self):
            pre_reboot_status = self.status
            self._reboot_server()
            self.status = self._get_status()
            self.assertEqual(pre_reboot_status, self.status,
                             'pre and post reboot status is not equal')

    def test_01_post_reboot(self):
        undefined = self._get_undefined_services()
        self.assertEqual(undefined, [], 'undefined services: {0}'
                         .format(','.join(undefined)))
        stopped = self._get_stopped_services()
        self.assertEqual(stopped, [], 'stopped services: {0}'
                         .format(','.join(stopped)))
