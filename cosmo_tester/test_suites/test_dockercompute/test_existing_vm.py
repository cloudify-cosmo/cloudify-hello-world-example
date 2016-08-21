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

import uuid

from cosmo_tester.test_suites.test_dockercompute import DockerComputeTestCase


class ExistingVMTest(DockerComputeTestCase):

    def setUp(self):
        super(DockerComputeTestCase, self).setUp()
        setup_blueprint_id = str(uuid.uuid4())
        self.setup_deployment_id = setup_blueprint_id
        self.blueprint_path = self.copy_blueprint('existing-vm')
        self.blueprint_yaml = self.blueprint_path / 'setup-blueprint.yaml'
        self.add_plugin_yaml_to_blueprint()
        self.upload_deploy_and_execute_install(
            fetch_state=False,
            blueprint_id=setup_blueprint_id,
            deployment_id=self.setup_deployment_id
        )
        self.addCleanup(
            self.uninstall_delete_deployment_and_blueprint,
            deployment_id=self.setup_deployment_id
        )

    def test_existing_vm(self):
        self.blueprint_yaml = self.blueprint_path / 'blueprint.yaml'
        self.upload_deploy_and_execute_install(
            fetch_state=False,
            inputs={
                'ip': self.ip('setup_host',
                              deployment_id=self.setup_deployment_id),
                'agent_key': self.key_path(
                    'setup_host',
                    deployment_id=self.setup_deployment_id),
                'agent_user': 'root'
            })

        instances = self.client.node_instances.list(deployment_id=self.test_id)
        middle_runtime_properties = [i.runtime_properties for i in instances
                                     if i.node_id == 'middle'][0]
        self.assertDictEqual({'working': True}, middle_runtime_properties)
        self.uninstall_delete_deployment_and_blueprint()
