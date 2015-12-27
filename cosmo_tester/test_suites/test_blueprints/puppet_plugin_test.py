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

import subprocess
import tempfile
import time
import os
from os.path import dirname

import requests
import fabric.api
import fabric.context_managers
from path import path

from cosmo_tester.framework.testenv import TestCase
from cosmo_tester.framework.util import YamlPatcher, get_actual_keypath


PUPPET_MASTER_VERSION = '3.5.1-1puppetlabs1'

# TODO: whoever did a review for this, should not have accepted this reference
# to some external FewBytes repo.
# see the chef test and do something similar
MANIFESTS_URL = ('https://github.com/Fewbytes/cosmo-tester-puppet-downloadable'
                 '/archive/master.tar.gz')

MANIFESTS_FILE_NAME = 'manifests.tar.gz'


def find_node_state(node_name, nodes_state):
    pfx = node_name + '_'
    matches = [v for k, v in nodes_state.items() if k.startswith(pfx)]
    if len(matches) != 1:
        raise RuntimeError("Failed to find node {0}".format(node_name))
    return matches[0]


def get_nodes_of_type(blueprint, type_):
    return [node_obj for _, node_obj in blueprint.obj[
        'node_templates'].iteritems() if node_obj['type'] == type_]


def update_blueprint(env, blueprint, hostname, userdata_vars=None):
    hostname_base = 'system-test-{0}-{1}'.format(
        time.strftime("%Y%m%d-%H%M"), hostname)
    vm = get_nodes_of_type(blueprint, 'cloudify.openstack.nodes.Server')[0]
    hostnames = [hostname_base]

    users = []

    vm_hostname = hostname_base
    sg = '{0}{1}'.format(env.resources_prefix, 'puppet_sg')

    inputs = {
        'flavor': env.flavor_name,
        'image': env.ubuntu_precise_image_name,
        'server_name': vm_hostname,
        'security_groups': [sg]
    }

    server_userdata = """#!/bin/bash -ex
grep -q "{hostname}" /etc/hosts || echo "127.0.0.1 {hostname}" >> /etc/hosts"""

    client_userdata = """#!/bin/bash -ex
grep -q puppet /etc/hosts || echo "{puppet_server_ip} puppet" >> /etc/hosts"""

    props = vm['properties']['server']
    if 'userdata' in props:
        if userdata_vars:
            userdata = client_userdata.format(**userdata_vars)
        else:
            hostname = '{0}{1}'.format(env.resources_prefix,
                                       vm_hostname).replace('_', '-')
            userdata = server_userdata.format(hostname=hostname)
        inputs['userdata'] = userdata
    users.append('ubuntu')
    return {'hostnames': hostnames, 'users': users}, inputs


