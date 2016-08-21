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
import requests
from requests.exceptions import ConnectionError

from cosmo_tester.framework.git_helper import clone
from cosmo_tester.framework.testenv import TestCase


class ResourcesAvailableTest(TestCase):
    repo_url = ('https://github.com/cloudify-cosmo/'
                'cloudify-nodecellar-example.git')

    def test_resources_available(self):
        blueprint_name = 'openstack-blueprint.yaml'
        self.repo_dir = clone(self.repo_url, self.workdir)
        self.blueprint_yaml = self.repo_dir / blueprint_name

        self.cfy.blueprints.upload(
            self.blueprint_yaml,
            blueprint_id=self.test_id
        )

        invalid_resource_url = 'http://{0}/resources/blueprints/{1}/{2}' \
            .format(self.env.management_ip, self.test_id, blueprint_name)

        try:
            result = requests.head(invalid_resource_url)
            self.assertNotEqual(
                result.status_code, 200,
                "Resources are available through a different port than 53229.")
        except ConnectionError:
            pass

        self.cfy.blueprints.delete(self.test_id)
