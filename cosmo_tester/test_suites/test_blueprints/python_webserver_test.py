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


__author__ = 'dan'

from cosmo_tester.framework.testenv import TestCase
from cosmo_tester.framework.util import YamlPatcher


class PythonWebServerTest(TestCase):

    def test_python_webserver(self):

        blueprint_path = self.copy_blueprint('python-webserver')
        self.blueprint_yaml = blueprint_path / 'blueprint.yaml'
        self.webserver_yaml = blueprint_path / 'python_webserver.yaml'
        self.modify_blueprint()

        before, after = self.upload_deploy_and_execute_install()

        self.post_install_assertions(before, after)

        self.execute_uninstall()

        self.post_uninstall_assertions()

    def modify_blueprint(self):
        with YamlPatcher(self.webserver_yaml) as patch:
            vm_path = 'type_implementations.vm_openstack_host_impl.properties'
            patch.merge_obj('{0}.server'.format(vm_path), {
                'name': 'pythonwebserver',
                'image_name': self.env.ubuntu_image_name,
                'flavor_name': self.env.flavor_name,
                'security_groups': ['webserver_security_group'],
            })

    def post_install_assertions(self, before_state, after_state):
        delta = self.get_manager_state_delta(before_state, after_state)

        self.logger.info('Current manager state: {0}'.format(delta))

        deployment_from_list = delta['deployments'].values()[0]

        deployment_by_id = self.client.deployments.get(deployment_from_list.id)

        executions = self.client.deployments.list_executions(
            deployment_by_id.id)

        execution_from_list = executions[0]
        execution_by_id = self.client.executions.get(execution_from_list.id)

    def post_uninstall_assertions(self):
        # TODO
        pass
