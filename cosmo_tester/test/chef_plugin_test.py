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
import sh
import subprocess
import sys
import time
import UserDict
import yaml

from cosmo_tester.framework.testenv import TestCase

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


def get_nodes_of_type(blueprint, type_):
    return [n for n in blueprint['blueprint']['nodes'] if n['type'] == type_]


def get_agent_key_file(env):
    with env.cloudify_config_path.dirname():
        agent_key_file = path(env.agent_key_path).abspath()
        if not agent_key_file.exists():
            raise RuntimeError("Agent key file {0} does not exist".format(
                agent_key_file))
    return agent_key_file


def update_blueprint(env, blueprint, hostname, userdata_vars=None):
    hostname_base = 'system-test-{0}-{1}'.format(
        time.strftime("%Y%m%d-%H%M"), hostname)
    agent_key_file = get_agent_key_file(env)
    vms = get_nodes_of_type(blueprint, 'cloudify.openstack.server')
    vms += get_nodes_of_type(blueprint, 'existing_server')
    if len(vms) > 1:
        hostnames = [
            '{0}-{1:2}'.format(hostname_base, i)
            for i in range(0, len(vms))
        ]
    else:
        hostnames = [hostname_base]

    users = []
    for vm_idx, vm in enumerate(vms):
        vm_hostname = hostnames[vm_idx]
        vm['properties']['worker_config']['key'] = (
            '~/.ssh/' + str(agent_key_file.basename()))

        # vm['properties']['server'] does not exist when using existing one
        if 'server' in vm['properties']:
            vm['properties']['server'].update({
                'name': vm_hostname,
                'key_name': env.agent_keypair_name,
            })
            vm['properties']['server']['security_groups'].append(
                env.agents_security_group)
            props = vm['properties']['server']
            if 'userdata' in props:
                props['userdata'] = props['userdata'].format(
                    hostname=vm_hostname, **(userdata_vars or {}))
        users.append(vm['properties']['worker_config']['user'])

    fips = get_nodes_of_type(blueprint, 'cloudify.openstack.floatingip')
    for fip in fips:
            fip_fip = fip['properties']['floatingip']
            fip_fip['floating_network_name'] = env.external_network_name

    return {'hostnames': hostnames, 'users': users}


class ChefPluginClientTest(TestCase):

    def setUp(self, *args, **kwargs):

        super(ChefPluginClientTest, self).setUp(*args, **kwargs)
        agent_key_file = get_agent_key_file(self.env)

        ### # XXX - continue with existing setup
        ### self.test_id = 'system-test-20140325-1303'
        ### self.blueprint_dir = path('/tmp/cosmo-test-PtHEwB/chef-plugin')
        ### self.chef_server_hostname = 'system-test-20140325-1303-chef-server'
        ### self.chef_server_ip = '15.126.198.93'
        ### fabric_env = fabric.api.env
        ### fabric_env.update({
        ###     'timeout': 30,
        ###     'user': 'ubuntu',
        ###     'key_filename': str(agent_key_file),
        ###     'host_string': self.chef_server_ip,
        ### })
        ### return
        ### # XXX

        blueprint_dir = self.copy_blueprint('chef-plugin')
        self.blueprint_yaml = blueprint_dir / 'chef-server-by-chef-solo.yaml'

        with YamlFile(self.blueprint_yaml) as blueprint:
            bp_info = update_blueprint(self.env, blueprint, 'chef-server')

        self.chef_server_hostname = bp_info['hostnames'][0]

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

        id_ = self.test_id + '-chef-server'
        before, after = self.upload_deploy_and_execute_install(id_, id_)

        fip_node = find_node_state('ip', after['node_state'][id_])
        self.chef_server_ip = fip_node['runtimeInfo']['floating_ip_address']

        fabric_env = fabric.api.env
        fabric_env.update({
            'timeout': 30,
            'user': bp_info['users'][0],
            'key_filename': str(agent_key_file),
            'host_string': self.chef_server_ip,
        })

        setup_chef_server.setup(blueprint_dir, CHEF_SERVER_COOKBOOKS_TAR_GZS)
        self.blueprint_dir = blueprint_dir

    def test_chef_client(self):
        blueprint_dir = self.blueprint_dir
        self.blueprint_yaml = blueprint_dir / 'chef-client-test.yaml'
        with YamlFile(self.blueprint_yaml) as blueprint:
            update_blueprint(self.env, blueprint, 'chef-server', {
                'chef_server_ip': self.chef_server_ip,
                'chef_server_hostname': self.chef_server_hostname,
            })
            chef_node = get_nodes_of_type(blueprint, 'db_server_chef')[0]
            chef_config = chef_node['properties']['chef_config']
            chef_config['chef_server_url'] = 'https://{0}:443'.format(
                self.chef_server_ip)
            chef_config['validation_client_name'] = 'chef-validator'
            chef_config['validation_key'] = (
                path(blueprint_dir) / 'chef-validator.pem').text()

        # import pdb; pdb.set_trace()

        id_ = self.test_id + '-chef-client-' + str(int(time.time()))  # XXX
        before, after = self.upload_deploy_and_execute_install(id_, id_)

        fip_node = find_node_state('ip', after['node_state'][id_])
        chef_client_ip = fip_node['runtimeInfo']['floating_ip_address']

        fabric_env = fabric.api.env
        fabric_env.update({
            # XXX: sometime - same user for connection is accidental
            #      todo: replace it with update_blueprint()'s bp_info,
            #            as in setUp()
            'host_string': chef_client_ip,
        })

        out = fabric.api.run('cat /tmp/blueprint.txt')
        self.assertEquals(out, 'Great success!')


class ChefPluginSoloTest(TestCase):

    def setUp(self, *args, **kwargs):

        super(ChefPluginSoloTest, self).setUp(*args, **kwargs)

        self.blueprint_dir = self.copy_blueprint('chef-plugin')

        # Get resources
        with self.blueprint_dir:
            # Cookbooks
            for name, url in CHEF_SERVER_COOKBOOKS_TAR_GZS:
                sh.mkdir('-p', 'cookbooks/' + name)
                sh.tar(sh.wget('-qO-', url), 'xvzC', 'cookbooks/' + name,
                       '--strip-components=1')
            for res in 'data_bags', 'environments', 'roles':
                sh.tar('czf', res+'.tgz', res)

    def test_chef_solo(self):
        agent_key_file = get_agent_key_file(self.env)
        blueprint_dir = self.blueprint_dir
        self.blueprint_yaml = blueprint_dir / 'chef-solo-test.yaml'
        with YamlFile(self.blueprint_yaml) as blueprint:
            bp_info = update_blueprint(self.env, blueprint, 'chef-solo')

        id_ = self.test_id + '-chef-solo-' + str(int(time.time()))  # XXX
        before, after = self.upload_deploy_and_execute_install(id_, id_)

        import ipdb; ipdb.set_trace()

        fip_node = find_node_state('ip', after['node_state'][id_])
        chef_solo_ip = fip_node['runtimeInfo']['floating_ip_address']

        fabric_env = fabric.api.env
        fabric_env.update({
            'timeout': 30,
            'user': bp_info['users'][0],
            'key_filename': str(agent_key_file),
            'host_string': chef_solo_ip,
        })

        out = fabric.api.run('cat /tmp/blueprint.txt')
        self.assertEquals(out, 'Great success!')
