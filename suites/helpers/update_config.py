#! /usr/bin/env python
# flake8: NOQA

import sys
import os

from cosmo_tester.framework.util import YamlPatcher

properties = {
    'KEYSTONE_PASSWORD'     : 'keystone.password',
    'KEYSTONE_USERNAME'     : 'keystone.username',
    'KEYSTONE_TENANT'       : 'keystone.tenant_name',
    'KEYSTONE_AUTH_URL'     : 'keystone.auth_url',
    'RESOURCE_PREFIX'       : 'cloudify.resources_prefix',
    'COMPONENTS_PACKAGE_URL': 'cloudify.server.packages.components_package_url',
    'CORE_PACKAGE_URL'      : 'cloudify.server.packages.core_package_url',
    'UI_PACKAGE_URL'        : 'cloudify.server.packages.ui_package_url',
    'UBUNTU_PACKAGE_URL'    : 'cloudify.agents.packages.ubuntu_agent_url',
    'CENTOS_PACKAGE_URL'    : 'cloudify.agents.packages.centos_agent_url',
    'WINDOWS_PACKAGE_URL'   : 'cloudify.agents.packages.windows_agent_url',
}

with YamlPatcher(sys.argv[1]) as patch:
    for env_var, prop_path in properties.items():
        value = os.environ.get(env_var)
        if value:
            patch.set_value(prop_path, value)
