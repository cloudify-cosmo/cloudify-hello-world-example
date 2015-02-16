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

# a test for container management and recovery. The docker container is managed
# by docker and should be restarted automatically upon failure.

import urllib
import json
from time import sleep, time

import fabric.api

from cosmo_tester.test_suites.test_blueprints import nodecellar_test


class DockerRecoveryTest(nodecellar_test.NodecellarAppTest):

    def test_docker_recovery(self):
        context_before = self.get_provider_context()
        self.init_fabric()
        self.restart_vm()
        down = self._wait_for_management_state(self.env.management_ip, 180,
                                               state=False)
        self.assertTrue(down, 'Management VM {} failed to terminate'
                              .format(self.env.management_ip))
        started = self._wait_for_management_state(self.env.management_ip, 180)
        self.assertTrue(started, 'Cloudify docker service container failed'
                                 ' to start after reboot. Test failed.')
        context_after = self._wait_for_provider_context(180)

        self.assertEqual(json.load(context_before),
                         json.load(context_after),
                         msg='Provider context should be identical to what it '
                             'was prior to reboot.')

    def get_provider_context(self):
        context_url = 'http://{0}/provider/context'\
                      .format(self.env.management_ip)
        return urllib.urlopen(context_url)

    def init_fabric(self):
        manager_keypath = self.env._config_reader.management_key_path
        fabric_env = fabric.api.env
        fabric_env.update({
            'timeout': 30,
            'user': 'ubuntu',
            'key_filename': manager_keypath,
            'host_string': self.env.management_ip,
        })

    def restart_vm(self):
        self.logger.info('Restarting machine with ip {0}'
                         .format(self.env.management_ip))
        return fabric.api.run('sudo shutdown -r now')

    def _wait_for_provider_context(self, timeout):
        end = time() + timeout
        while end - time() >= 0:
            context = self.get_provider_context()
            if context:
                return context
            else:
                self.logger.info('Provider context is empty. sleeping for 2 '
                                 'seconds...')
                sleep(2)

        raise RuntimeError('Failed waiting for provider context. '
                           'waited {0} seconds'.format(timeout))

    def _wait_for_management_state(self, ip, timeout, port=80, state=True):
        """ Wait for management to reach state
            :param ip: the manager IP
            :param timeout: in seconds
            :param port: port used by the rest service.
            :param state: management state, true for running, else false.
            :return: True of False
        """
        validation_url = 'http://{0}:{1}/blueprints'.format(ip, port)

        end = time() + timeout

        while end - time() >= 0:
            try:
                status = urllib.urlopen(validation_url).getcode()
                if status == 200 and state:
                    return True
                if not state:
                    if status == 200:
                        self.logger.info('Manager is accessible. '
                                         'retrying in 2 seconds.')
                    else:
                        return True

            except IOError:
                if not state:
                    return True
                self.logger.info('Manager not accessible. '
                                 'retrying in 2 seconds.')
            sleep(2)

        return False

    def get_inputs(self):

        return {
            'image': self.env.ubuntu_image_id,
            'flavor': self.env.small_flavor_id,
            'agent_user': 'ubuntu'
        }
