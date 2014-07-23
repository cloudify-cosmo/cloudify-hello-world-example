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


from cosmo_cli.cosmo_cli import ProviderConfig
from cloudify_openstack.cloudify_openstack import ProviderManager


from cosmo_tester.framework.util import get_cloudify_config
from cosmo_tester.framework.handlers.openstack import OpenstackHandler


def get_openstack_cloudify_config(simple_cloudify_config):
    # load openstack configuration skeleton
    config_name = 'cloudify-config-hp-paid-system-tests-tenant.yaml'
    openstack_config = get_cloudify_config(config_name)
    # update with values injected into current config (simple)
    openstack_config['keystone'].update(
        simple_cloudify_config['keystone'])
    openstack_config['cloudify']['resources_prefix'] = simple_cloudify_config[
        'cloudify'].get('resources_prefix', '')
    return openstack_config


class SimpleOnOpenstackConfigReader(OpenstackHandler.CloudifyConfigReader):

    def __init__(self, cloudify_config):
        openstack_config = get_openstack_cloudify_config(cloudify_config)
        super(SimpleOnOpenstackConfigReader, self).__init__(openstack_config)


class SimpleOnOpenstackCleanupContext(OpenstackHandler.CleanupContext):

    def __init__(self, context_name, cloudify_config):
        openstack_config = get_openstack_cloudify_config(cloudify_config)
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
        # reuse openstack provider to setup an environment in which
        # everything is already configured.
        openstack_config = get_openstack_cloudify_config(
            self.env.cloudify_config)
        # use dict config wrapper used by cosmo_cli
        openstack_config = ProviderConfig(openstack_config)
        pm = ProviderManager(openstack_config, is_verbose_output=True)
        pm.update_names_in_config()
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

handler = SimpleOnOpenstackHandler
