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
import sys
import time
import os
from os.path import dirname

import fabric.api
import fabric.context_managers
from path import path

from cosmo_tester.framework.testenv import TestCase
from cosmo_tester.framework.util import YamlPatcher

IMAGE_NAME = 'Ubuntu Precise 12.04 LTS Server 64-bit 20121026 (b)'
FLAVOR_NAME = 'standard.small'

PUPPET_MASTER_VERSION = '3.5.1-1puppetlabs1'


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
    with env.cloudify_config_path.dirname():
        agent_key_file = path(env.agent_key_path).abspath()
        if not agent_key_file.exists():
            raise RuntimeError("Agent key file {0} does not exist".format(
                agent_key_file))
    # agent_key_file = path(os.path.expanduser(env.agent_key_path)).abspath()
    # if not agent_key_file.exists():
    #     raise RuntimeError("Agent key file {0} does not exist".format(
    #         agent_key_file))
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
                'flavor_name': FLAVOR_NAME,
                'image_name': IMAGE_NAME,
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


def setup_puppet_server(local_dir):
    # import pdb; pdb.set_trace()
    for p in 'puppetmaster-common', 'puppetmaster':
        cmd = 'apt-get install -y {0}={1}'.format(p, PUPPET_MASTER_VERSION)
        fabric.api.sudo(cmd)
    remote_path = '/etc/puppet'
    local_path = (
        path(dirname(os.path.dirname(os.path.realpath(__file__)))) /
        'resources' /
        'puppet' + remote_path)
    fabric.api.put(local_path=local_path,
                   remote_path=dirname(remote_path),
                   use_sudo=True)
    fabric.api.sudo('chown puppet -R ' + remote_path)

    t = remote_path + '/puppet.conf'
    fabric.api.sudo('grep -q autosign ' + t + ' || ' +
                    '(echo "[master]"; echo "autosign = true") >> ' + t)
    # fabric.api.sudo('service puppetmaster restart') # Does not work !!!
    fabric.api.sudo('fuser -k 8140/tcp')
    fabric.api.sudo('service puppetmaster start')


class PuppetPluginAgentTest(TestCase):

    def setUp(self, *args, **kwargs):

        super(PuppetPluginAgentTest, self).setUp(*args, **kwargs)

        blueprint_dir = self.copy_blueprint('puppet-plugin')
        self.blueprint_dir = blueprint_dir
        if 'CLOUDIFY_TEST_PUPPET_IP' in os.environ:
            self.logger.info('Using existing Puppet server at {0}'.format(
                os.environ['CLOUDIFY_TEST_PUPPET_IP']))
            self.puppet_server_ip = os.environ['CLOUDIFY_TEST_PUPPET_IP']
            self.puppet_server_id = None
            return

        self.logger.info('Setting up Puppet master')

        self.blueprint_yaml = blueprint_dir / 'puppet-server-by-puppet.yaml'

        with YamlPatcher(self.blueprint_yaml) as blueprint:
            bp_info = update_blueprint(self.env, blueprint, 'puppet-server')

        self.puppet_server_hostname = bp_info['hostnames'][0]

        def run(*args, **kwargs):
            return subprocess.check_output(*args, stderr=sys.stderr, **kwargs)

        self.puppet_server_id = self.test_id + '-puppet-master'
        id_ = self.puppet_server_id
        before, after = self.upload_deploy_and_execute_install(id_, id_)

        fip_node = find_node_state('ip', after['node_state'][id_])
        self.puppet_server_ip = fip_node['runtimeInfo']['floating_ip_address']

        fabric_env = fabric.api.env
        fabric_env.update({
            'timeout': 30,
            'user': bp_info['users'][0],
            'key_filename': get_agent_key_file(self.env),
            'host_string': self.puppet_server_ip,
        })

        setup_puppet_server(blueprint_dir)

        # raise RuntimeError('Remove this line later')

    def tearDown(self, *args, **kwargs):
        if self.puppet_server_id:
            self.execute_uninstall(self.puppet_server_id)
        super(PuppetPluginAgentTest, self).tearDown(*args, **kwargs)

    def test_puppet_agent(self):
        blueprint_dir = self.blueprint_dir
        self.blueprint_yaml = blueprint_dir / 'puppet-agent-test.yaml'
        with YamlPatcher(self.blueprint_yaml) as blueprint:
            bp_info = update_blueprint(self.env, blueprint, 'puppet-server', {
                'puppet_server_ip': self.puppet_server_ip,
            })

        id_ = self.test_id + '-puppet-agent-' + str(int(time.time()))
        before, after = self.upload_deploy_and_execute_install(id_, id_)

        # import pdb; pdb.set_trace()

        fip_node = find_node_state('ip', after['node_state'][id_])
        puppet_agent_ip = fip_node['runtimeInfo']['floating_ip_address']

        fabric_env = fabric.api.env
        fabric_env.update({
            'timeout': 30,
            'user': bp_info['users'][0],
            'key_filename': get_agent_key_file(self.env),
            'host_string': puppet_agent_ip,
        })

        f = '/tmp/cloudify_operation_create'

        out = fabric.api.run('[ -f {0} ]; echo $?'.format(f))
        self.assertEquals(out, '0')

        out = fabric.api.run('cat {0}'.format(f))
        self.assertEquals(out, id_)

        self.execute_uninstall(id_)
