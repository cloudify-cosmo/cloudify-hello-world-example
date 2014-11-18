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
import os

from cosmo_tester.framework import vsphere_utils

from cosmo_tester.framework.handlers import BaseHandler, BaseCloudifyInputsConfigReader
import random
from cosmo_tester.framework.testenv import CLOUDIFY_TEST_NO_CLEANUP

__author__ = 'boris'

def get_vsphere_state(env):
    #vms = vsphere_utils.get_all_vms('192.168.30.1', 'administrator@vsphere.local', 'Cloudify1!', '443')
    vms = vsphere_utils.get_all_vms(env.vsphere_url, env.vsphere_username, env.vsphere_password, '443')
    for vm in vms:
        vsphere_utils.print_vm_info(vm)
    return vms


class VsphereCleanupContext(BaseHandler.CleanupContext):
    def __init__(self, context_name, env):
        super(VsphereCleanupContext, self).__init__(context_name, env)
        self.vsphere_state_before = get_vsphere_state(env)


    def cleanup(self):
        super(VsphereCleanupContext, self).cleanup()
        if os.environ.get(CLOUDIFY_TEST_NO_CLEANUP):
            self.logger.warn('SKIPPING cleanup: of the resources')
            return
        vsphere_state_after = get_vsphere_state(self.config)
        diff = self.calc_diff(self.vsphere_state_before, vsphere_state_after)
        for vm in diff:
            #TODO call terminate here
            #vsphere_utils.terminate_vm(self.config)
            vsphere_utils.print_vm_info(vm)

    #TODO test this method
    def calc_diff(self, vms_before, vms_after):
        return list(set(vms_after) - set(vms_before))


class CloudifyVsphereInputsConfigReader(BaseCloudifyInputsConfigReader):

    def __init__(self, cloudify_config, manager_blueprint_path, **kwargs):
        super(CloudifyVsphereInputsConfigReader, self).__init__(
            cloudify_config, manager_blueprint_path=manager_blueprint_path,
            **kwargs)

    @property
    def management_server_name(self):
        return self.config['manager_server_name']

    @property
    def agent_key_path(self):
        return self.config['agent_private_key_path']

    @property
    def management_user_name(self):
        return self.config['manager_server_user']

    @property
    def management_key_path(self):
        return self.config['manager_private_key_path']

    @property
    def external_network_name(self):
        return self.config['external_network_name']

    @property
    def vsphere_username(self):
        return self.config['vsphere_username']

    @property
    def vsphere_password(self):
        return self.config['vsphere_password']

    @property
    def vsphere_datacenter_name(self):
        return self.config['vsphere_datacenter_name']

    @property
    def vsphere_url(self):
        return self.config['vsphere_url']

    @property
    def management_network_name(self):
        return self.config['management_network_name']

    @property
    def external_network_name(self):
        return self.config['external_network_name']


class VsphereHandler(BaseHandler):
    provider = 'vsphere'
    CleanupContext = VsphereCleanupContext
    manager_blueprint = 'manager_blueprint/vsphere.yaml'
    CloudifyConfigReader = CloudifyVsphereInputsConfigReader

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
            patch.append_value('manager_server_name', suffix)
        print "before bs"

    def after_teardown(self):
        print "after teardown stuff"


handler = VsphereHandler