def setup_puppet_server(local_dir):
    # import pdb; pdb.set_trace()
    for p in 'puppetmaster-common', 'puppetmaster':
        cmd = 'apt-get install -y {0}={1}'.format(p, PUPPET_MASTER_VERSION)
        fabric.api.sudo(cmd)
    remote_path = '/etc/puppet'
    local_path = (
        path(dirname(dirname(dirname(os.path.realpath(__file__))))) /
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

        self.blueprint_yaml = (
            blueprint_dir / 'puppet-server-by-puppet-blueprint.yaml')

        with YamlPatcher(self.blueprint_yaml) as blueprint:
            bp_info, inputs = update_blueprint(self.env, blueprint,
                                               'puppet-master')

        self.puppet_server_hostname = bp_info['hostnames'][0]

        self.puppet_server_id = self.test_id + '-puppet-master'
        id_ = self.puppet_server_id
        before, after = self.upload_deploy_and_execute_install(
            id_, id_, inputs=inputs)

        fip_node = find_node_state('ip', after['node_state'][id_])
        self.puppet_server_ip = \
            fip_node['runtime_properties']['floating_ip_address']

        fabric_env = fabric.api.env
        fabric_env.update({
            'timeout': 30,
            'user': bp_info['users'][0],
            'key_filename': get_actual_keypath(self.env,
                                               self.env.agent_key_path),
            'host_string': self.puppet_server_ip,
        })

        setup_puppet_server(blueprint_dir)

    def tearDown(self, *args, **kwargs):
        if self.puppet_server_id:
            self.execute_uninstall(self.puppet_server_id)
        super(PuppetPluginAgentTest, self).tearDown(*args, **kwargs)

    def test_puppet_agent(self):
        blueprint_dir = self.blueprint_dir
        self.blueprint_yaml = (
            blueprint_dir / 'puppet-agent-test-blueprint.yaml')
        with YamlPatcher(self.blueprint_yaml) as blueprint:
            bp_info, inputs = update_blueprint(
                self.env, blueprint,
                'puppet-agent', {
                    'puppet_server_ip': self.puppet_server_ip,
                })

        id_ = self.test_id + '-puppet-agent-' + str(int(time.time()))
        before, after = self.upload_deploy_and_execute_install(
            id_, id_, inputs=inputs)

        # import pdb; pdb.set_trace()

        fip_node = find_node_state('ip', after['node_state'][id_])
        puppet_agent_ip = fip_node['runtime_properties']['floating_ip_address']

        fabric_env = fabric.api.env
        fabric_env.update({
            'timeout': 30,
            'user': bp_info['users'][0],
            'key_filename': get_actual_keypath(self.env,
                                               self.env.agent_key_path),
            'host_string': puppet_agent_ip,
        })

        f = '/tmp/cloudify_operation_create'

        out = fabric.api.run('[ -f {0} ]; echo $?'.format(f))
        self.assertEquals(out, '0')

        out = fabric.api.run('cat {0}'.format(f))
        self.assertEquals(out, id_)

        self.execute_uninstall(id_)


class PuppetPluginStandaloneTest(TestCase):

    def execute_and_check(self, id_, inputs=None):
        before, after = self.upload_deploy_and_execute_install(
            id_, id_, inputs=inputs)

        fip_node = find_node_state('ip', after['node_state'][id_])
        puppet_standalone_ip = \
            fip_node['runtime_properties']['floating_ip_address']

        page = requests.get('http://{0}:8080'.format(puppet_standalone_ip))
        self.assertIn('Cloudify Hello World', page.text,
                      'Expected text not found in response')
        self.execute_uninstall(id_)

    def test_puppet_standalone_without_download(self):
        id_ = "{0}-puppet-standalone-{1}-{2}".format(self.test_id,
                                                     'nodl',
                                                     str(int(time.time())))
        blueprint_dir = self.copy_blueprint('puppet-plugin')

        self.blueprint_yaml = (
            blueprint_dir / 'puppet-standalone-test-blueprint.yaml')
        with YamlPatcher(self.blueprint_yaml) as blueprint:
            _, inputs = update_blueprint(self.env, blueprint,
                                         'puppet-standalone-nodl')
        self.execute_and_check(id_, inputs=inputs)

    def _test_puppet_standalone_with_download(self, manifests_are_from_url):
        """ Tests standalone Puppet.
        manifests_are_from_url True ->
            puppet_config:
                download: http://....
                execute: -- removed
                manifest: site.pp
        manifests_are_from_url False ->
                download: /....
                execute:
                    configure: -- removed
        """

        mode = ['resource', 'url'][manifests_are_from_url]
        id_ = "{0}-puppet-standalone-{1}-{2}".format(self.test_id,
                                                     mode,
                                                     str(int(time.time())))
        _url = ('http://' +
                self.env.management_ip +
                '/resources/blueprints/' +
                id_ +
                '/' +
                MANIFESTS_FILE_NAME)

        download_from = ['/' + MANIFESTS_FILE_NAME, _url][
            manifests_are_from_url]

        def call(cmd):
            print("Executing: {0}".format(' '.join(cmd)))
            # subprocess.check_call(cmd, stdout=sys.stdout, stderr=sys.stderr)
            # Trying without piping since this caused the following problem:
            # Traceback (most recent call last):
            # File "/usr/lib/python2.7/subprocess.py", line 506, in check_call
            # retcode = call(*popenargs, **kwargs)
            # File "/usr/lib/python2.7/subprocess.py", line 493, in call
            # return Popen(*popenargs, **kwargs).wait()
            # File "/usr/lib/python2.7/subprocess.py", line 672, in __init__
            # errread, errwrite) = self._get_handles(stdin, stdout, stderr)
            # File "/usr/lib/python2.7/subprocess.py", line 1053, in _get_handles  # noqa
            # c2pwrite = stdout.fileno()
            # AttributeError: 'Tee' object has no attribute 'fileno'
            subprocess.check_call(cmd)

        blueprint_dir = self.copy_blueprint('puppet-plugin')

        # Download manifests
        file_name = os.path.join(tempfile.gettempdir(),
                                 self.test_id + '.manifests.tar.gz')
        temp_dir = tempfile.mkdtemp('.manifests', self.test_id + '.')
        call(['wget', '-O', file_name, MANIFESTS_URL])
        call(['tar', '-vxzf', file_name, '-C', temp_dir,
              '--xform', 's/^[^\/]\+\///'])
        call(['tar', '-vczf', os.path.join(blueprint_dir, MANIFESTS_FILE_NAME),
              '-C', temp_dir, '.'])

        self.blueprint_yaml = (
            blueprint_dir / 'puppet-standalone-test-blueprint.yaml')
        with YamlPatcher(self.blueprint_yaml) as blueprint:
            _, inputs = update_blueprint(self.env, blueprint,
                                         'puppet-standalone-' + mode)
            conf = blueprint.obj['node_templates']['puppet_node_one'][
                'properties']['puppet_config']
            conf['download'] = download_from
            if manifests_are_from_url:
                del conf['execute']
                conf['manifest'] = {'start': 'manifests/site.pp'}
            else:
                del conf['execute']['configure']
        self.execute_and_check(id_, inputs=inputs)

    def test_puppet_standalone_with_resource(self):
        self._test_puppet_standalone_with_download(False)

    def test_puppet_standalone_with_url(self):
        self._test_puppet_standalone_with_download(True)
