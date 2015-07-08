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

from cosmo_tester.framework.util import YamlPatcher, process_variables


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


class BaseCloudifyInputsConfigReader(object):

    def __init__(self, cloudify_config, manager_blueprint_path, **kwargs):
        self.config = cloudify_config
        self.manager_blueprint = yaml.load(path(manager_blueprint_path).text())

    @property
    def cloudify_agent_user(self):
        return self.config['agents_user']

    @property
    def resources_prefix(self):
        return self.config['resources_prefix']

    @property
    def transient_deployment_workers(self):
        manager = self.manager_blueprint['node_templates'].get('manager', {})
        bootstrap_context = manager.get('properties', {}).get('cloudify', {})
        return bootstrap_context.get('transient_deployment_workers', False)

    @property
    def management_user_name(self):
        raise NotImplementedError('management_user_name property must be '
                                  'implemented by concrete handler config '
                                  'reader')

    @property
    def management_key_path(self):
        raise NotImplementedError('management_key_path property must be '
                                  'implemented by concrete handler config '
                                  'reader')

    @property
    def docker_url(self):
        manager = self.manager_blueprint['node_templates'].get('manager', {})
        packages = manager.get('properties', {}).get('cloudify_packages', {})
        return packages.get('docker', {}).get('docker_url')


class BaseHandler(object):

    # The following attributes are mainly for documentation
    # purposes. Handler subclasses should override them
    # to have the appropriate inputs file read loaded
    CleanupContext = BaseCleanupContext
    CloudifyConfigReader = BaseCloudifyInputsConfigReader

    def __init__(self, env):
        self.env = env
        properties_name = env.handler_configuration.get('properties')
        if properties_name:
            properties = env.suites_yaml['handler_properties'][properties_name]
            processed_properties = process_variables(env.suites_yaml,
                                                     properties)
            for attr_name, attr_value in processed_properties.items():
                setattr(self, attr_name, attr_value)

    @contextmanager
    def update_cloudify_config(self):
        with YamlPatcher(self.env.cloudify_config_path) as patch:
            yield patch
        self.env.cloudify_config = yaml.load(
            self.env.cloudify_config_path.text())
        self.env._config_reader = self.CloudifyConfigReader(
            self.env.cloudify_config,
            manager_blueprint_path=self.env._manager_blueprint_path)

    @property
    def is_docker_bootstrap(self):
        return self.env._config_reader.docker_url is not None

    def before_bootstrap(self):
        pass

    def after_bootstrap(self, provider_context):
        pass

    def after_teardown(self):
        pass

handler = BaseHandler
