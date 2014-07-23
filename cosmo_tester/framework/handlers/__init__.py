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


import logging
from contextlib import contextmanager

import yaml

from cosmo_tester.framework.util import YamlPatcher


class BaseCleanupContext(object):

    logger = logging.getLogger('CleanupContext')
    logger.setLevel(logging.DEBUG)

    def __init__(self, context_name, cloudify_config):
        self.context_name = context_name
        self.cloudify_config = cloudify_config

    def cleanup(self):
        pass


class BaseCloudifyConfigReader(object):

    def __init__(self, cloudify_config):
        self.config = cloudify_config

    @property
    def cloudify_agent_user(self):
        return self.config['cloudify']['agents']['config']['user']

    @property
    def resources_prefix(self):
        return self.config['cloudify'].get('resources_prefix', '')


class BaseHandler(object):

    provider = 'base'
    CleanupContext = BaseCleanupContext
    CloudifyConfigReader = BaseCloudifyConfigReader

    def __init__(self, env):
        self.env = env

    @contextmanager
    def update_cloudify_config(self):
        with YamlPatcher(self.env.cloudify_config_path) as patch:
            yield patch
        self.env.cloudify_config = yaml.load(
            self.env.cloudify_config_path.text())
        self.env._config_reader = self.CloudifyConfigReader(
            self.env.cloudify_config)

    def before_bootstrap(self):
        pass

handler = BaseHandler
