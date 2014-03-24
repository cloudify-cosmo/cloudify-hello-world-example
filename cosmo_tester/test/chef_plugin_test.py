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

CHEF_SERVER_COOKBOOKS_TAR_GZS = (
    (
        'create-file',
        'https://github.com/ilyash/cookbook-create-file/archive/'
        'bd8218a6a9b3e33a165042241c50908ccb6145d1.tar.gz'
    ),
)


import fabric.api
from path import path
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

from cosmo_tester.test import setup_chef_server


class YamlFile(UserDict.UserDict):

    def __init__(self, path):
        self.path = path

    def __enter__(self):
        self.data = yaml.load(open(self.path, 'r'))
        return self

    def __exit__(self, ex_type, ex_val, ex_bt):
        if not ex_type:
            yaml.dump(self.data, open(self.path, 'w'))


def find_node_state(node_name, nodes_state):
    pfx = node_name + '_'
    matches = [v for k, v in nodes_state.items() if k.startswith(pfx)]
    if len(matches) != 1:
        raise RuntimeError("Failed to find node {0}".format(node_name))
    return matches[0]


class ChefPluginTest(TestCase):

    def setUp(self, *args, **kwargs):

        super(ChefPluginTest, self).setUp(*args, **kwargs)
        # import pdb; pdb.set_trace()
        with self.env.cloudify_config_path.dirname():
            agent_key_file = path(self.env.agent_key_path).abspath()
        if not agent_key_file.exists():
            raise RuntimeError("Agent key file {0} does not exist".format(
                agent_key_file))


        blueprint_dir = self.copy_blueprint('chef-plugin')
        self.blueprint_yaml = blueprint_dir / 'chef-server-by-chef-solo.yaml'
        hostname = 'system-test-chef-server-{0}'.format(time.strftime("%Y%m%d-%H%M"))
        with YamlFile(self.blueprint_yaml) as blueprint:
            vm = blueprint['blueprint']['nodes'][0]
            vm['properties']['worker_config']['key'] = '~/.ssh/' + str(agent_key_file.basename())

            # vm['properties']['server'] does not exist when using existing one
            if 'server' in vm['properties']:
                vm['properties']['server'].update({
                    'name': hostname,
                    'key_name': self.env.agent_keypair_name,
                })
                vm['properties']['server']['security_groups'].append(self.env.agents_security_group)
                props = vm['properties']['server']
                props['userdata'] = props['userdata'].format(hostname=hostname)
            # print(yaml.dump(blueprint.data))
            fip = blueprint['blueprint']['nodes'][1]
            fip_fip = fip['properties']['floatingip']
            fip_fip['floating_network_name'] = self.env.external_network_name

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

        import pdb; pdb.set_trace()
        fip_node = find_node_state('ip', after['node_state'][self.test_id])
        chef_server_ip = fip_node['runtimeInfo']['floating_ip_address']

        fabric_env = fabric.api.env
        fabric_env.update({
            'timeout': 30,
            'user': vm['properties']['worker_config']['user'],
            'key_filename': str(agent_key_file),
            'host_string': chef_server_ip,
        })

        setup_chef_server.setup(blueprint_dir, CHEF_SERVER_COOKBOOKS_TAR_GZS)




    def test(self):
        pass
