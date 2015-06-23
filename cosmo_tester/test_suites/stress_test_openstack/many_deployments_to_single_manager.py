########
# Copyright (c) 2015 GigaSpaces Technologies Ltd. All rights reserved
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

import time
from time import sleep
import fabric.api
import json

from cosmo_tester.framework.test_cases import MonitoringTestCase


def num(s):
    return int(s)


class ManyDeploymentsTest(MonitoringTestCase):

    def many_deployments_test(self):
        self._run()

    def init_fabric(self):
        manager_keypath = self.env._config_reader.management_key_path
        fabric_env = fabric.api.env
        fabric_env.update({
            'timeout': 30,
            'user': 'ubuntu',
            'key_filename': manager_keypath,
            'host_string': self.env.management_ip,
            })

    def get_manager_memory_available(self):
        self.logger.info('get_manager_memory_available with ip {0}'
                         .format(self.env.management_ip))
        return int(fabric.api.run(
            'free -t -m | egrep Mem | awk \'{print $4}\''))

    def get_manager_memory_total(self):
        self.logger.info('get_manager_memory_total with ip {0}'
                         .format(self.env.management_ip))
        return int(fabric.api.run(
            'free -t -m | egrep Mem | awk \'{print $2}\''))

    def get_manager_disk_total(self):
        self.logger.info('get_manager_disk_total with ip {0}'
                         .format(self.env.management_ip))
        return int(fabric.api.run(
            'df -k /tmp | tail -1 | awk \'{print $2}\''))

    def get_manager_disk_available(self):
        self.logger.info('get_manager_disk_available with ip {0}'
                         .format(self.env.management_ip))
        return int(fabric.api.run(
            'df -k /tmp | tail -1 | awk \'{print $4}\''))

    def _run(self):
        number_of_deployments = 3
        self.init_fabric()
        blueprint_path = self.copy_blueprint('mocks')
        self.blueprint_yaml = blueprint_path / 'single-node-blueprint.yaml'
        manager_disk_space_total = self.get_manager_disk_total()
        manager_memory_total = self.get_manager_memory_total()
        prev_manager_memory_available = self.get_manager_memory_available()
        prev_space_available = self.get_manager_disk_available()
        self.upload_blueprint(blueprint_id=self.test_id)
        deployment_dict = {"deployment number": 0,
                           "manager_memory_available":
                               prev_manager_memory_available,
                           "manager_memory_total":
                               manager_memory_total,
                           "manager_disk space_available":
                               prev_space_available,
                           "manager_disk_space_total":
                               manager_disk_space_total}
        deployments_dict = {0: deployment_dict}
        for i in range(1, number_of_deployments+1):
            start_time = time.time()
            self.create_deployment(blueprint_id=self.test_id,
                                   deployment_id=self.test_id+str(i),
                                   inputs='')
            start_install_time = time.time()
            while True:
                try:
                    self.client.executions.start(
                        deployment_id=self.test_id+str(i),
                        workflow_id="install")
                    start_install_time = time.time()
                except Exception as e:
                    sleep(1)
                    end_create_deployment_time = time.time()
                    self.logger.error(e)
                    continue
                break
            self.logger.debug(
                "time to create deployment number {0} : {1}".format(
                    i, end_create_deployment_time - start_time))

            end_execute_install_time = time.time()
            self.logger.debug(
                "time to execute install number {0} : {1}".format(
                    i, end_execute_install_time - start_install_time))
            manager_disk_space_available = self.get_manager_disk_available()
            manager_memory_available = self.get_manager_memory_available()

            deployment_dict = {"deployment_number": i,
                               "nodes_active": str(self.client.nodes.list(
                                   _include=["deploy_number_of_instances",
                                             "deployment_id"])),
                               "time_to_create_deployment":
                                   end_create_deployment_time - start_time,
                               "time_to_install":
                                   end_execute_install_time -
                                   start_install_time,
                               "manager_memory_available":
                                   manager_memory_available,
                               "manager_memory_total":
                                   manager_memory_total,
                               "manager_disk_space_available":
                                   manager_disk_space_available,
                               "manager_disk_space_total":
                                   manager_disk_space_total,
                               "memory_change_in_deployment":
                                   prev_manager_memory_available -
                                   manager_memory_available,
                               "disk_change_in_deployment":
                                   prev_space_available -
                                   manager_disk_space_available}
            prev_space_available = manager_disk_space_available
            prev_manager_memory_available = manager_memory_available
            self.logger.debug(deployment_dict)
            deployments_dict.update({i: deployment_dict})
        for i in range(1, number_of_deployments+1):
            executions_list = self.client.executions.list(
                deployment_id=self.test_id+str(i))
            while executions_list != []:
                executions_list = self.client.executions.list(
                    deployment_id=self.test_id+str(i))
                executions_list = \
                    [execution for execution in executions_list if
                     execution["status"] == "started"]
                sleep(1)
        self.logger.info(json.dumps(deployments_dict, indent=2))
