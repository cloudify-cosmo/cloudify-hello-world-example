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

from fabric import api as fabric_api
from path import path

from cosmo_tester.framework import util
from cosmo_tester.framework.testenv import TestCase


class RestPluginsTests(TestCase):

    def test_install_rest_plugins(self):
        self._copy_manager_blueprint()
        self._update_manager_blueprint()
        self._bootstrap()
        self._assert_plugins_installed()

    def _copy_manager_blueprint(self):
        inputs_path, mb_path = util.generate_unique_configurations(
            workdir=self.workdir,
            original_inputs_path=self.env.cloudify_config_path,
            original_manager_blueprint_path=self.env._manager_blueprint_path)
        self.test_manager_blueprint_path = path(mb_path)
        self.test_inputs_path = path(inputs_path)

    def _update_manager_blueprint(self):
        src_plugin_dir = util.get_plugin_path('mock-rest-plugin')
        shutil.copytree(src_plugin_dir,
                        self.test_manager_blueprint_path.dirname() /
                        'mock-rest-plugin')
        plugins = {
            'plugin1': {
                # testing plugin installation from remote url
                'source': 'https://github.com/cloudify-cosmo/'
                          'cloudify-plugin-template/archive/{0}.zip'
                          .format(os.environ.get('BRANCH_NAME_CORE',
                                                 'master'))
            },
            'plugin2': {
                # testing plugin installation in manager blueprint directory
                'source': 'mock-rest-plugin',
                # testing install_args, without the following, plugin
                # installation should fail
                'install_args': "--install-option='--do-not-fail'"
            }
        }
        plugins_path = 'node_templates.rest_service.properties.plugins'
        with util.YamlPatcher(self.test_manager_blueprint_path) as patch:
            patch.set_value(plugins_path, plugins)

    def _assert_plugins_installed(self):
        manager_key_path = util.get_actual_keypath(
            self.env, self.env.management_key_path)
        local_script_path = util.get_resource_path(
            'scripts/test_rest_plugins.sh')
        remote_script_path = ('/home/{0}/test_rest_plugins.sh'
                              .format(self.env.management_user_name))
        with fabric_api.settings(
                timeout=30,
                user=self.env.management_user_name,
                key_filename=manager_key_path,
                host_string=self.get_manager_ip(),
                warn_only=False):
            fabric_api.put(local_script_path, remote_script_path)
            output = fabric_api.run(
                'chmod +x {0} && {0}'.format(remote_script_path))
        # This tells us that plugin-template was successfully installed
        self.assertIn('imported_plugin_tasks', output)
        # This tells us that mock-rest-plugin was successfully installed
        self.assertIn('mock_attribute_value', output)

    def _bootstrap(self):
        self.bootstrap(
            self.test_manager_blueprint_path,
            inputs=self.test_inputs_path,
            install_plugins=self.env.install_plugins
        )
        self.addCleanup(self.cfy.teardown, force=True)
