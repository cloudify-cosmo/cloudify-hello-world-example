########
# Copyright (c) 2018 Cloudify Platform Ltd. All rights reserved
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

from cosmo_tester.framework.test_hosts import (
    REMOTE_OPENSTACK_CONFIG_PATH,
    REMOTE_PRIVATE_KEY_PATH
)

MOM_PLUGIN_VERSION = '2.0.1'
MOM_PLUGIN_WGN_URL = 'https://github.com/Cloudify-PS/manager-of-managers/releases/download/v{0}/cloudify_manager_of_managers-{0}-py27-none-linux_x86_64.wgn'.format(MOM_PLUGIN_VERSION)  # NOQA
MOM_PLUGIN_YAML_URL = 'https://github.com/Cloudify-PS/manager-of-managers/releases/download/v{0}/cmom_plugin.yaml'.format(MOM_PLUGIN_VERSION)  # NOQA

OS_WGN_FILENAME_TEMPLATE = 'cloudify_openstack_plugin-{0}-py27-none-linux_x86_64-centos-Core.wgn'  # NOQA
OS_YAML_URL_TEMPLATE = 'http://www.getcloudify.org/spec/openstack-plugin/{0}/plugin.yaml'  # NOQA
OS_WGN_URL_TEMPLATE = 'http://repository.cloudifysource.org/cloudify/wagons/cloudify-openstack-plugin/{0}/{1}'  # NOQA

# This version of the plugin is used by the mom blueprint
OS_PLUGIN_VERSION = '2.12.0'
OS_PLUGIN_WGN_FILENAME = OS_WGN_FILENAME_TEMPLATE.format(OS_PLUGIN_VERSION)
OS_PLUGIN_WGN_URL = OS_WGN_URL_TEMPLATE.format(OS_PLUGIN_VERSION,
                                               OS_PLUGIN_WGN_FILENAME)
OS_PLUGIN_YAML_URL = OS_YAML_URL_TEMPLATE.format(OS_PLUGIN_VERSION)

# The version of the OS plugin used by Hello World Example
HW_OS_PLUGIN_VERSION = '2.0.1'
HW_OS_WGN_FILENAME = OS_WGN_FILENAME_TEMPLATE.format(HW_OS_PLUGIN_VERSION)
HW_OS_PLUGIN_WGN_URL = OS_WGN_URL_TEMPLATE.format(HW_OS_PLUGIN_VERSION,
                                                  HW_OS_WGN_FILENAME)
HW_OS_PLUGIN_YAML_URL = OS_YAML_URL_TEMPLATE.format(HW_OS_PLUGIN_VERSION)

HELLO_WORLD_URL = 'https://github.com/cloudify-cosmo/cloudify-hello-world-example/archive/4.5.zip'  # NOQA
HELLO_WORLD_BP = 'hello_world_bp'
HELLO_WORLD_DEP = 'hello_world_dep'

TENANT_1 = 'tenant_1'
TENANT_2 = 'tenant_2'

FIRST_DEP_INDICATOR = '0'
SECOND_DEP_INDICATOR = '1'

TIER_2_SNAP_ID = 'snapshot_id'

INSTALL_RPM_PATH = '/etc/cloudify/cloudify-manager-install.rpm'
HW_OS_PLUGIN_WGN_PATH = '/etc/cloudify/{0}'.format(HW_OS_WGN_FILENAME)
HW_OS_PLUGIN_YAML_PATH = '/etc/cloudify/plugin.yaml'

SECRET_STRING_KEY = 'test_secret_from_string'
SECRET_STRING_VALUE = 'test_secret_value'
SECRET_FILE_KEY = 'test_secret_from_file'

BLUEPRINT_ZIP_PATH = '/etc/cloudify/cloudify-hello-world-example.zip'

SCRIPT_SH_PATH = '/etc/cloudify/script_1.sh'
SCRIPT_PY_PATH = '/etc/cloudify/script_2.py'

SSH_KEY_TMP_PATH = '/tmp/ssh_key'
OS_CONFIG_TMP_PATH = '/tmp/openstack_config.json'

SH_SCRIPT = '''#!/usr/bin/env bash
echo "Moving the SSH key..."
sudo cp {tmp_ssh_key_path} {ssh_key_path}
sudo chown cfyuser: {ssh_key_path}

echo "Moving the OS config..."
sudo cp {tmp_os_config_path} {os_config_path}
sudo chown cfyuser: {os_config_path}
'''.format(
    tmp_ssh_key_path=SSH_KEY_TMP_PATH,
    ssh_key_path=REMOTE_PRIVATE_KEY_PATH,
    tmp_os_config_path=OS_CONFIG_TMP_PATH,
    os_config_path=REMOTE_OPENSTACK_CONFIG_PATH
)

PY_SCRIPT = '''#!/usr/bin/env python
print 'Running a python script!'
'''
