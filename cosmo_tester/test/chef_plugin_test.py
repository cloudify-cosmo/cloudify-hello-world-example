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

""" Assumes fabric environment already set up """

__author__ = 'ilyash'

import subprocess
import time
import os
from zipfile import ZipFile

from fabric import operations
import fabric.api
from path import path
import sh

from cosmo_tester.framework.testenv import TestCase
from cosmo_tester.framework.util import YamlPatcher
from cosmo_tester.framework.util import get_blueprint_path

CHEF_SERVER_COOKBOOK_ZIP_URL = (
    'https://github.com/opscode-cookbooks/chef-server/archive/'
    'c588a4c401d3fac14f70d3285fe49eb4dccd9759.zip'
)

KNIFE_PARAMS = '-u admin -k ~/admin.pem'


def _use_cookbook(cookbook_name,
                  cookbook_local_tar_path):
    """ Downloads cookbook from given url and uploads it to the Chef server """
    fabric.api.run('mkdir -p ~/cookbooks/{0}'.format(cookbook_name))
    fabric.api.put(local_path=cookbook_local_tar_path,
                   remote_path='/tmp/{0}.tar.gz'.format(cookbook_name))
    fabric.api.run('tar -xzvf /tmp/{0}.tar.gz --strip-components=1'
                   ' -C ~/cookbooks/{0}'.format(cookbook_name))
    fabric.api.run('knife cookbook upload {0} --cookbook-path ~/cookbooks {1}'
                   .format(KNIFE_PARAMS, cookbook_name))
    fabric.api.run('knife cookbook list {0} | grep -F {1}'
                   .format(KNIFE_PARAMS, cookbook_name))


def _userize_file(original_path):
    """ Places the file under user's home directory and make it
        permissions-wise accessible """
    fabric.api.sudo("cp -a {path} ~{user}/ && chown {user} ~{user}/{basename}"
                    .format(path=original_path,
                            basename=str(path(original_path).basename()),
                            user=fabric.api.env['user']))


def setup_chef_server(local_dir, cookbooks):
    _userize_file("/etc/chef-server/admin.pem")
    for cb in cookbooks:
        _use_cookbook(*cb)

    _userize_file("/etc/chef-server/chef-validator.pem")
    operations.get('~/chef-validator.pem', str(local_dir))


def find_node_state(node_name, nodes_state):
    pfx = node_name + '_'
    matches = [v for k, v in nodes_state.items() if k.startswith(pfx)]
    if len(matches) != 1:
        raise RuntimeError("Failed to find node {0}".format(node_name))
    return matches[0]


def get_nodes_of_type(blueprint, type_):
    return [n for n in blueprint.obj['blueprint']['nodes']
            if n['type'] == type_]


def get_agent_key_file(env):
    agent_key_file = path(os.path.expanduser(env.agent_key_path)).abspath()
    if not agent_key_file.exists():
        raise RuntimeError("Agent key file {0} does not exist".format(
            agent_key_file))
    return agent_key_file


