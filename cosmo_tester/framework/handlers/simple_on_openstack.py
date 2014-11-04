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


from cosmo_cli.cosmo_cli import ProviderConfig
from cloudify_openstack.cloudify_openstack import ProviderManager

from cosmo_tester.framework.util import fix_keypath
from cosmo_tester.framework.util import get_cloudify_config
from cosmo_tester.framework.handlers.openstack import OpenstackHandler


def get_openstack_cloudify_config(simple_cloudify_config):
    # load openstack configuration skeleton
    config_name = 'cloudify-config-openstack-on-hp.yaml'
    openstack_config = get_cloudify_config(config_name)
    # update with values injected into current config (simple)
    openstack_config['keystone'].update(
        simple_cloudify_config['keystone'])
    openstack_config['cloudify']['resources_prefix'] = simple_cloudify_config[
        'cloudify'].get('resources_prefix', '')
    return openstack_config


def get_provider_manager(openstack_config):
    # use dict config wrapper used by cosmo_cli
    openstack_config = ProviderConfig(openstack_config)
    pm = ProviderManager(openstack_config, is_verbose_output=True)
    pm.update_names_in_config()
    return pm


class SimpleOnOpenstackConfigReader(OpenstackHandler.CloudifyConfigReader):

    def __init__(self, cloudify_config):
        self.original_config = cloudify_config
        openstack_config = get_openstack_cloudify_config(cloudify_config)
        super(SimpleOnOpenstackConfigReader, self).__init__(openstack_config)

    @property
    def public_ip(self):
        return self.original_config['public_ip']

    @property
    def private_ip(self):
        return self.original_config['private_ip']

    @property
    def ssh_key_path(self):
        return self.original_config['ssh_key_path']

    @property
    def ssh_username(self):
        return self.original_config['ssh_username']

    @property
    def context(self):
        return self.original_config['context']


class SimpleOnOpenstackCleanupContext(OpenstackHandler.CleanupContext):

    def __init__(self, context_name, env):
        openstack_config = get_openstack_cloudify_config(env.cloudify_config)
        super(SimpleOnOpenstackCleanupContext, self).__init__(context_name,
                                                              openstack_config)


class SimpleOnOpenstackHandler(OpenstackHandler):
    """
    We derive from OpenstackHandler to get the constants it defines
    also defined here (image names, flavors, etc...)
    """

    provider = 'simple_provider'
    CleanupContext = SimpleOnOpenstackCleanupContext
    CloudifyConfigReader = SimpleOnOpenstackConfigReader

    def before_bootstrap(self):
        openstack_config = get_openstack_cloudify_config(
            self.env.cloudify_config)
        # reuse openstack provider to setup an environment in which
        # everything is already configured.
        pm = get_provider_manager(openstack_config)
        public_ip, private_ip, key_path, username, context = pm.provision()
        # update the simple config with the bootstrap info
        with self.update_cloudify_config() as patch:
            patch.obj.update(dict(
                public_ip=public_ip,
                private_ip=private_ip,
                ssh_key_path=key_path,
                ssh_username=username,
                context=context
            ))
            # the implementation is such, that the values when reading these
            # properties from the env are actually read from the openstack
            # config, so we copy these values to the simple config
            # for the bootstrap process
            patch.set_value('compute.region', self.env.region)
            patch.set_value('cloudify.agents.config.user',
                            self.env.cloudify_agent_user)
            key_prop = 'compute.agent_servers.agents_keypair.private_key_path'
            key_val = fix_keypath(self.env,
                                  self.env.agent_key_path)
            patch.set_value(key_prop, key_val)

    def after_bootstrap(self, provider_context):
        super(SimpleOnOpenstackHandler, self).after_bootstrap(provider_context)
        openstack_config = get_openstack_cloudify_config(
            self.env.cloudify_config)
        pm = get_provider_manager(openstack_config)
        config_reader = self.env._config_reader
        driver = pm._get_driver(openstack_config)
        driver.copy_files_to_manager(
            mgmt_ip=config_reader.public_ip,
            ssh_key=config_reader.ssh_key_path,
            ssh_user=config_reader.ssh_username)

handler = SimpleOnOpenstackHandler
