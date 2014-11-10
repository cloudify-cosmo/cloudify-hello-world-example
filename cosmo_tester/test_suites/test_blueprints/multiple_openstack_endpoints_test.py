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


import novaclient.v1_1.client as nvclient
import neutronclient.v2_0.client as neclient

from cosmo_tester.framework.testenv import TestCase
from cosmo_tester.framework.handlers.openstack import openstack_infra_state


class MultipleOpenstackEndpointsTest(TestCase):

    def test_openstack_multiple_endpoints(self):

        blueprint_path = self.copy_blueprint('multiple-openstack-endpoints')
        self.blueprint_yaml = blueprint_path / 'blueprint.yaml'

        self.nova_url = 'https://region-a.geo-1.compute.hpcloudsvc.com/v2/11625898853599'
        self.neutron_url = 'https://region-a.geo-1.network.hpcloudsvc.com'

        self.nova, self.neutron = self.get_other_region_clients()

        inputs = {
            'keystone_username': self.env.keystone_username,
            'keystone_password': self.env.keystone_password,
            'keystone_tenant_name': self.env.keystone_tenant_name,
            'keystone_url': self.env.keystone_url,
            'region': self.env.region,
            'other_region_nova_url': self.nova_url,
            'other_region_neutron_url': self.neutron_url,
        }

        try:
            self.upload_deploy_and_execute_install(inputs=inputs)
            self.post_install_assertions()
        finally:
            self.clear_other_region_resources()

        self.execute_uninstall()
        self.post_uninstall_assertions()

    def post_install_assertions(self):
        openstack = openstack_infra_state(self.env)
        openstack_other_region = openstack_infra_state(self.env, self.nova,
                                                       self.neutron)
        self.assertEquals(1, len(openstack['key_pairs']))
        self.assertEquals(1, len(openstack['networks']))
        self.assertEquals(1, len(openstack_other_region['key_pairs']))
        self.assertEquals(1, len(openstack_other_region['networks']))

    def post_uninstall_assertions(self):
        openstack = openstack_infra_state(self.env)
        openstack_other_region = openstack_infra_state(self.env, self.nova,
                                                       self.neutron)
        self.assertEquals(0, len(openstack['key_pairs']))
        self.assertEquals(0, len(openstack['networks']))
        self.assertEquals(0, len(openstack_other_region['key_pairs']))
        self.assertEquals(0, len(openstack_other_region['networks']))

    def clear_other_region_resources(self):
        try:
            self.nova.keypairs.delete(self.p('keypair'))
        except Exception:
            pass
        try:
            self.neutron.delete_network(self.p('network'))
        except Exception:
            pass

    def get_other_region_clients(self):
        client_kwargs = dict(
            username=self.env.keystone_username,
            api_key=self.env.keystone_password,
            project_id=self.env.keystone_tenant_name,
            auth_url=self.env.keystone_url,
            region_name=self.env.region,
            bypass_url=self.nova_url,
            http_log_debug=False
        )
        nova = nvclient.Client(**client_kwargs)

        del(client_kwargs['region_name'])
        del(client_kwargs['bypass_url'])
        del(client_kwargs['http_log_debug'])
        client_kwargs['endpoint_url'] = self.neutron_url
        neutron = neclient.Client(**client_kwargs)

        return nova, neutron

    def p(self, name):
        return '{}{}'.format(self.env.resources_prefix, name)
