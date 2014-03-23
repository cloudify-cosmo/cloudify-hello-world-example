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


__author__ = 'ilyash'

CHEF_SERVER_COOKBOOK_ZIP_URL = (
    'https://github.com/opscode-cookbooks/chef-server/archive/'
    'c588a4c401d3fac14f70d3285fe49eb4dccd9759.zip'
)


import shutil
import subprocess
import sys
import time
import UserDict
import yaml

# WORKAROUND - start
from cosmo_manager_rest_client.cosmo_manager_rest_client import CosmoManagerRestClient
CosmoManagerRestClient.status = type('MockOkStatus', (object,), {'status': 'running'})
# WORKAROUND - end


from cosmo_tester.framework.testenv import TestCase
from cosmo_tester.framework.util import get_blueprint_path, YamlPatcher


class YamlFile(UserDict.UserDict):

    def __init__(self, path):
        self.path = path

    def __enter__(self):
        self.data = yaml.load(open(self.path, 'r'))
        return self

    def __exit__(self, ex_type, ex_val, ex_bt):
        if not ex_type:
            yaml.dump(self.data, open(self.path, 'w'))
    

class ChefPluginTest(TestCase):

    def setUp(self, *args, **kwargs):
        super(ChefPluginTest, self).setUp(*args, **kwargs)
        blueprint_dir = self.copy_blueprint('chef-plugin')
        self.blueprint_yaml = blueprint_dir / 'chef-server-by-chef-solo.yaml'
        with YamlFile(self.blueprint_yaml) as blueprint:
            vm = blueprint['blueprint']['nodes'][0]
            vm['properties']['server'].update({
                'name': 'system-test-chef-server-{0}'.format(int(time.time())),
            })
            # print(yaml.dump(blueprint.data))
        cookbooks_dir = blueprint_dir / 'cookbooks'
        cookbooks_dir.mkdir()

        def run(*args, **kwargs):
            return subprocess.check_output(*args, stderr=sys.stderr, **kwargs)

        with cookbooks_dir:
            run([
                'wget', '-q', '-O', 'chef-server.zip',
                CHEF_SERVER_COOKBOOK_ZIP_URL,
            ])
            run(['unzip', 'chef-server.zip'])
            chef_cookbook_dir = cookbooks_dir.glob('chef-server-*')[0]
            run(['mv', chef_cookbook_dir, 'chef-server'])
            # Next line because Chef cookbooks are required 
            # to declare all dependencies, even if they don't use them.
            # We don't need git, it's only used in chef-cookbook::dev recipe.
            run(['sed', '-i', "/depends 'git'/d", 'chef-server/metadata.rb'])
        
        with blueprint_dir:
            run(['tar', 'czf', 'cookbooks.tar.gz', 'cookbooks'])

        before, after = self.upload_deploy_and_execute_install()
        print(before)
        print(after)

    def test(self):
        pass
