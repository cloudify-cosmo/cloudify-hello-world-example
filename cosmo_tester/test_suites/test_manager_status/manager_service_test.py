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
import time
import tempfile
import os
import tarfile
from contextlib import closing

import fabric.api
import sh

from cosmo_tester.framework.testenv import TestCase
from cosmo_tester.framework.util import get_actual_keypath


class RebootManagerTest(TestCase):

    def _update_fabric_env(self):
        fabric_env = fabric.api.env
        fabric_env.update({
            'timeout': 30,
            'user': self.env.centos_7_image_user,
            'key_filename': get_actual_keypath(
                self.env, self.env.management_key_path),
            'host_string': self.env.management_ip
        })

    def _reboot_server(self):
        self._update_fabric_env()
        return fabric.api.run('sudo shutdown -r +1')

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
        self.assertEqual(stopped, [], 'stopped services: {0}'
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
        """Wait for url to become available

        :param ip: the manager IP
        :param timeout: in seconds
        :param port: port used by the rest service.
        :return: True of False
        """
        validation_url = 'http://{0}:{1}/blueprints'.format(ip, port)

        end = time.time() + timeout

        while end - time.time() >= 0:
                try:
                    status = urllib.urlopen(validation_url).getcode()
                    if status == 200:
                        return True
                except IOError:
                    time.sleep(5)

        return False

    def test_02_post_reboot(self):
        is_docker_manager = self.is_docker_manager()
        if not is_docker_manager:
            undefined = self._get_undefined_services()
            self.assertEqual(undefined, [],
                             'undefined services: {0}'
                             .format(','.join(undefined)))
        stopped = self._get_stopped_services()
        self.assertEqual(stopped, [], 'stopped services: {0}'
                         .format(','.join(stopped)))

    def test_03_cfy_logs(self):
        self._update_fabric_env()

        fd, tmp_log_archive = tempfile.mkstemp()
        os.close(fd)
        self.logger.info('Testing `cfy logs get`')
        try:
            self.cfy.get_logs(destination_path=tmp_log_archive)
            with closing(tarfile.open(name=tmp_log_archive)) as tar:
                files = [f.name for f in tar.getmembers()]
                self.assertIn('cloudify/journalctl.log', files)
                self.assertIn('cloudify/nginx/cloudify.access.log', files)
                self.logger.info('Success!')
        finally:
            os.remove(tmp_log_archive)

        self.logger.info('Testing `cfy logs backup`')
        self.cfy.backup_logs()
        self.assertTrue(fabric.api.sudo(
            'tar -xzvf /var/log/cloudify-manager-logs_*').succeeded)
        self.logger.info('Success!')

        self.logger.info('Testing `cfy logs purge`')
        self.cfy.purge_logs()
        self.assertTrue(fabric.api.run(
            '[ ! -s /var/log/cloudify/nginx/cloudify.access.log ]',).succeeded)
        self.logger.info('Success!')

    def test_04_tmux_session(self):
        self._update_fabric_env()
        self.logger.info('Test list without tmux installed...')
        try:
            self.cfy.ssh_list()
        except sh.ErrorReturnCode_1 as ex:
            self.assertIn('tmux executable not found on Manager', str(ex))

        self.logger.info('Installing tmux...')
        fabric.api.sudo('yum install tmux -y')

        self.logger.info('Test listing sessions when non are available..')
        output = self.cfy.ssh_list().stdout.splitlines()[-1]
        self.assertIn('No sessions are available.', output)
        fabric.api.sudo('yum remove tmux -y')

        self.logger.info('Test running ssh command...')
        self.cfy.ssh_run_command('echo yay! > /tmp/ssh_test_output_file')
        self._check_remote_file_content('/tmp/ssh_test_output_file', 'yay!')

    def _check_remote_file_content(self, remote_path, desired_content):
        fd, temp_file = tempfile.mkstemp()
        os.close(fd)
        try:
            fabric.api.get(remote_path, temp_file)
            with open(temp_file) as f:
                self.assertEqual(f.read().rstrip('\n\r'), desired_content)
        finally:
            os.remove(temp_file)
        fabric.api.run('rm {0}'.format(remote_path))
