########
# Copyright (c) 2016 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.

import uuid
import requests
import shutil
import os

from requests.exceptions import RequestException
from retrying import retry

from cosmo_tester.framework import testenv, util
from cosmo_tester.test_suites.test_blueprints.hello_world_bash_test import \
    clone_hello_world, verify_webserver_running


def wait_for_deployment_update_to_finish(func):
    def _update_and_wait_to_finish(self, deployment_id, *args, **kwargs):
        func(self, deployment_id, *args, **kwargs)

        @retry(stop_max_attempt_number=10,
               wait_fixed=5000,
               retry_on_result=lambda r: not r)
        def repetetive_check():
            deployment_updates_list = self.client.deployment_updates.list(
                deployment_id=deployment_id)
            executions_list = self.client.executions.list(
                deployment_id=deployment_id,
                workflow_id='update',
                _include=['status']
            )

            if len(deployment_updates_list) != self.update_counter:
                return False

            for deployment_update in deployment_updates_list:
                if deployment_update.state not in ['failed', 'successful']:
                    return False
            for execution in executions_list:
                if execution['status'] not in ['terminated',
                                               'failed',
                                               'cancelled']:
                    return False

            return True

        repetetive_check()

    return _update_and_wait_to_finish


class DeploymentUpdateTest(testenv.TestCase):

    def setUp(self):
        super(DeploymentUpdateTest, self).setUp()
        self.update_counter = 0

    @property
    def _hello_world_inputs(self):
        raise NotImplementedError

    @property
    def _blueprint_name(self):
        raise NotImplementedError

    def deployment_update_test(self):
        deployment_id = str(uuid.uuid4())
        modified_port = '9090'

        self.addCleanup(
            self.uninstall_delete_deployment_and_blueprint,
            deployment_id=deployment_id
        )
        self._upload_helloworld_and_deploy(deployment_id,
                                           blueprint_file=self._blueprint_name,
                                           inputs=self._hello_world_inputs)

        end_point = self._get_endpoint(deployment_id)
        # Check server is indeed online
        self._check_webserver(end_point)

        # Update the deployment - shutdown the http_web_server, and the
        # security_group node. Remove the relationship between the vm
        # and the security_group node. Remove the output - since no new outputs
        # have been outputed, the check will be based on the old outputs.
        modified_blueprint_path = self._create_modified_deployment()
        self._update_deployment(deployment_id,
                                modified_blueprint_path)
        self._check_webserver(end_point, assert_online=False)

        # Startup the initial blueprint (with 9090 as port)
        self._update_deployment(deployment_id,
                                self.blueprint_yaml,
                                inputs={'webserver_port': modified_port})

        end_point = self._get_endpoint(deployment_id)
        self._check_webserver(end_point)

    def _check_webserver(self, end_point, assert_online=True):
        if assert_online:
            self.logger.info('Verifying web server is running on: {0}'
                             .format(end_point))
            verify_webserver_running(end_point)
        else:
            try:
                self.logger.info('Verifying web server is not running on: {0}'
                                 .format(end_point))
                self._verify_webserver_offline(end_point)
            except RequestException:
                return
            self.fail("Accessing should have resulted in Connection timeout "
                      "error, But wasn't")

    def _upload_helloworld_and_deploy(self,
                                      deployment_id,
                                      blueprint_file='blueprint.yaml',
                                      inputs=None,
                                      install=True):
        self.repo_dir = clone_hello_world(self.workdir)
        self.blueprint_yaml = self.repo_dir / blueprint_file
        if install:
            self.upload_deploy_and_execute_install(
                deployment_id=deployment_id,
                fetch_state=False,
                inputs=inputs)

    @wait_for_deployment_update_to_finish
    def _update_deployment(self, deployment_id, blueprint_path, inputs=None):
        inputs = self.get_inputs_in_temp_file(inputs, deployment_id)
        self.update_counter += 1
        self.cfy.deployments.update(
            deployment_id,
            blueprint_path=blueprint_path,
            inputs=inputs
        )

    def _create_modified_deployment(self):
        self.modified_dir = os.path.join(self.workdir, 'modified_blueprint')
        shutil.copytree(self.repo_dir, self.modified_dir)
        modified_blueprint_path = util.get_blueprint_path('blueprint.yaml',
                                                          self.modified_dir)
        self.modified_blueprint_yaml = \
            self._modify_blueprint(modified_blueprint_path)

        return modified_blueprint_path

    def _modify_blueprint(self, blueprint_path):
        with util.YamlPatcher(blueprint_path) as patcher:
            # Remove security group
            patcher.delete_property('node_templates.security_group')
            # Remove the webserver node
            patcher.delete_property('node_templates.http_web_server')
            # Remove the output
            patcher.delete_property('outputs', 'http_endpoint')

            # Remove vm to security_group relationships
            blueprint = util.get_yaml_as_dict(blueprint_path)
            vm_relationships = blueprint['node_templates']['vm'][
                'relationships']
            vm_relationships = [r for r in vm_relationships if r['target'] !=
                                'security_group']
            patcher.set_value('node_templates.vm.relationships',
                              vm_relationships)

        return blueprint_path

    @retry(stop_max_attempt_number=5,
           wait_fixed=2000,
           retry_on_exception=lambda e: isinstance(e, RequestException))
    def _verify_webserver_offline(self, end_point):
        requests.get(end_point, timeout=15)

    def _get_endpoint(self, deployment_id):
        outputs = self.client.deployments.outputs.get(deployment_id)['outputs']
        return outputs['http_endpoint']


class DeploymentUpdateOSTest(DeploymentUpdateTest):

    @property
    def _blueprint_name(self):
        return 'blueprint.yaml'

    @property
    def _hello_world_inputs(self):
        return {
            'agent_user': 'ubuntu',
            'image': self.env.ubuntu_trusty_image_id,
            'flavor': self.env.medium_flavor_id
        }
