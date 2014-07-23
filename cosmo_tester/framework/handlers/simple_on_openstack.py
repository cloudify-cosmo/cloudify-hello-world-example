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
from cosmo_tester.framework.handlers import BaseHandler
from cosmo_tester.framework.handlers.openstack import OpenstackCleanupContext


class SimpleOnOpenstackHandler(BaseHandler):
    provider = 'simple_provider'
    CleanupContext = OpenstackCleanupContext

    def before_bootstrap(self):
        # load openstack configuration skeleton
        config_name = 'cloudify-config-hp-paid-system-tests-tenant.yaml'
        openstack_config = get_cloudify_config(config_name)

        # update with values injected into current config (simple)
        openstack_config['keystone'].update(
            self.env.cloudify_config['keystone'])
        openstack_config['cloudify'][
            'resources_prefix'] = self.env.resources_prefix
        openstack_config = ProviderConfig(openstack_config)

        # reuse openstack provider to setup an environment in which
        # everything is already configured

        pm = ProviderManager(openstack_config, is_verbose_output=True)
        pm.update_names_in_config()
        public_ip, private_ip, key_path, username, context = pm.provision()

        # update the simple config with the the bootstrap info
        with self.update_cloudify_config() as patch:
            patch.obj.update(dict(
                public_ip=public_ip,
                private_ip=private_ip,
                ssh_key_path=key_path,
                ssh_username=username,
                context=context
            ))

handler = SimpleOnOpenstackHandler
