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

import time

import requests

from cosmo_tester.framework.git_helper import clone
from cosmo_tester.framework.util import YamlPatcher
from cosmo_tester.test_suites.test_blueprints.nodecellar_test import (
    OpenStackNodeCellarTestBase)


class OpenStackAutohealNodeCellarTest(OpenStackNodeCellarTestBase):

    AUTOHEAL_GROUP_YAML = {
        'autohealing_group': {
            'members': ['nodejs_host'],
            'policies': {
                'simple_autoheal_policy': {
                    'type': 'cloudify.policies.types.host_failure',
                    'properties': {
                        'service': ['cpu.total.system']
                    },
                    'triggers': {
                        'auto_heal_trigger': {
                            'type':
                                'cloudify.policies.triggers.execute_workflow',
                            'parameters': {
                                'workflow': 'heal',
                                'workflow_parameters': {
                                    'node_instance_id': {
                                        'get_property': ['SELF', 'node_id']
                                    },
                                    'diagnose_value': {
                                        'get_property': ['SELF', 'diagnose']
                                    },
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    def _test_nodecellar_impl(self, blueprint_file):
        self.repo_dir = clone(self.repo_url, self.workdir)
        self.blueprint_yaml = self.repo_dir / blueprint_file

        self.modify_blueprint()

        before_install, after_install = self.upload_deploy_and_execute_install(
            inputs=self.get_inputs()
        )

        self.post_install_assertions(before_install, after_install)

        self.kill_nodejs_vm()

        # make sure nodecellar is down
        self.assert_nodecellar_down(self.public_ip)

        self.wait_for_autoheal(after_install)

        after_autoheal = self.get_manager_state()

        self.post_autoheal_assertions(after_install, after_autoheal)

        self.execute_uninstall()

        self.post_uninstall_assertions()

    def kill_nodejs_vm(self, timeout=10):
        end = time.time() + timeout
        nova_controller, _, _ = self.env.handler.openstack_clients()
        srv = [s for s in nova_controller.servers.list() if 'nodejs' in s.name]
        self.assertEqual(len(srv), 1)
        srv = srv[0]
        srv.delete()
        while time.time() < end and srv in nova_controller.servers.list():
            time.sleep(1)

    def get_autoheal_execution(self):
        executions = self.client.executions.list(
            deployment_id=self.deployment_id)
        for e in executions:
            if e.workflow_id == 'heal':
                return e
        return None

    def wait_for_autoheal(self, before, timeout=1200):
        end = time.time() + timeout
        autoheal_execution = None

        while time.time() < end:
            autoheal_execution = self.get_autoheal_execution()
            if autoheal_execution is not None:
                break
            time.sleep(10)

        self.assertIsNotNone(autoheal_execution, msg="Timed out waiting "
                                                     "for auto-heal workflow")
        self.wait_for_execution(autoheal_execution, end - time.time())

    def assert_nodecellar_down(self, public_ip):
        with self.assertRaises(requests.ConnectionError):
            requests.get('http://{0}:8080'.format(self.public_ip))

    def post_autoheal_assertions(self, before_state, after_state):
        delta = self.get_manager_state_delta(before_state, after_state)
        for key in ['blueprints', 'deployments', 'node_state',
                    'nodes', 'deployment_nodes']:
            self.assertEqual(len(delta[key]), 0)
        self.assert_nodecellar_working(self.public_ip)

    def modify_blueprint(self):
        with YamlPatcher(self.blueprint_yaml) as patch:
            patch.merge_obj('groups', self.AUTOHEAL_GROUP_YAML)

    def get_inputs(self):
        return {
            'image': self.env.ubuntu_image_id,
            'flavor': self.env.small_flavor_id,
            'agent_user': 'ubuntu'
        }

    def test_openstack_autoheal_nodecellar(self):
        self._test_openstack_nodecellar('openstack-blueprint.yaml')
