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

import filecmp
import os
import shutil
import tarfile
import tempfile

from cosmo_tester.framework import util
from cosmo_tester.framework.testenv import TestCase

TEST_PACKAGE_NAME = 'mock-wagon-plugin'


class DownloadInstallPluginTest(TestCase):

    def setUp(self):
        super(DownloadInstallPluginTest, self).setUp()
        self.wheel_tar = self._create_sample_wheel()
        self.downloaded_archive_path = os.path.join(self.workdir,
                                                    os.path.basename(
                                                        self.wheel_tar))

    def tearDown(self):
        if self.client:
            self._delete_all_plugins()
        super(DownloadInstallPluginTest, self).tearDown()

    def _create_sample_wheel(self):
        source_dir = util.get_resource_path('plugins/{0}'.format(
            TEST_PACKAGE_NAME))
        target_dir = tempfile.mkdtemp(dir=self.workdir)
        return util.create_wagon(source_dir=source_dir, target_dir=target_dir)

    def test_download_plugin(self):
        # upload the plugin
        plugin = self.client.plugins.upload(self.wheel_tar)

        # check download
        self.cfy.plugins.download(
            plugin.id,
            output_path=self.downloaded_archive_path
        )
        self.assertTrue(os.path.exists(self.downloaded_archive_path))

        # assert plugin metadata integrity
        package_json = self._extract_package_json(self.wheel_tar)
        new_package_json = self._extract_package_json(
            self.downloaded_archive_path)
        self.assertTrue(filecmp.cmp(package_json, new_package_json))

    def test_install_managed_plugin(self):
        self._upload_plugin()
        self._verify_plugin_can_be_used_in_blueprint()

    def test_create_snapshot_with_plugin(self):
        self._upload_plugin()

        execution = self.client.snapshots.create(self.test_id, False, False)
        self.wait_for_execution(execution, 1000)
        self._delete_all_plugins()
        execution = self.client.snapshots.restore(self.test_id)
        self.wait_for_execution(execution, 1000)

        self._verify_plugin_can_be_used_in_blueprint()

    def _upload_plugin(self):
        return self.client.plugins.upload(self.wheel_tar)

    def _verify_plugin_can_be_used_in_blueprint(self):
        blueprint_path = self.copy_blueprint('managed-plugins')
        self.blueprint_yaml = blueprint_path / 'blueprint.yaml'

        try:
            # install a blueprint that uses the managed plugin
            test_input_value = 'MY_TEST_INPUT'
            inputs = {'test_input': test_input_value}
            self.upload_deploy_and_execute_install(fetch_state=False,
                                                   inputs=inputs)
            outputs = self.client.deployments.outputs.get(self.test_id)
            self.assertEqual(outputs.outputs['test_output'], test_input_value)
        finally:
            self.execute_uninstall()
            self.cfy.deployments.delete(self.test_id)
            self.cfy.blueprints.delete(self.test_id)
            shutil.rmtree(blueprint_path)

    def _delete_all_plugins(self):
        for plugin in self.client.plugins.list():
            self.client.plugins.delete(plugin.id)

    def _delete_plugins_by_package_name(self, package_name):
        plugins = self.client.plugins.list(package_name=package_name)
        for plugin in plugins:
            self.client.plugins.delete(plugin.id)

    def _extract_package_json(self, tar_location):
        tar = tarfile.open(tar_location)
        member = tar.getmember('{0}/package.json'.format(TEST_PACKAGE_NAME))
        member.name = os.path.basename(member.name)
        dest = tempfile.mkdtemp(dir=self.workdir)
        tar.extract(member, dest)
        return '{0}/{1}'.format(dest, os.path.basename(member.name))
