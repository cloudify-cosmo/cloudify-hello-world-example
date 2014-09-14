#! /usr/bin/env python
# flake8: NOQA

import sys
import os

from cosmo_tester.framework.util import YamlPatcher

shared_properties = {
    'RESOURCE_PREFIX'       : 'cloudify.resources_prefix',
    'COMPONENTS_PACKAGE_URL': 'cloudify.server.packages.components_package_url',
    'CORE_PACKAGE_URL'      : 'cloudify.server.packages.core_package_url',
    'UI_PACKAGE_URL'        : 'cloudify.server.packages.ui_package_url',
    'UBUNTU_PACKAGE_URL'    : 'cloudify.agents.packages.ubuntu_agent_url',
    'CENTOS_PACKAGE_URL'    : 'cloudify.agents.packages.centos_agent_url',
    'WINDOWS_PACKAGE_URL'   : 'cloudify.agents.packages.windows_agent_url',
}

ec2_properties = {
    'AWS_ACCESS_ID'         : 'connection.access_id',
    'AWS_SECRET_KEY'        : 'connection.secret_key',
}

openstack_properties = {
    'KEYSTONE_PASSWORD'     : 'keystone.password',
    'KEYSTONE_USERNAME'     : 'keystone.username',
    'KEYSTONE_TENANT'       : 'keystone.tenant_name',
    'KEYSTONE_AUTH_URL'     : 'keystone.auth_url',
}

def main():
    yaml_path = sys.argv[1]
    handler = os.environ.get('CLOUDIFY_TEST_HANDLER_MODULE')
    if handler in [
        'cosmo_tester.framework.handlers.openstack',
        'cosmo_tester.framework.handlers.simple_on_openstack']:
        cloud_properties = openstack_properties
    elif handler == 'cosmo_tester.framework.handlers.ec2':
        cloud_properties = ec2_properties
    else:
        raise RuntimeError('Unsupported handler: {}'.format(handler))

    properties = {}
    properties.update(shared_properties)
    properties.update(cloud_properties)

    with YamlPatcher(yaml_path) as patch:
        for env_var, prop_path in properties.items():
            value = os.environ.get(env_var)
            if value:
                patch.set_value(prop_path, value)

if __name__ == '__main__':
    main()
