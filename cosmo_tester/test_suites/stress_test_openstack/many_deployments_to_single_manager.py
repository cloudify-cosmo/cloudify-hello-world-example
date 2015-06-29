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

import json
import time

import fabric.api

from cloudify_rest_client.executions import Execution

from cosmo_tester.framework.test_cases import MonitoringTestCase


def limit_dpoints(num):
    return float("{0:.3f}".format(num))


def num(s):
    return int(s)


class ManyDeploymentsTest(MonitoringTestCase):

    def wait_until_all_deployment_executions_end(self, deployment_id):
        while len([execution for execution in self.client.executions.list(
                deployment_id=deployment_id)
                if execution["status"] not in Execution.END_STATES]) > 0:
                        time.sleep(1)
        return

    def many_deployments_stress_test(self):
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

    def get_manager_cpu_usage(self):
        self.logger.info('get_manager_memory_total with ip {0}'
                         .format(self.env.management_ip))
        return (fabric.api.run(
            'top -bn1 | grep \"Cpu(s)\" | \
           sed \"s/.*, *\([0-9.]*\)%* id.*/\1/\" | \
           awk \'{print 100 - $1\"%\"}\''))

    def get_manager_memory_available(self):
        self.logger.info('get_manager_memory_available with ip {0}'
                         .format(self.env.management_ip))
        free = int(fabric.api.run(
            'free -t -m | egrep Mem | awk \'{print $4}\''))
        cache = int(fabric.api.run(
            'free -t -m | egrep buffers | awk \'{print $4}\' | sed -n 2p'))
        return cache + free

    def get_manager_memory_total(self):
        self.logger.info('get_manager_memory_total with ip {0}'
                         .format(self.env.management_ip))
        return int(fabric.api.run(
            'free -t -m | egrep Mem | awk \'{print $2}\''))

    def get_manager_disk_total(self):
        self.logger.info('get_manager_disk_total with ip {0}'
                         .format(self.env.management_ip))
        return int(
            str(fabric.api.run(
                'sudo docker exec cfy df -k | grep /dev/vdc1 | '
                'awk \'{print $2}\'')).replace(
                "sudo: unable to resolve host cloudify-manager-server", ""))

    def get_manager_disk_available(self):
        self.logger.info('get_manager_disk_available with ip {0}'
                         .format(self.env.management_ip))
        return int(
            str(fabric.api.run(
                'sudo docker exec cfy df -k | grep /dev/vdc1 | '
                'awk \'{print $4}\'')).replace(
                "sudo: unable to resolve host cloudify-manager-server", ""))

    def get_number_of_total_active_nodes(self):
        return len((self.client.nodes.list(
            _include=["deploy_number_of_instances",
                      "deployment_id"])))

    def get_number_of_active_nodes_per_deployment(self, deployment_id):
        return len((self.client.nodes.list(
            deployment_id=deployment_id,
            _include=["deploy_number_of_instances",
                      "deployment_id"])))

    def _end_test(self, report):
        self.logger.info(json.dumps(report, indent=2))
        return report

    def _run(self):
        number_of_deployments = 1
        self.init_fabric()
        blueprint_path = self.copy_blueprint('mocks')
        self.blueprint_yaml = blueprint_path / 'single-node-blueprint.yaml'
        manager_disk_space_total = self.get_manager_disk_total()
        manager_memory_total = self.get_manager_memory_total()
        prev_manager_memory_available = self.get_manager_memory_available()
        prev_space_available = self.get_manager_disk_available()
        self.upload_blueprint(blueprint_id=self.test_id)
        deployment_dict = {"deployment_number": 0,
                           "manager_memory_available":
                               prev_manager_memory_available,
                           "manager_memory_total":
                               manager_memory_total,
                           "manager_cpu_usage":
                               self.get_manager_cpu_usage(),
                           "manager_disk space_available":
                               prev_space_available,
                           "manager_disk_space_total":
                               manager_disk_space_total}
        deployments_dict = {0: deployment_dict}
        try:
            while True:
                start_time = time.time()
                self.create_deployment(blueprint_id=self.test_id,
                                       deployment_id=self.test_id+str(
                                           number_of_deployments),
                                       inputs='')
                self.wait_until_all_deployment_executions_end(
                    deployment_id=self.test_id+str(number_of_deployments))
                end_create_deployment_time = time.time()
                start_install_time = time.time()
                self.client.executions.start(
                    deployment_id=self.test_id+str(number_of_deployments),
                    workflow_id="install")
                self.wait_until_all_deployment_executions_end(
                    deployment_id=self.test_id+str(number_of_deployments))
                end_execute_install_time = time.time()
                self.logger.debug(
                    "time to create deployment number {0} : {1}".format(
                        number_of_deployments,
                        end_create_deployment_time - start_time))
                self.logger.debug(
                    "time to execute install number {0} : {1}".format(
                        number_of_deployments,
                        end_execute_install_time - start_install_time))
                manager_disk_space_available = \
                    self.get_manager_disk_available()
                manager_memory_available = self.get_manager_memory_available()
                number_of_active_nodes = \
                    self.get_number_of_total_active_nodes()
                number_of_my_active_nodes = \
                    self.get_number_of_active_nodes_per_deployment(
                        deployment_id=self.test_id+str(number_of_deployments))
                deployment_dict = {"deployment_number": number_of_deployments,
                                   "number_of_my_active_nodes":
                                       number_of_my_active_nodes,
                                   "nodes_active": number_of_active_nodes,
                                   "time_to_create_deployment": limit_dpoints(
                                       end_create_deployment_time -
                                       start_time),
                                   "time_to_install":
                                       limit_dpoints(
                                           end_execute_install_time -
                                           start_install_time),
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
                                   "manager_cpu_usage":
                                       self.get_manager_cpu_usage(),
                                   "disk_change_in_deployment":
                                       prev_space_available -
                                       manager_disk_space_available}
                prev_space_available = manager_disk_space_available
                prev_manager_memory_available = manager_memory_available
                self.logger.debug(deployment_dict)
                deployments_dict.update(
                    {number_of_deployments: deployment_dict})
                number_of_deployments += 1
                self.logger.debug(deployments_dict)
            for i in range(1, number_of_deployments+1):
                self.wait_until_all_deployment_executions_end(
                    deployment_id=self.test_id+str(i))
            self._end_test(deployments_dict)
        except Exception as e:
            print e
            self._end_test(deployments_dict)
