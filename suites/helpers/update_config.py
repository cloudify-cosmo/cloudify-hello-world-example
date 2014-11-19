#! /usr/bin/env python
# flake8: NOQA

import sys
import os

from cosmo_tester.framework.util import YamlPatcher

shared_provider_properties = {
    'RESOURCE_PREFIX'       : 'cloudify.resources_prefix',
    'COMPONENTS_PACKAGE_URL': 'cloudify.server.packages.components_package_url',
    'CORE_PACKAGE_URL'      : 'cloudify.server.packages.core_package_url',
    'UI_PACKAGE_URL'        : 'cloudify.server.packages.ui_package_url',
    'UBUNTU_PACKAGE_URL'    : 'cloudify.agents.packages.ubuntu_agent_url',
    'CENTOS_PACKAGE_URL'    : 'cloudify.agents.packages.centos_agent_url',
    'WINDOWS_PACKAGE_URL'   : 'cloudify.agents.packages.windows_agent_url',
    'WORKFLOW_TASK_RETRIES' : 'cloudify.workflows.task_retries',
}

ec2_provider_properties = {
    'AWS_ACCESS_ID'         : 'connection.access_id',
    'AWS_SECRET_KEY'        : 'connection.secret_key',
}

openstack_provider_properties = {
    'KEYSTONE_PASSWORD'     : 'keystone.password',
    'KEYSTONE_USERNAME'     : 'keystone.username',
    'KEYSTONE_TENANT'       : 'keystone.tenant_name',
    'KEYSTONE_AUTH_URL'     : 'keystone.auth_url',
}

shared_inputs_properties = {
    'RESOURCE_PREFIX'       : 'resources_prefix'
}

openstack_inputs_properties = {
    'KEYSTONE_USERNAME'     : 'keystone_username',
    'KEYSTONE_PASSWORD'     : 'keystone_password',
    'KEYSTONE_TENANT'       : 'keystone_tenant_name',
    'KEYSTONE_AUTH_URL'     : 'keystone_url'
}

shared_manager_blueprint_properties = {
    'COMPONENTS_PACKAGE_URL':
        'node_templates.manager.properties.cloudify_packages.server'
        '.components_package_url',
    'CORE_PACKAGE_URL'      :
        'node_templates.manager.properties.cloudify_packages.server'
        '.core_package_url',
    'UI_PACKAGE_URL'        :
        'node_templates.manager.properties.cloudify_packages.server'
        '.ui_package_url',
    'UBUNTU_PACKAGE_URL'    :
        'node_templates.manager.properties.cloudify_packages.agents'
        '.ubuntu_agent_url',
    'CENTOS_PACKAGE_URL'    :
        'node_templates.manager.properties.cloudify_packages.agents.'
        'centos_agent_url',
    'WINDOWS_PACKAGE_URL'   :
        'node_templates.manager.properties.cloudify_packages.agents'
        '.windows_agent_url',
    'WORKFLOW_TASK_RETRIES' :
        'node_templates.manager.properties.cloudify.workflows.task_retries',
}


def main():
    config_path = sys.argv[1]
    bootstrap_using_providers = \
        os.environ['BOOTSTRAP_USING_PROVIDERS'] == 'true'

    handler = os.environ.get('CLOUDIFY_TEST_HANDLER_MODULE')
    if handler in [
        'cosmo_tester.framework.handlers.openstack',
        'cosmo_tester.framework.handlers.simple_on_openstack']:
        cloud_specific_properties = openstack_provider_properties \
            if bootstrap_using_providers else openstack_inputs_properties
    elif handler == 'cosmo_tester.framework.handlers.openstack_nova_net':
        # openstack_nova_net handler currently has no cloud specific
        # properties, as the credentials information is simply hardcoded in its
        # inputs file, and there's no need to override it with quickbuild
        # data. if such a need arises, there should be separate env vars
        # for the nova net openstack credentials.
        cloud_specific_properties = {}
    elif handler == 'cosmo_tester.framework.handlers.ec2':
        cloud_specific_properties = ec2_provider_properties
    else:
        raise RuntimeError('Unsupported handler: {}'.format(handler))

    shared_properties = shared_provider_properties if \
        bootstrap_using_providers else shared_inputs_properties

    properties = {}
    properties.update(shared_properties)
    properties.update(cloud_specific_properties)
    _patch_properties(config_path, properties)

    if not bootstrap_using_providers:
        # in manager blueprints mode, we also need to update the blueprints
        # themselves for some configuration parameters which are not exposed
        # as inputs
        manager_blueprints_base_dir = os.environ['MANAGER_BLUEPRINTS_DIR']
        for manager_blueprint in _get_manager_blueprints(
                manager_blueprints_base_dir):
            _patch_properties(manager_blueprint,
                              shared_manager_blueprint_properties)


def _patch_properties(path, properties, is_json=False):
    with YamlPatcher(path, is_json) as patch:
        for env_var, prop_path in properties.items():
            value = os.environ.get(env_var)
            if value:
                if env_var is 'WORKFLOW_TASK_RETRIES':
                    value = int(value)
                patch.set_value(prop_path, value)


def _get_manager_blueprints(manager_blueprints_base_dir):
    manager_blueprints_paths = []

    manager_blueprints_dirs = \
        [os.path.join(manager_blueprints_base_dir, dir) for dir in os.listdir(
            manager_blueprints_base_dir) if os.path.isdir(os.path.join(
                manager_blueprints_base_dir, dir)) and not dir.startswith('.')]

    for manager_blueprint_dir in manager_blueprints_dirs:
        yaml_files = [os.path.join(manager_blueprint_dir, file) for file in
                      os.listdir(manager_blueprint_dir) if
                      file.endswith('.yaml')]
        if len(yaml_files) != 1:
            raise RuntimeError(
                'Expected exactly one .yaml file at {0}, but found {1}'.format(
                manager_blueprint_dir, len(yaml_files)))

        manager_blueprints_paths.append(yaml_files[0])

    return manager_blueprints_paths


if __name__ == '__main__':
    main()
