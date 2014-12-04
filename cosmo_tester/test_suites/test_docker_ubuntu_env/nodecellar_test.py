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

# Test docker bootstrap and installation of nodecellar on Ubuntu 14.04
from cosmo_tester.framework.util import YamlPatcher
from cosmo_tester.test_suites.test_blueprints import nodecellar_test


class DockerNodeCellarTest(nodecellar_test.NodecellarAppTest):

    UBUNTU_TRUSTY_IMAGE_MANE = 'Ubuntu Server 14.04.1 LTS (amd64 20140927)'
    ' - Partner Image'
    UNBUNTU_TRUSTY_IMAGE_ID = 'bec3cab5-4722-40b9-a78a-3489218e22fe'

    def test_docker_and_nodecellar(self):
        self._test_nodecellar_impl('openstack-blueprint.yaml',
                                   self.UBUNTU_TRUSTY_IMAGE_MANE,
                                   self.env.flavor_name)

    def modify_blueprint(self, image_name, flavor_name):
        with YamlPatcher(self.blueprint_yaml) as patch:
            vm_props_path = 'node_types.vm_host.properties'
            # Add required docker param. See CFY-816
            patch.merge_obj('{0}.cloudify_agent.default'
                            .format(vm_props_path), {
                                'home_dir': '/home/ubuntu'
                            })
            vm_type_path = 'node_types.vm_host.properties'
            patch.merge_obj('{0}.server.default'.format(vm_type_path), {
                'image_name': image_name,
                'flavor_name': flavor_name
            })
            # Use ubuntu trusty 14.04 as agent machine
            patch.merge_obj('{0}.server.default'.format(vm_props_path), {
                'image': self.UNBUNTU_TRUSTY_IMAGE_ID
            })
