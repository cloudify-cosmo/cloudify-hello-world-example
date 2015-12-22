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

from cinderclient import exceptions as cinder_exc

from cosmo_tester.framework.testenv import TestCase


class CinderVolumeTestBase(TestCase):

    VOLUME_SIZE = 1
    DEVICE_NAME = '/dev/vdc'

    def setUp(self):
        super(CinderVolumeTestBase, self).setUp()
        _, _, self.cinderclient = self.env.handler.openstack_clients()


class CinderVolumeTest(CinderVolumeTestBase):

    def test_volume_use_existing(self):

        blueprint_path = self.copy_blueprint('openstack-cinder')
        self.blueprint_yaml = \
            blueprint_path / 'use-existing-volume-blueprint.yaml'

        volume_name = 'volume-system-test'

        volume = self.cinderclient.volumes.create(size=self.VOLUME_SIZE,
                                                  display_name=volume_name)
        self.addCleanup(self.cinderclient.volumes.delete, volume.id)

        self._wait_for_volume_available(volume)

        inputs = {
            'image': self.env.ubuntu_trusty_image_name,
            'flavor': self.env.flavor_name,
            'existing_volume_id': volume.id,
            'device_name': self.DEVICE_NAME
        }

        before, after = self.upload_deploy_and_execute_install(
            inputs=inputs
        )

        self._post_install_assertions(before, after)

        self.execute_uninstall()

        self._post_uninstall_assertions()

    def _wait_for_volume_available(self, volume, num_tries=10):
        for _ in range(num_tries):
            v = self.cinderclient.volumes.get(volume.id)
            if v.status == 'available':
                return True
            else:
                time.sleep(2)
        return False

    def _post_install_assertions(self, before_state, after_state):
        delta = self.get_manager_state_delta(before_state, after_state)

        self.assertEqual(len(delta['deployment_nodes']), 1)

        self.assertEqual(len(delta['node_state']), 1)

        self._check_nodes(delta)
        self._check_blueprint(delta)
        self._check_deployment(delta)

        nodes_state = delta['node_state'].values()[0]
        self.assertEqual(len(nodes_state), 2)

        for key, value in nodes_state.items():
            if 'volume' in key:
                self.assertTrue('external_name' in value['runtime_properties'])
                self.assertTrue('external_id' in value['runtime_properties'])
                self.assertTrue('external_type'
                                in value['runtime_properties'])
                self.assertEqual('volume',
                                 value['runtime_properties']['external_type'])
                self.assertEqual(value['state'], 'started')

                volume_id = value['runtime_properties']['external_id']
                volume_created = True
                try:
                    volume = self.cinderclient.volumes.get(volume_id)
                except cinder_exc.NotFound:
                    volume_created = False
                self.assertTrue(volume_created)
                self.assertEqual(self.VOLUME_SIZE, volume.size)
                self.assertEqual(1, len(volume.attachments))
                self.assertEqual(self.DEVICE_NAME,
                                 volume.attachments[0]['device'])

    def _post_uninstall_assertions(self):
        nodes_instances = self.client.node_instances.list(self.deployment_id)
        self.assertEqual(len([node_ins for node_ins in nodes_instances if
                              node_ins.state != 'deleted']), 0)

    def _check_nodes(self, delta):
        self.assertEqual(len(delta['nodes']), 2)
        deployment = delta['deployments'].values()[0]
        nodes = self.client.nodes.list(deployment.id)
        self.assertEqual(len(nodes), 2)
        volume_node_verified = False
        for node in nodes:
            if node.id == 'test_volume':
                self.assertEqual(len(node.relationships), 1)
                self.assertTrue('device_name' in node.properties)
                volume_node_verified = True
        self.assertTrue(volume_node_verified)

    def _check_blueprint(self, delta):
        self.assertEqual(len(delta['blueprints']), 1)

    def _check_deployment(self, delta):
        self.assertEqual(len(delta['deployments']), 1)
        deployment_from_list = delta['deployments'].values()[0]
        deployment = self.client.deployments.get(deployment_from_list.id)
        self.assertEqual(deployment_from_list.id, deployment.id)
        self.deployment_id = deployment_from_list.id
        self._check_executions(deployment)

    def _check_executions(self, deployment):
        executions = self.client.executions.list(deployment_id=deployment.id)

        self.assertEqual(len(executions), 2)

        execution_from_list = executions[0]
        execution_by_id = self.client.executions.get(execution_from_list.id)

        self.assertEqual(execution_from_list.id, execution_by_id.id)
        self.assertEqual(execution_from_list.workflow_id,
                         execution_by_id.workflow_id)
        self.assertEqual(execution_from_list['blueprint_id'],
                         execution_by_id['blueprint_id'])

        events, _ = self.client.events.get(execution_by_id.id)

        self.assertGreater(len(events), 0)


class CinderVolumeFSTest(CinderVolumeTestBase):

    FS_TYPE = 'ext4'
    FS_MOUNT_PATH = '/test-mount'

    def test_volume_file_system(self):

        blueprint_path = self.copy_blueprint('openstack-cinder')
        self.blueprint_yaml = blueprint_path / 'file-system-blueprint.yaml'

        inputs = {
            'image': self.env.ubuntu_trusty_image_name,
            'flavor': self.env.flavor_name,
            'volume_size': self.VOLUME_SIZE,
            'fs_type': self.FS_TYPE,
            'fs_mount_path': self.FS_MOUNT_PATH
        }

        before, after = self.upload_deploy_and_execute_install(
            inputs=inputs
        )

        self._post_install_assertions(before, after)

        self.execute_uninstall()

        self._post_uninstall_assertions()

    def _post_install_assertions(self, before_state, after_state):
        delta = self.get_manager_state_delta(before_state, after_state)

        self.assertEqual(len(delta['deployment_nodes']), 1)

        self.assertEqual(len(delta['node_state']), 1)

        self._check_nodes(delta)
        self._check_blueprint(delta)
        self._check_deployment(delta)

        nodes_state = delta['node_state'].values()[0]
        self.assertEqual(len(nodes_state), 4)

    def _post_uninstall_assertions(self):
        nodes_instances = self.client.node_instances.list(self.deployment_id)
        self.assertEqual(len([node_ins for node_ins in nodes_instances if
                              node_ins.state != 'deleted']), 0)

    def _check_nodes(self, delta):
        self.assertEqual(len(delta['nodes']), 4)
        deployment = delta['deployments'].values()[0]
        nodes = self.client.nodes.list(deployment.id)
        self.assertEqual(len(nodes), 4)

    def _check_blueprint(self, delta):
        self.assertEqual(len(delta['blueprints']), 1)

    def _check_deployment(self, delta):
        self.assertEqual(len(delta['deployments']), 1)
        deployment_from_list = delta['deployments'].values()[0]
        deployment = self.client.deployments.get(deployment_from_list.id)
        self.assertEqual(deployment_from_list.id, deployment.id)
        self.deployment_id = deployment_from_list.id
