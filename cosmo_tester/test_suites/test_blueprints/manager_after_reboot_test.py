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
from time import sleep, time

import fabric.api
from cloudify_rest_client import exceptions

from cosmo_tester.test_suites.test_blueprints import hello_world_bash_test


class ManagerAfterRebootTest(hello_world_bash_test.AbstractHelloWorldTest):

    def test_manager_after_reboot(self):
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

        self.logger.info('provider context before restart is : {0}'
                         .format(context_before))
        self.logger.info('provider context after restart is : {0}'
                         .format(context_after))
        self.assertEqual(context_before,
                         context_after,
                         msg='Provider context is not the same after restart')
        inputs = {
            'agent_user': self.env.centos_7_image_user,
            'image': self.env.centos_7_image_name,
            'flavor': self.env.flavor_name
        }
        self._run(inputs=inputs)

    def get_provider_context(self):
        return self.client.manager.get_context()

    def init_fabric(self):
        manager_keypath = self.env._config_reader.management_key_path
        fabric_env = fabric.api.env
        self.logger.info('Fabric env: user={0}, key={1}, host={2}'.format(
            self.env.centos_7_image_user,
            manager_keypath,
            self.env.management_ip))
        fabric_env.update({
            'timeout': 30,
            'user': self.env.centos_7_image_user,
            'key_filename': manager_keypath,
            'host_string': self.env.management_ip,
        })

    def restart_vm(self):
        self.logger.info('Restarting machine with ip {0}'
                         .format(self.env.management_ip))
        return fabric.api.run('sudo shutdown -r +1')

    def _wait_for_provider_context(self, timeout):
        end = time() + timeout
        while end - time() >= 0:
            try:
                context = self.get_provider_context()
                if context:
                    return context
                self.logger.info('Provider context is empty. sleeping for 2 '
                                 'seconds...')
                sleep(2)
            except exceptions.CloudifyClientError as e:
                # might be an elastic search issue (
                # NoShardAvailableActionException)
                self.logger.warning(str(e))
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
