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

__author__ = 'idanmo'


import os
import shutil
import uuid
import tarfile
import filecmp

from cosmo_tester.framework.testenv import TestCase


class DownloadBlueprintTest(TestCase):
    """
    CFY-196: Tests downloading of a previously uploaded blueprint.
    CFY-995" Added a large (50MB) file to the blueprint
    """

    def setUp(self):
        super(DownloadBlueprintTest, self).setUp()
        self.blueprint_id = str(uuid.uuid4())
        self.blueprint_file = '%s.tar.gz' % self.blueprint_id
        tempdir_name = str(uuid.uuid4())
        self.download_path = os.path.join(self.cfy.workdir, tempdir_name)
        self.downloaded_archive_path = os.path.join(self.cfy.workdir,
                                                    self.blueprint_file)

    def tearDown(self):
        if os.path.exists(self.download_path):
            shutil.rmtree(self.download_path)
        super(DownloadBlueprintTest, self).tearDown()

    def download_blueprint_test(self):
        blueprint_path = self.copy_blueprint('mocks')
        self._create_file("50M", "just_a_large_file.img", blueprint_path)
        blueprint_yaml = blueprint_path / 'single-node.yaml'
        self.cfy.upload_blueprint(self.blueprint_id, blueprint_yaml)
        self.cfy.download_blueprint(self.blueprint_id)
        self.assertTrue(os.path.exists(self.downloaded_archive_path))
        self._extract_tar_file()
        downloaded_blueprint_file = os.path.join(self.download_path,
                                                 'mocks/single-node.yaml')
        self.assertTrue(os.path.exists(downloaded_blueprint_file))
        self.assertTrue(filecmp.cmp(blueprint_yaml, downloaded_blueprint_file))

    def _extract_tar_file(self):
        with tarfile.open(self.downloaded_archive_path) as tar:
            for item in tar:
                tar.extract(item, self.download_path)

    def _create_file(self, fileSize, fileName, path):
        os.system("fallocate -l " + fileSize +
                  " " + path + "/" + fileName)
