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
from random import randint
import fabric.api
import os

from retrying import retry
from threading import Thread

from cosmo_tester.framework.test_cases import MonitoringTestCase
from cloudify_rest_client.executions import Execution

DEFAULT_MAX_THREADS = 25
DEFAULT_EXECUTE_TIMEOUT = 30
DEFAULT_TOTAL_TIMEOUT = 300
MINIMUM_INSTALLED_TO_PASS = 10
TOTAL_TEST_TIME = 1800


class MultiDeploymentParallelExecutionTest(MonitoringTestCase):
    """uploads blueprints, creates deployments, and executes install
       in a randomized order and in parallel(threads) until a significant
       amount of errors are received as to declare we reached a limit."""

    def check_all_installed_deployments_installed_successfully(self):
        for counter in range(0, self.installed):
            deployment_id = self.test_id+str(counter)
            if len([execution for execution in self.client.executions.list(
                    deployment_id=deployment_id)
                    if execution["status"] in Execution.FAILED]) > 0:
                ex = Exception("failed workflow on deployment {0}".format(
                    deployment_id))
                raise ex

    def execute_install_on_all_deployments(self):
        try:
            for counter in range(0, self.installed):
                deployment_id = self.test_id+str(counter)
                self.execute_install(deployment_id=deployment_id)
        except Exception as e:
            self.logger.error(e)
            self.logger.error(
                self.client.executions.list(deployment_id=deployment_id))

    def get_manager_metrics(self):
        while time.time() - self.time_started < TOTAL_TEST_TIME:
            manager_disk_space_available = \
                self.get_manager_disk_available()
            manager_memory_available = \
                self.get_manager_memory_available()
            number_of_active_nodes = \
                self.get_number_of_total_active_nodes()
            self.nodes_active = number_of_active_nodes
            state = {"manager_disk_space_available":
                     manager_disk_space_available,
                     "manager_memory_available":
                         manager_memory_available,
                     "number_of_active_nodes":
                         number_of_active_nodes,
                     "blueprints": self.blueprints,
                     "deployments": self.deployments,
                     "installed": self.installed,
                     "manager_cpu_usage":
                         self.get_manager_cpu_usage()
                     }
            self.state_dict.update({
                time.time(): state})
            self.logger.info("current_state: {0}".format(state))
            time.sleep(5)
            self.logger.info(
                "number_of_active_threads {0}".format(self.active_threads))

    def run_thread_with_this(self, func, args, append=True):
        self.active_threads = self.active_threads + 1
        t = Thread(target=func,
                   args=args or [])
        t.start()
        if append:
            self.threads.append([t, [func, args]])
        return t

    def wait_for_all_threads_to_finish(self):
        for x in self.threads:
            self.logger.info('waiting for {0} threads'.format(
                len(self.threads)))
            x[0].join()

    def wait_until_all_deployment_executions_end(self, deployment_id):
        start_time = time.time()
        while len([execution for execution in self.client.executions.list(
                deployment_id=deployment_id)
                if execution["status"] not in Execution.END_STATES]) > 0:
            self.logger.info("waiting for executions to end on deployment {0}"
                             .format(deployment_id))
            time.sleep(1)
            if time.time() - start_time > self.execute_timeout:
                ex = Exception("Time out while waiting for executions on "
                               "deployment {0}".format(deployment_id))
                raise ex
        return

    @retry(stop_max_delay=10000,
           stop_max_attempt_number=555)
    def create_deployment_retry(
            self, params_dict):
        deployment_id = params_dict['deployment_id']
        blueprint_id = params_dict['blueprint_id']
        inputs = params_dict.get('inputs', '')
        self.logger.info("creating deployment {0}"
                         .format(deployment_id))
        result = self.create_deployment(
            blueprint_id,
            deployment_id,
            inputs
        )
        self.active_threads -= 1
        return result

    @retry(stop_max_delay=10000,
           stop_max_attempt_number=555)
    def upload_blueprint_retry(
            self,
            blueprint_id):
        self.logger.info("uploading blueprint {0}"
                         .format(blueprint_id))
        result = self.cfy.blueprints.upload(
            self.blueprint_yaml,
            blueprint_id=blueprint_id
        )
        self.active_threads -= 1
        return result

    @retry(stop_max_delay=10000,
           stop_max_attempt_number=555)
    def execute_install_retry(self,
                              deployment_id=None,
                              fetch_state=True):
        self.wait_until_all_deployment_executions_end(
            deployment_id=deployment_id)
        self.logger.info("executing install on deployment {0}"
                         .format(deployment_id))
        result = self.execute_install(deployment_id, fetch_state)
        self.active_threads -= 1
        return result

    def many_deployments_stress_test(self):
        self.stop_test = False
        self.time_started = time.time()
        self.active_threads = 0
        self.init_fabric()
        blueprint_path = self.copy_blueprint('mocks')
        self.blueprint_yaml = blueprint_path / 'empty-blueprint.yaml'
        self.blueprints = 0
        self.deployments = 0
        self.installed = 0
        self.nodes_active = 0
        self.threads = []
        manager_disk_space_total = self.get_manager_disk_total()
        manager_memory_total = self.get_manager_memory_total()
        self.state_dict = {"static_info":
                           {"manager_disk_space_total":
                            manager_disk_space_total,
                            "manager_memory_total":
                            manager_memory_total}}
        self.run_thread_with_this(
            func=self.get_manager_metrics,
            args=None, append=False)
        self.total_timeout = os.getenv("TOTAL_TIMEOUT", DEFAULT_TOTAL_TIMEOUT)
        self.execute_timeout = os.getenv("EXECUTE_TIMEOUT",
                                         DEFAULT_EXECUTE_TIMEOUT)
        self.max_threads = os.getenv("EXECUTE_TIMEOUT",
                                     DEFAULT_MAX_THREADS)
        try:
            while time.time() - self.time_started < TOTAL_TEST_TIME \
                    and self.active_threads < self.max_threads:
                operation = randint(1, 3)
                if operation == 1:
                    blueprint_name = \
                        self.test_id+str(self.blueprints)
                    self.logger.info(
                        "uploading blueprint {0} with name {1}"
                        .format(self.blueprints, blueprint_name))
                    self.blueprints = self.blueprints + 1
                    self.run_thread_with_this(
                        func=self.upload_blueprint_retry,
                        args=[blueprint_name])
                if operation == 2 and self.deployments < self.blueprints:
                    self.logger.info("creating deployment {0}"
                                     .format(self.deployments))
                    blueprint_name = \
                        str(self.test_id+str(self.deployments))
                    deployment_name = blueprint_name
                    params_dict = {"blueprint_id": blueprint_name,
                                   "deployment_id": deployment_name}
                    self.deployments = self.deployments + 1
                    self.run_thread_with_this(
                        func=self.create_deployment_retry,
                        args=[params_dict])
                if operation == 3 and self.installed < self.deployments:
                    self.logger.info("executing install on deployment {0}"
                                     .format(self.installed))
                    deployment_name = self.test_id+str(self.installed)
                    self.installed += 1
                    self.run_thread_with_this(
                        func=self.execute_install_retry,
                        args=[deployment_name])
                time.sleep(1)
        except Exception as e:
            self.logger.error(e)
        finally:
            self._end_test()

    def init_fabric(self):
        manager_keypath = self.env._config_reader.management_key_path
        fabric_env = fabric.api.env
        fabric_env.update({
            'timeout': 30,
            'user': 'centos',
            'key_filename': manager_keypath,
            'host_string': self.env.management_ip,
            })

    def get_manager_cpu_usage(self):
        self.logger.info('get_manager_memory_total with ip {0}'
                         .format(self.env.management_ip))
        return (fabric.api.run(
            'echo $[100-$(vmstat|tail -1|awk \'{print $15}\')];'))

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
                'df -k | grep /dev/vda1 | '
                'awk \'{print $2}\'')).replace(
                "sudo: unable to resolve host cloudify-manager-server", ""))

    def get_manager_disk_available(self):
        self.logger.info('get_manager_disk_available with ip {0}'
                         .format(self.env.management_ip))
        return int(
            str(fabric.api.run(
                'df -k | grep /dev/vda1 | '
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

    def _end_test(self):
        # self.check_all_installed_deployments_installed_successfully()
        self.wait_for_all_threads_to_finish()
        self.execute_install_on_all_deployments()
        self.logger.info(json.dumps(self.state_dict, indent=2))
        self.assertGreater(self.installed, 10, "failed to reach 10 installed "
                                               "deployments within 30 minutes")
        return self.state_dict
