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

import logging
from contextlib import contextmanager

import yaml
from path import path

from cosmo_tester.framework.util import YamlPatcher


class BaseCleanupContext(object):

    def __init__(self, context_name, env):
        self.context_name = context_name
        self.env = env
        self.logger = logging.getLogger('CleanupContext')
        self.logger.setLevel(logging.DEBUG)
        self.skip_cleanup = self.env.handler_configuration.get(
            'skip_cleanup', False)

    def cleanup(self):
        pass


class BaseCloudifyConfigReader(object):

    def __init__(self, cloudify_config, **kwargs):
        self.config = cloudify_config


class BaseCloudifyProviderConfigReader(BaseCloudifyConfigReader):

    def __init__(self, cloudify_config, **kwargs):
        super(BaseCloudifyProviderConfigReader, self).__init__(cloudify_config)

    @property
    def cloudify_agent_user(self):
        return self.config['cloudify']['agents']['config']['user']

    @property
    def resources_prefix(self):
        return self.config['cloudify'].get('resources_prefix', '')


class BaseCloudifyInputsConfigReader(BaseCloudifyConfigReader):

    def __init__(self, cloudify_config, manager_blueprint_path, **kwargs):
        super(BaseCloudifyInputsConfigReader, self).__init__(cloudify_config)
        self.manager_blueprint = yaml.load(path(manager_blueprint_path).text())

    @property
    def cloudify_agent_user(self):
        return self.config['agents_user']

    @property
    def resources_prefix(self):
        return self.config['resources_prefix']


class BaseHandler(object):

    provider = 'base'
    CleanupContext = BaseCleanupContext
    CloudifyConfigReader = BaseCloudifyConfigReader

    def __init__(self, env):
        self.env = env
        self.CloudifyConfigReader = BaseCloudifyProviderConfigReader if \
            env.is_provider_bootstrap else BaseCloudifyInputsConfigReader
        for attr_name, attr_value in env.handler_configuration.get(
                'properties', {}).items():
            setattr(self, attr_name, attr_value)

    @contextmanager
    def update_cloudify_config(self):
        with YamlPatcher(self.env.cloudify_config_path,
                         is_json=not self.env.is_provider_bootstrap) as patch:
            yield patch
        self.env.cloudify_config = yaml.load(
            self.env.cloudify_config_path.text())
        self.env._config_reader = self.CloudifyConfigReader(
            self.env.cloudify_config,
            manager_blueprint_path=self.env._manager_blueprint_path)

    def before_bootstrap(self):
        pass

    def after_bootstrap(self, provider_context):
        pass

    def after_teardown(self):
        pass

handler = BaseHandler
