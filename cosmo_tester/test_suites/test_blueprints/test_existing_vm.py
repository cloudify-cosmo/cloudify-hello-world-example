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

__author__ = 'dank'

import time
import os

import fabric.api
import fabric.context_managers
from path import path

from cosmo_tester.framework.util import YamlPatcher
from cosmo_tester.framework.testenv import TestCase
from cosmo_tester.framework.openstack_api import openstack_clients


class ExistingVMTest(TestCase):

    def test_existing_vm(self):
        blueprint_path = self.copy_blueprint('existing-vm')
        self.blueprint_yaml = blueprint_path / 'blueprint.yaml'

        server_name = 'testexistingvm'
        remote_key_path = '/tmp/test-existing-vm.pem'
        key_name = 'test_existing_vm_key'

        nova_client, _ = openstack_clients(self.env.cloudify_config)
        self.create_keypair_and_copy_to_manager(
            nova_client=nova_client,
            remote_key_path=remote_key_path,
            key_name=key_name)
        private_server_ip = self.create_server(
            name=server_name,
            nova_client=nova_client,
            key_name=key_name,
            security_groups=[self.env.agents_security_group])

        self.modify_yaml(ip=private_server_ip,
                         remote_key_path=remote_key_path)

        self.upload_deploy_and_execute_install(fetch_state=False)

        instances = self.client.node_instances.list(deployment_id=self.test_id)
        middle_runtime_properties = [i.runtime_properties for i in instances
                                     if i.node_id == 'middle'][0]
        self.assertDictEqual({'working': True}, middle_runtime_properties)
        self.execute_uninstall()

    def modify_yaml(self, ip, remote_key_path):
        with YamlPatcher(self.blueprint_yaml) as patch:
            base_path = 'blueprint.nodes[0].properties'
            patch.set_value('{}.ip'.format(base_path), ip)
            patch.set_value('{}.cloudify_agent.key'.format(base_path),
                            remote_key_path)

    def create_keypair_and_copy_to_manager(self,
                                           nova_client,
                                           remote_key_path,
                                           key_name):
        key_file = path(self.workdir) / '{}.pem'.format(key_name)
        keypair = nova_client.keypairs.create(key_name)
        key_file.write_text(keypair.private_key)
        key_file.chmod(0600)

        management_key_path = os.path.expanduser(self.env.management_key_path)
        fabric.api.env.update({
            'timeout': 30,
            'user': self.env.cloudify_agent_user,
            'key_filename': path(management_key_path).abspath(),
            'host_string': self.env.management_ip,
        })
        fabric.api.put(local_path=key_file,
                       remote_path=remote_key_path)

    def create_server(self,
                      nova_client,
                      name,
                      key_name,
                      security_groups,
                      timeout=120):
        server = {
            'name': name,
            'image': self.env.ubuntu_image_id,
            'flavor': self.env.small_flavor_id,
            'key_name': key_name,
            'security_groups': security_groups
        }
        srv = nova_client.servers.create(**server)
        end = time.time() + timeout
        while srv.status != 'ACTIVE' and time.time() < end:
            sleep_time = 1
            time.sleep(sleep_time)
            srv = nova_client.servers.get(srv)
        if srv.status != 'ACTIVE':
            raise RuntimeError('Failed starting server')
