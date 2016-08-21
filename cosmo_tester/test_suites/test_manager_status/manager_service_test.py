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

import os
import time
import json
import urllib
import tarfile
import tempfile
from contextlib import closing

import sh
import fabric.api
from fabric.api import run, sudo
from fabric.contrib.files import exists, sed

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
        return run('sudo shutdown -r +1')

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
        self.logger.info('Testing `cfy logs download`')
        try:
            self.cfy.logs.download(output_path=tmp_log_archive)
            with closing(tarfile.open(name=tmp_log_archive)) as tar:
                files = [f.name for f in tar.getmembers()]
                self.assertIn('cloudify/journalctl.log', files)
                self.assertIn('cloudify/nginx/cloudify.access.log', files)
                self.logger.info('Success!')
        finally:
            os.remove(tmp_log_archive)

        self.logger.info('Testing `cfy logs backup`')
        self.cfy.logs.backup(verbose=True)
        try:
            self.assertTrue(
                sudo('tar -xzvf /var/log/cloudify-manager-logs_*').succeeded)
            self.logger.info('Success!')
        finally:
            # Clear the newly created backups
            sudo('rm /var/log/cloudify-manager-logs_*')

        self.logger.info('Testing `cfy logs purge`')
        self.cfy.logs.purge(force=True)
        self.assertTrue(run(
            '[ ! -s /var/log/cloudify/nginx/cloudify.access.log ]',).succeeded)
        self.logger.info('Success!')

    def test_04_tmux_session(self):
        self._update_fabric_env()
        self.logger.info('Test list without tmux installed...')
        try:
            self.cfy.ssh(list_sessions=True)
        except sh.ErrorReturnCode_1 as ex:
            self.assertIn('tmux executable not found on manager', ex.stdout)

        self.logger.info('Installing tmux...')
        sudo('yum install tmux -y')

        self.logger.info('Test listing sessions when non are available..')
        output = self.cfy.ssh(list_sessions=True).stdout.splitlines()[-1]
        self.assertIn('No sessions are available', output)
        sudo('yum remove tmux -y')

        self.logger.info('Test running ssh command...')
        self.cfy.ssh(command='echo yay! > /tmp/ssh_test_output_file')
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
        run('rm {0}'.format(remote_path))

    def test_05_no_es_clustering(self):
        """Tests that when bootstrapping we don't cluster two elasticsearch
        nodes.

        This test mainly covers the use case where a user bootstraps two
        managers on the same network.

        The test runs two nodes on the same machine. If they're not clustered,
        two nodes on different servers will definitely not be clustered.
        """
        self._update_fabric_env()

        self.logger.info('Duplicating elasticsearch config...')
        sudo('mkdir /etc/es_test')
        sudo('cp /etc/elasticsearch/elasticsearch.yml /etc/es_test/es.yml')

        self.logger.info('Replacing ES REST port for second node...')
        sed('/etc/es_test/es.yml', 'http.port: 9200', 'http.port: 9201',
            use_sudo=True)
        self.logger.info('Running second node...')
        es_cmd = "/usr/share/elasticsearch/bin/elasticsearch \
            -Des.pidfile='/var/run/elasticsearch/es_test.pid' \
            -Des.default.path.home='/usr/share/elasticsearch' \
            -Des.default.path.logs='/var/log/elasticsearch' \
            -Des.default.path.data='/var/lib/elasticsearch' \
            -Des.default.config='/etc/es_test/es.yml' \
            -Des.default.path.conf='/etc/es_test'"
        sudo('nohup {0} >& /dev/null < /dev/null &'.format(es_cmd),
             pty=False)
        # this is a good approximation of how much
        # time it will take to load the node.
        time.sleep(20)

        node1_url = 'http://localhost:9200/_nodes'
        node2_url = 'http://localhost:9201/_nodes'

        def get_node_count(url):
            # in case the node has not be loaded yet, this will retry.
            curl_nodes = 'curl --retry 10 --show-error {0}'.format(url)
            return len(json.loads(run(curl_nodes).stdout)['nodes'])

        self.logger.info(
            'Verifying that both nodes are running but not clustered...')
        self.assertEqual(get_node_count(node1_url), 1)
        self.assertEqual(get_node_count(node2_url), 1)

    def test_06_logrotation(self):
        """Tests logrotation configuration on the manager.

        This goes over some of the logs but for each of services
        and performs logrotation based on the manager blueprint's provided
        logrotate configuration. It then validates that logrotation occurs.
        """
        self._update_fabric_env()
        logs_dir = '/var/log/cloudify'
        test_log_files = [
            'elasticsearch/elasticsearch.log',
            'influxdb/log.txt',
            'mgmtworker/logs/test.log',
            'rabbitmq/rabbit@cloudifyman.log',
            'rest/cloudify-rest-service.log',
            'logstash/logstash.log',
            'nginx/cloudify.access.log',
            'riemann/riemann.log',
            'webui/backend.log'
        ]
        # the mgmtworker doesn't create a log file upon loading so we're
        # generating one for him.
        sudo('touch /var/log/cloudify/mgmtworker/logs/test.log')

        self.logger.info('Cancelling date suffix on rotation...')
        sed('/etc/logrotate.conf', 'dateext', '#dateext', use_sudo=True)
        for rotation in range(1, 9):
            for log_file in test_log_files:
                full_log_path = os.path.join(logs_dir, log_file)
                self.logger.info('fallocating 101M in {0}...'.format(
                    full_log_path))
                sudo('fallocate -l 101M {0}'.format(full_log_path))
                self.logger.info('Running cron.hourly to apply rotation...')
                sudo('run-parts /etc/cron.hourly')
                rotated_log_path = full_log_path + '.{0}'.format(rotation)
                compressed_log_path = rotated_log_path + '.gz'
                with fabric.api.settings(warn_only=True):
                    if rotation == 8:
                        self.logger.info(
                            'Verifying overshot rotation did not occur: {0}...'
                            .format(compressed_log_path))
                        self.assertFalse(exists(compressed_log_path))
                    elif rotation == 1:
                        self.logger.info(
                            'Verifying rotated log exists: {0}...'.format(
                                rotated_log_path))
                        self.assertTrue(exists(rotated_log_path))
                    else:
                        self.logger.info(
                            'Verifying compressed log exists: {0}...'.format(
                                compressed_log_path))
                        self.assertTrue(exists(compressed_log_path))
