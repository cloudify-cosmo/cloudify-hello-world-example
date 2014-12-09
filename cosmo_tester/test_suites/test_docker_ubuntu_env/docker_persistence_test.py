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

# a test for data persistence. We start a new cloudify manager, then kill the
# main container and restart it using the data container and see that we can
# still deploy the nodecellar app on it.

from cosmo_tester.framework.util import YamlPatcher
from cosmo_tester.test_suites.test_blueprints import nodecellar_test
import fabric.api
from time import sleep, time
import urllib


class DockerNodeCellarTest(nodecellar_test.NodecellarAppTest):

    def test_docker_persistence_nodecellar(self):
        self.init_fabric()
        restarted = self.restart_container()
        if not restarted:
            raise AssertionError('Failed restarting container. Test failed.')

        self._test_nodecellar_impl('openstack-blueprint.yaml',
                                   self.env.ubuntu_trusty_image_name,
                                   self.env.flavor_name)

    def modify_blueprint(self, image_name, flavor_name):
        with YamlPatcher(self.blueprint_yaml) as patch:
            vm_props_path = 'node_types.vm_host.properties'
            # Add required docker param. See CFY-816
            patch.merge_obj('{0}.cloudify_agent.default'
                            .format(vm_props_path), {
                                'home_dir': '/home/ubuntu'
                            })
            vm_type_path = 'node_types.vm_host.properties'
            patch.merge_obj('{0}.server.default'.format(vm_type_path), {
                'image_name': image_name,
                'flavor_name': flavor_name
            })
            # Use ubuntu trusty 14.04 as agent machine
            patch.merge_obj('{0}.server.default'.format(vm_props_path), {
                'image': self.env.ubuntu_trusty_image_id
            })

    def init_fabric(self):
        manager_keypath = self.env._config_reader.management_key_path
        fabric_env = fabric.api.env
        fabric_env.update({
            'timeout': 30,
            'user': 'ubuntu',
            'key_filename': manager_keypath,
            'host_string': self.env.management_ip,
        })

    def restart_container(self):
        self.logger.info('acquiring instance private IP')
        private_ip = fabric.api.run('ip addr | grep \'eth0\' -A0 | tail -n1 '
                                    '| awk \'{print $2}\' | cut -f1  -d\'/\'')

        self.logger.info('terminating cloudify services container')
        fabric.api.run('sudo docker rm -f cfy')

        start_cmd = 'sudo docker run -t -v ~/:/root ' \
                    '--volumes-from data -p 80:80 -p 5555:5555 ' \
                    '-p 5672:5672 -p 53229:53229 -p 8100:8100 ' \
                    '-p 9200:9200 -e MANAGEMENT_IP={0} ' \
                    '--restart=always --name=cfy -d ' \
                    'cloudify:latest /sbin/my_init' \
                    .format(private_ip)

        self.logger.info('starting new cloudify container.. running command:' +
                         start_cmd)
        started = fabric.api.run(start_cmd)
        if not started:
            return False
        self._wait_for_management(self.env.management_ip, 120)
        return True

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
                print 'Manager not accessible. retrying in 5 seconds.'
            sleep(5)

        return False