def update_blueprint(env, blueprint, hostname, userdata_vars=None):
    hostname_base = 'system-test-{0}-{1}'.format(
        time.strftime("%Y%m%d-%H%M"), hostname)
    agent_key_file = get_agent_key_file(env)
    vms = get_nodes_of_type(blueprint, 'cloudify.openstack.server')
    if len(vms) > 1:
        hostnames = ['{0}-{1:2}'.format(hostname_base, i)
                     for i in range(0, len(vms))]
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
                'flavor_name': env.flavor_name,
                'image_name': env.ubuntu_image_name,
                'key_name': env.agent_keypair_name,
                'name': vm_hostname,
            })
            vm['properties']['management_network_name'] = (
                env.management_network_name)
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

        blueprint_dir = self.copy_blueprint('chef-plugin')
        self.blueprint_yaml = blueprint_dir / 'chef-server-by-chef-solo.yaml'

        with YamlPatcher(self.blueprint_yaml) as blueprint:
            bp_info = update_blueprint(self.env, blueprint, 'chef-server')

        self.chef_server_hostname = bp_info['hostnames'][0]

        cookbooks_dir = blueprint_dir / 'cookbooks'

        def run(*args, **kwargs):
            return subprocess.check_output(*args, **kwargs)

        with cookbooks_dir:
            run([
                'wget', '-q', '-O', 'chef-server.zip',
                CHEF_SERVER_COOKBOOK_ZIP_URL,
                ])
            ZipFile('chef-server.zip').extractall()
            chef_cookbook_dir = cookbooks_dir.glob('chef-server-*')[0]
            run(['mv', chef_cookbook_dir, 'chef-server'])
            # Next line because Chef cookbooks are required
            # to declare all dependencies, even if they don't use them.
            # We don't need git, it's only used in chef-cookbook::dev recipe.
            run(['sed', '-i', "/depends 'git'/d", 'chef-server/metadata.rb'])

        with blueprint_dir:
            run(['tar', 'czf', 'cookbooks.tar.gz', 'cookbooks'])

        self.chef_server_id = self.test_id + '-chef-server'
        id_ = self.chef_server_id
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

        cookbook_local_path = os.path.abspath(
            os.path.join(get_blueprint_path('chef-plugin'),
                         'cookbook-create-file.tar.gz'))
        setup_chef_server(blueprint_dir, [[
            'create-file',
            cookbook_local_path,
        ]])
        self.blueprint_dir = blueprint_dir

    def tearDown(self, *args, **kwargs):
        self.execute_uninstall(self.chef_server_id)
        super(ChefPluginClientTest, self).tearDown(*args, **kwargs)

    def test_chef_client(self):
        blueprint_dir = self.blueprint_dir
        self.blueprint_yaml = blueprint_dir / 'chef-client-test.yaml'
        with YamlPatcher(self.blueprint_yaml) as blueprint:
            update_blueprint(self.env, blueprint, 'chef-server', {
                'chef_server_ip': self.chef_server_ip,
                'chef_server_hostname': self.chef_server_hostname,
            })
            chef_node = get_nodes_of_type(blueprint,
                                          'cloudify.types.chef.db_server')[0]
            chef_config = chef_node['properties']['chef_config']
            chef_config['chef_server_url'] = 'https://{0}:443'.format(
                self.chef_server_ip)
            chef_config['validation_client_name'] = 'chef-validator'
            chef_config['validation_key'] = (
                path(blueprint_dir) / 'chef-validator.pem').text()

        id_ = self.test_id + '-chef-client-' + str(int(time.time()))
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

        self.execute_uninstall(id_)


class ChefPluginSoloTest(TestCase):

    def setUp(self, *args, **kwargs):

        super(ChefPluginSoloTest, self).setUp(*args, **kwargs)

        self.blueprint_dir = self.copy_blueprint('chef-plugin')

        # Get resources
        with self.blueprint_dir:
            for res in 'cookbooks', 'data_bags', 'environments', 'roles':
                sh.tar('czf', res+'.tar.gz', res)

    def test_chef_solo(self):
        agent_key_file = get_agent_key_file(self.env)
        blueprint_dir = self.blueprint_dir
        self.blueprint_yaml = blueprint_dir / 'chef-solo-test.yaml'
        with YamlPatcher(self.blueprint_yaml) as blueprint:
            bp_info = update_blueprint(self.env, blueprint, 'chef-solo')

        id_ = self.test_id + '-chef-solo-' + str(int(time.time()))
        before, after = self.upload_deploy_and_execute_install(id_, id_)

        fip_node = find_node_state('ip', after['node_state'][id_])
        chef_solo_ip = fip_node['runtimeInfo']['floating_ip_address']

        fabric_env = fabric.api.env
        fabric_env.update({
            'timeout': 30,
            'user': bp_info['users'][0],
            'key_filename': str(agent_key_file),
            'host_string': chef_solo_ip,
        })

        expected_files_contents = (
            ('/tmp/blueprint.txt', 'Great success number #2 !'),
            ('/tmp/blueprint2.txt', '/tmp/blueprint.txt'),
            ('/tmp/chef_node_env.e1.txt', 'env:e1'),
            ('/tmp/chef_node_data_bag_user.db1.i1.txt', 'db1-i1-k1'),
        )

        for file_name, expected_content in expected_files_contents:
            actual_content = fabric.api.run('cat ' + file_name)
            msg = "File '{0}' should have content '{1}' but has '{2}'".format(
                file_name, expected_content, actual_content)
            self.assertEquals(actual_content, expected_content, msg)

        self.execute_uninstall(id_)
