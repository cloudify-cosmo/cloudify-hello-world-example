########
# Copyright (c) 2016 GigaSpaces Technologies Ltd. All rights reserved
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

from cosmo_tester.framework.util import YamlPatcher
from cosmo_tester.test_suites.test_dockercompute import DockerComputeTestCase
from cosmo_tester.test_suites.test_dockercompute.test_nodecellar import (
    DockerNodeCellar)
from cosmo_tester.test_suites.test_blueprints.nodecellar_test import (
    NodecellarAppTest)


class DockerComputeNodeCellarAutoHealTest(DockerComputeTestCase,
                                          NodecellarAppTest):

    def test_dockercompute_nodecellar_autoheal(self):
        nodecellar = DockerAutoHealNodeCellar(self)
        nodecellar.prepare()
        nodecellar.install()
        nodecellar.assert_installed()
        nodecellar.kill_nodejs_vm()
        nodecellar.assert_web_server_not_running()
        nodecellar.wait_for_autoheal()
        nodecellar.assert_webserver_running()
        nodecellar.uninstall()
        nodecellar.assert_uninstalled()


class DockerAutoHealNodeCellar(DockerNodeCellar):

    def prepare(self):
        super(DockerAutoHealNodeCellar, self).prepare()
        with YamlPatcher(self.test_case.blueprint_yaml) as patch:
            patch.merge_obj('groups', self.autoheal_group_yaml)

    def kill_nodejs_vm(self):
        self.test_case.kill_container(node_id='nodejs_host')

    def wait_for_autoheal(self, timeout=1200):
        end = time.time() + timeout
        autoheal_execution = None

        while time.time() < end:
            autoheal_execution = self.get_autoheal_execution()
            if autoheal_execution is not None:
                break
            time.sleep(10)

        self.test_case.assertIsNotNone(autoheal_execution,
                                       msg="Timed out waiting "
                                           "for auto-heal workflow")
        self.test_case.wait_for_execution(
            autoheal_execution, end - time.time())

    def get_autoheal_execution(self):
        executions = self.test_case.client.executions.list(
            deployment_id=self.deployment_id)
        for e in executions:
            if e.workflow_id == 'heal':
                return e
        return None

    execute_workflow_trigger = 'cloudify.policies.triggers.execute_workflow'
    workflow_parameters = {
        'node_instance_id': {'get_property': ['SELF', 'node_id']},
        'diagnose_value': {'get_property': ['SELF', 'diagnose']},
    }
    autoheal_group_yaml = {
        'autohealing_group': {
            'members': ['nodejs_host'],
            'policies': {
                'simple_autoheal_policy': {
                    'type': 'cloudify.policies.types.host_failure',
                    'properties': {'service': ['cpu.total.system']},
                    'triggers': {
                        'auto_heal_trigger': {
                            'type': execute_workflow_trigger,
                            'parameters': {
                                'workflow': 'heal',
                                'workflow_parameters': workflow_parameters
                            }
                        }
                    }
                }
            }
        }
    }
