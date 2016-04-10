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

from fabric import contrib

from cosmo_tester.framework.testenv import TestCase


RESOURCE_PATH = 'resources/resource.txt'
RESOURCE_CONTENT = 'this is a deployment resource'


class DeploymentResourceTest(TestCase):

    def get_and_download_deployment_resource_test(self):
        blueprint_id = str(uuid.uuid4())
        deployment_id = blueprint_id
        self.logger.info('blueprint_id/deployment_id = {0}'.format(
            blueprint_id))
        blueprint_path = self.copy_blueprint('deployment-resource')
        blueprint_yaml = blueprint_path / 'blueprint.yaml'
        self.cfy.upload_blueprint(blueprint_id, blueprint_yaml)
        self.cfy.create_deployment(
            blueprint_id,
            deployment_id,
            inputs={'resource_path': RESOURCE_PATH})
        deployment_folder_on_manager = \
            '/opt/manager/resources/deployments/{0}'.format(deployment_id)

        with self.manager_env_fabric() as api:
            api.sudo('mkdir -p {0}/resources'.format(
                deployment_folder_on_manager))
            api.sudo('echo -n "{0}" > {1}/{2}'.format(RESOURCE_CONTENT,
                                                      deployment_id,
                                                      RESOURCE_PATH))
        self.execute_install(deployment_id, fetch_state=False)
        node_instance = self.client.node_instances.list(
            deployment_id=deployment_id)[0]
        get_resource = node_instance.runtime_properties['get_resource']
        download_resource = node_instance.runtime_properties[
            'download_resource']

        self.logger.info('runtime_properties[get_resource] = {0}'.format(
            get_resource))
        self.logger.info('runtime_properties[download_resource] = {0}'.format(
            download_resource))

        self.assertEquals(RESOURCE_CONTENT, get_resource)
        self.assertEquals(RESOURCE_CONTENT, download_resource)

        self.client.deployments.delete(deployment_id)
        with self.manager_env_fabric():
            self.assertFalse(
                contrib.files.exists(deployment_folder_on_manager))
