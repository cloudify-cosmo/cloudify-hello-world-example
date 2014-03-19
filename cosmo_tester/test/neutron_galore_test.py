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


__author__ = 'dan'


import shutil

from cosmo_tester.framework.testenv import TestCase
from cosmo_tester.framework.util import get_blueprint_path, YamlPatcher


class NeutronGaloreTest(TestCase):

    flavor_name = 'm1.small'
    host_name = 'novaservertest'
    image_name = 'Ubuntu 12.04 64bit'
    security_groups = ['neutron_test_security_group_dst']

    def test_neutron_galore(self):
        self.security_groups.append(self.env.agents_security_group)

        blueprint_path = self.copy_blueprint('neutron-galore')
        self.blueprint_yaml = blueprint_path / 'blueprint.yaml'
        self.modify_blueprint()

        before, after = self.upload_deploy_and_execute_install()

        self.post_install_assertions(before, after)

        self.execute_uninstall()

        self.post_uninstall_assertions()

    def copy_python_webserver_blueprint(self, target):
        shutil.copytree(get_blueprint_path('neutron-galore'), target)

    def modify_blueprint(self):
        with YamlPatcher(self.blueprint_yaml) as patch:
            vm_path = 'blueprint.nodes.[0].properties'
            patch.set_value('{0}.management_network_name'.format(vm_path),
                            self.env.management_network_name)
            patch.set_value('{0}.worker_config.key'.format(vm_path),
                            self.env.agent_key_path)
            patch.merge_obj('{0}.server'.format(vm_path), {
                'name': self.host_name,
                'image_name': self.image_name,
                'flavor_name': self.flavor_name,
                'key_name': self.env.agent_keypair_name,
                'security_groups': self.security_groups,
            })

            router_path = 'blueprint.nodes[3].properties.router'\
                          '.external_gateway_info.network_name'
            patch.set_value(router_path, self.env.external_network_name)

            ip_path = 'blueprint.nodes[7].properties.floatingip'\
                      'floating_network_name'
            patch.set_value(ip_path, self.env.external_network_name)

    def post_install_assertions(self, before_state, after_state):
        pass

    def post_uninstall_assertions(self):
        pass
