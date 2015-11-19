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

from wagon.wagon import Wagon

from cosmo_tester.framework.testenv import TestCase

TEST_PACKAGE_NAME = 'mogrify'
TEST_PACKAGE_VERSION = '0.1'


class DownloadInstallPluginTest(TestCase):

    def setUp(self):
        super(DownloadInstallPluginTest, self).setUp()
        self.wheel_tar = self._create_sample_wheel(TEST_PACKAGE_NAME,
                                                   TEST_PACKAGE_VERSION)
        self.downloaded_archive_path = os.path.join(self.workdir,
                                                    os.path.basename(
                                                        self.wheel_tar))

    def tearDown(self):
        if self.client:
            self._delete_all_plugins()
        super(DownloadInstallPluginTest, self).tearDown()

    def _create_sample_wheel(self, package_name, package_version):
        package_src = '{0}=={1}'.format(package_name,
                                        package_version)
        wagon_client = Wagon(package_src)
        return wagon_client.create(
            archive_destination_dir=tempfile.mkdtemp(dir=self.workdir),
            force=True)

    def test_download_plugin(self):
        # upload the plugin
        plugin = self.client.plugins.upload(self.wheel_tar)

        # check download
        self.cfy.download_plugin(plugin.id, self.downloaded_archive_path)
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
        self.client.snapshots.restore(self.test_id)

        self._verify_plugin_can_be_used_in_blueprint()

    def _upload_plugin(self):
        return self.client.plugins.upload(self.wheel_tar)

    def _verify_plugin_can_be_used_in_blueprint(self):
        blueprint_path = self.copy_blueprint('managed-plugins')
        self.blueprint_yaml = blueprint_path / 'blueprint.yaml'

        try:
            # install a blueprint that uses the managed plugin
            self.upload_deploy_and_execute_install(fetch_state=False)
        finally:
            self.execute_uninstall()
            self.cfy.delete_deployment(self.test_id)
            self.cfy.delete_blueprint(self.test_id)
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
