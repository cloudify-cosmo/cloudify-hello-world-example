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

from cosmo_tester.framework.handlers import BaseHandler
import random

__author__ = 'boris'


class VsphereCleanupContext(BaseHandler.CleanupContext):
    def __init__(self, context_name, cloudify_config):
        super(VsphereCleanupContext, self).__init__(context_name,
                                                    cloudify_config)
        #self.before_run = ec2_infra_state(cloudify_config)
        #self.logger = logging.getLogger('Ec2CleanupContext')

    def cleanup(self):
        super(VsphereCleanupContext, self).cleanup()


class CloudifyVsphereConfigReader(BaseHandler.CloudifyConfigReader):
    def __init__(self, cloudify_config):
        super(CloudifyVsphereConfigReader, self).__init__(cloudify_config)

    @property
    def management_server_name(self):
        return self.config['compute']['management_server']['instance']['name']

    @property
    def agent_key_path(self):
        return self.config['compute']['agent_servers']['agents_keypair'][
            'private_key_path']

    @property
    def management_user_name(self):
        return self.config['compute']['management_server'][
            'user_on_management']

    @property
    def management_key_path(self):
        return self.config['compute']['management_server'][
            'management_keypair']['private_key_path']

    @property
    def agent_keypair_name(self):
        return self.config['compute']['agent_servers']['agents_keypair'][
            'name']

    @property
    def management_keypair_name(self):
        return self.config['compute']['management_server'][
            'management_keypair']['name']

    @property
    def datacenter_name(self):
        return self.config['connection']['datacenter_name']

    @property
    def dmz_network_name(self):
        return self.config['networking']['dmz_network']['name']

    @property
    def management_network_name(self):
        return self.config['networking']['management_network']['name']

    @property
    def application_network_name(self):
        return self.config['networking']['application_network']['name']


class VsphereHandler(BaseHandler):
    provider = 'vsphere'
    CleanupContext = VsphereCleanupContext
    CloudifyConfigReader = CloudifyVsphereConfigReader

    def __init__(self, env):
        super(VsphereHandler, self).__init__(env)
        self._template = None

    @property
    def template(self):
        self._template = 'ubuntu-configured-template'
        return self._template

    def before_bootstrap(self):
        with self.update_cloudify_config() as patch:
            suffix = '-%06x' % random.randrange(16 ** 6)
            patch.append_value('compute.management_server.instance.name',
                               suffix)

    def after_teardown(self):
        print "after teardown stuff"


handler = VsphereHandler
