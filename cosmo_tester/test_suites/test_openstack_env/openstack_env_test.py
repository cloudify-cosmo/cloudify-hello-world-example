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


from cosmo_tester.framework.testenv import TestCase
from cloudify_openstack.cloudify_openstack import OpenStackConnector


class OpenstackEnvTest(TestCase):

    def setUp(self):
        super(OpenstackEnvTest, self).setUp()

    def test_connector_reads_neutron_url(self):
        self.assertEqual(None, self.env.neutron_url)

        connector = OpenStackConnector(self.env.cloudify_config)

        self.assertEqual(
            connector.get_neutron_client().httpclient.endpoint_url,
            'https://region-b.geo-1.network.hpcloudsvc.com')
