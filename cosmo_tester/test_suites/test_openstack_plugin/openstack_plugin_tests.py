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

import keystoneclient.v2_0.client as ksclient

from cosmo_tester.framework.testenv import TestCase


class OpenstackPluginTests(TestCase):

    def setUp(self):
        super(OpenstackPluginTests, self).setUp()

    def test_openstack_explicit_services_urls(self):
        blueprint_path = self.copy_blueprint(
            'openstack-explicit-services-urls')
        self.blueprint_path = blueprint_path / 'blueprint.yaml'

        inputs = {
            'keystone_username': self.env.keystone_username,
            'keystone_password': self.env.keystone_password,
            'keystone_tenant_name': self.env.keystone_tenant_name,
            'keystone_url': self.env.keystone_url,
            'region': self.env.region,
            'image': self.env.ubuntu_image_name,
            'flavor': self.env.flavor_name
        }

        # riding over bootstrap validation to easily check connection with the
        # various Openstack services
        # first, validating without using any explicit service urls
        self._validate_bootstrap_with_explicit_services_urls(inputs, '', '')

        # retrieving the public urls of the services from Keystone
        self.keystone = ksclient.Client(
            username=self.env.keystone_username,
            password=self.env.keystone_password,
            tenant_name=self.env.keystone_tenant_name,
            auth_url=self.env.keystone_url)

        nova_url = self._get_service_url_from_keystone(['compute', 'nova'])
        neutron_url = self._get_service_url_from_keystone(
            ['network', 'neutron'])

        # validating using the urls retrieved from keystone explicitly -
        # these urls should be the same ones that was used in the
        # previous validation, and thus this should pass as well
        self._validate_bootstrap_with_explicit_services_urls(
            inputs, nova_url, neutron_url)

        mock_url = 'http://mock.url'
        # validating when explicitly using mock urls - these should fail
        self._bootstrap_validation_expected_to_fail(inputs, mock_url, '',
                                                    'Neutron')
        self._bootstrap_validation_expected_to_fail(inputs, '', mock_url,
                                                    'Nova')

    def _validate_bootstrap_with_explicit_services_urls(self, inputs, nova_url,
                                                        neutron_url):
        inputs['nova_url'] = nova_url
        inputs['neutron_url'] = neutron_url
        inputs_file = self.cfy._get_inputs_in_temp_file(inputs, self.test_id)
        self.cfy.bootstrap(self.blueprint_path,
                           inputs_file=inputs_file,
                           reset_config=True,
                           validate_only=True,
                           task_retries=1)

    def _bootstrap_validation_expected_to_fail(self, inputs, nova_url,
                                               neutron_url,
                                               mocked_url_service_name):
        try:
            self._validate_bootstrap_with_explicit_services_urls(
                inputs, nova_url, neutron_url)
        except Exception:
            pass
        else:
            self.fail('Expected bootstrap validation to fail since explicit '
                      'mock url have been used for the {0} service'.format(
                          mocked_url_service_name))

    def _get_service_url_from_keystone(self, service_names):
        for service_name in service_names:
            service_url = \
                self.keystone.service_catalog.url_for(
                    service_type=service_name,
                    endpoint_type='publicURL',
                    region_name=self.env.region)

            if service_url:
                return service_url

        raise RuntimeError('Could not find public url for service names {'
                           '0}'.format(service_names))
