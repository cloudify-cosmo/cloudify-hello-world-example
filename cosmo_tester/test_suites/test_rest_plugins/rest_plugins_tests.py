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

import os
import shutil

import fabric
from path import path

from cosmo_tester.framework import util
from cosmo_tester.framework.testenv import TestCase


class RestPluginsTests(TestCase):

    def test_install_rest_plugins(self):
        self.manager_blueprint_path = path(self.env._manager_blueprint_path)
        self._update_manager_blueprint()
        self._bootstrap()
        self._assert_plugins_installed()
        self._teardown()

    def _update_manager_blueprint(self):
        src_plugin_dir = util.get_plugin_path('mock-rest-plugin')
        shutil.copytree(src_plugin_dir,
                        self.manager_blueprint_path.dirname() /
                        'mock-rest-plugin')
        plugin_template_url = ('https://github.com/cloudify-cosmo/'
                               'cloudify-plugin-template/archive/{0}.zip'
                               .format(os.environ.get('BRANCH_NAME_PLUGINS',
                                                      'master')))
        plugins = {
            'plugin1': {
                'source': plugin_template_url
            },
            'plugin2': {
                'source': 'mock-rest-plugin',
                'install_args': "--install-option='--do-not-fail'"
            }
        }
        plugins_path = 'node_templates.manager.properties.cloudify.plugins'
        with self.env.handler.update_manager_blueprint() as patch:
            patch.set_value(plugins_path, plugins)

    def _assert_plugins_installed(self):
        manager_key_path = util.get_actual_keypath(
            self.env, self.env.management_key_path)
        fabric.api.env.update({
            'timeout': 30,
            'user': self.env.management_user_name,
            'key_filename': manager_key_path,
            'host_string': self.cfy.get_management_ip()
        })
        local_path = util.get_resource_path('scripts/test_rest_plugins.sh')
        remote_path = ('/home/{0}/test_rest_plugins.sh'
                       .format(self.env.management_user_name))
        container_path = '/tmp/home/test_rest_plugins.sh'
        fabric.api.put(local_path, remote_path)
        output = fabric.api.run(
            'chmod +x {0} && '
            'sudo docker exec -t cfy bash {1}'
            .format(remote_path, container_path))
        # This tells us that plugin-template was successfully installed
        self.assertIn('imported_plugin_tasks', output)
        # This tells us that mock-rest-plugin was successfully installed
        self.assertIn('mock_attribute_value', output)

    def _bootstrap(self):
        self.cfy.bootstrap(self.manager_blueprint_path,
                           inputs_file=self.env.cloudify_config_path,
                           task_retries=5,
                           install_plugins=False)

    def _teardown(self):
        self.cfy.teardown()
