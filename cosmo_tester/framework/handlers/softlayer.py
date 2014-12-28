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

import SoftLayer
import random
import os
from cosmo_tester.framework.handlers import (
    BaseHandler,
    BaseCloudifyInputsConfigReader)

CLOUDIFY_TEST_NO_CLEANUP = 'CLOUDIFY_TEST_NO_CLEANUP'


class SoftLayerCleanupContext(BaseHandler.CleanupContext):

    def __init__(self, context_name, env):
        super(SoftLayerCleanupContext, self).__init__(context_name, env)

    def cleanup(self):
        super(SoftLayerCleanupContext, self).cleanup()
        resources_to_teardown = self.get_resources_to_teardown()
        if os.environ.get(CLOUDIFY_TEST_NO_CLEANUP):
            self.logger.warn('[{0}] SKIPPING cleanup: of the resources: {1}'
                             .format(self.context_name, resources_to_teardown))
            return
        self.logger.info('[{0}] Performing cleanup: will try removing these '
                         'resources: {1}'
                         .format(self.context_name, resources_to_teardown))

        leftovers = self.env.handler.remove_softlayer_resources(
            resources_to_teardown)
        self.logger.info('[{0}] Leftover resources after cleanup: {1}'
                         .format(self.context_name, leftovers))

    def get_resources_to_teardown(self):
        # TODO get softlayer resources to teardown
        pass


class CloudifySoftLayerInputsConfigReader(BaseCloudifyInputsConfigReader):

    def __init__(self, cloudify_config, manager_blueprint_path, **kwargs):
        super(CloudifySoftLayerInputsConfigReader, self).__init__(
            cloudify_config, manager_blueprint_path=manager_blueprint_path,
            **kwargs)

    @property
    def domain(self):
        return self.config['domain']


class SoftLayerHandler(BaseHandler):

    manager_blueprint = 'softlayer/softlayer.yaml'
    CleanupContext = SoftLayerCleanupContext
    CloudifyConfigReader = None

    small_flavor_id = 101

    def __init__(self, env):
        super(SoftLayerHandler, self).__init__(env)
        self.CloudifyConfigReader = CloudifySoftLayerInputsConfigReader

    def before_bootstrap(self):
        # TODO before bootstrap content
        pass

    def after_bootstrap(self, provider_context):
        # TODO after bootstrap content
        pass

    def after_teardown(self):
        # TODO after teardown content
        pass

    def _client_creds(self):
        return {
            'username': self.env.keystone_username,
            'api_key': self.env.keystone_password,
            'endpoint_url': self.env.keystone_url
        }

    def softlayer_clients(self):
        creds = self._client_creds()
        return SoftLayer.Client(**creds)

    def remove_softlayer_resources(self, resources_to_remove):
        pass


handler = SoftLayerHandler
