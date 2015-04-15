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
import urllib
from time import sleep, time

from fabric.api import env, reboot

from cosmo_tester.framework.testenv import TestCase
from cosmo_tester.framework.util import get_actual_keypath


class RebootManagerTest(TestCase):
    def _reboot_server(self):
        env.update({
            'user': self.env.management_user_name,
            'key_filename': get_actual_keypath(self.env,
                                               self.env.management_key_path),
            'host_string': self.env.management_ip,
        })
        reboot()

    def _get_undefined_services(self):
        return [each['display_name']
                for each in self.status if 'name' not in each]

    def _get_service_names(self):
        return [each['display_name']
                for each in self.status]

    def _get_stopped_services(self):
        return [each['display_name'] for each in self.status
                if each and 'instances' not in each]

    def setUp(self, *args, **kwargs):
        super(RebootManagerTest, self).setUp(*args, **kwargs)
        self.status = self.client.manager.get_status()['services']

    def is_docker_manager(self):
        services = self._get_service_names()
        if services.__contains__('ssh'):
            return False
        return True

    def test_00_pre_reboot(self):
        is_docker_manager = self.is_docker_manager()
        if not is_docker_manager:
            undefined = self._get_undefined_services()
            self.assertEqual(undefined, [],
                             'undefined services: {0}'
                             .format(','.join(undefined)))
        stopped = self._get_stopped_services()
        self.assertEqual(stopped, ['Cloudify UI'], 'stopped services: {0}'
                         .format(','.join(stopped)))

    def test_01_during_reboot(self):
            is_docker_manager = self.is_docker_manager()
            pre_reboot_status = self.status
            self._reboot_server()
            self._wait_for_management(self.env.management_ip, timeout=180)
            post_reboot_status = self.client.manager.get_status()['services']

            self.assertEqual(len(pre_reboot_status), len(post_reboot_status),
                             "number of jobs before reboot isn\'t equal to \
                              number of jobs after reboot")

            zipped = zip(pre_reboot_status, post_reboot_status)
            for pre, post in zipped:
                if is_docker_manager:
                    pre_display_name = pre.get('display_name')
                    post_display_name = pre.get('display_name')
                    self.assertEqual(pre_display_name, post_display_name,
                                     'pre and post reboot service names '
                                     'should be identical')
                    # compare all service states except UI which is absent from
                    # the non-commercial distro
                    if pre_display_name != 'Cloudify UI':
                        self.assertEqual(pre.get('instances')[0].get('state'),
                                         post.get('instances')[0].get('state'),
                                         'pre and post reboot status is not '
                                         'equal:{0}\n{1}'
                                         .format(pre.get('display_name'),
                                                 post.get('display_name')))
                else:
                    self.assertEqual(pre.get('name'), post.get('name'),
                                     'pre and post reboot status is not equal:'
                                     '{0}\n {1}'.format(pre.get('name'),
                                                        post.get('name')))

    def _wait_for_management(self, ip, timeout, port=80):
        """ Wait for url to become available
            :param ip: the manager IP
            :param timeout: in seconds
            :param port: port used by the rest service.
            :return: True of False
        """
        validation_url = 'http://{0}:{1}/blueprints'.format(ip, port)

        end = time() + timeout

        while end - time() >= 0:
                try:
                    status = urllib.urlopen(validation_url).getcode()
                    if status == 200:
                        return True
                except IOError:
                    sleep(5)

        return False

    def test_02_post_reboot(self):
        is_docker_manager = self.is_docker_manager()
        if not is_docker_manager:
            undefined = self._get_undefined_services()
            self.assertEqual(undefined, [],
                             'undefined services: {0}'
                             .format(','.join(undefined)))
        stopped = self._get_stopped_services()
        self.assertEqual(stopped, ['Cloudify UI'], 'stopped services: {0}'
                         .format(','.join(stopped)))
