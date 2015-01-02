import os

from cosmo_tester.framework.util import YamlPatcher

ssh_keys = {
    'SYSTEM_TESTS_MANAGER_KEY': '~/.ssh/shared-systemt-tests-manager.pem',
    'SYSTEM_TESTS_AGENT_KEY': '~/.ssh/shared-systemt-tests-agent.pem'
}

provider_properties = {
    'RESOURCE_PREFIX': 'cloudify.resources_prefix',
    'COMPONENTS_PACKAGE_URL':
        'cloudify.server.packages.components_package_url',
    'CORE_PACKAGE_URL': 'cloudify.server.packages.core_package_url',
    'UI_PACKAGE_URL': 'cloudify.server.packages.ui_package_url',
    'UBUNTU_PACKAGE_URL': 'cloudify.agents.packages.ubuntu_agent_url',
    'CENTOS_PACKAGE_URL': 'cloudify.agents.packages.centos_agent_url',
    'WINDOWS_PACKAGE_URL': 'cloudify.agents.packages.windows_agent_url',
    'WORKFLOW_TASK_RETRIES': 'cloudify.workflows.task_retries',
}

inputs_properties = {
    'RESOURCE_PREFIX': 'resources_prefix'
}

manager_blueprint_properties = {
    'UBUNTU_PACKAGE_URL':
        'node_templates.manager.properties.cloudify_packages.agents'
        '.ubuntu_agent_url',
    'CENTOS_PACKAGE_URL':
        'node_templates.manager.properties.cloudify_packages.agents.'
        'centos_agent_url',
    'WINDOWS_PACKAGE_URL':
        'node_templates.manager.properties.cloudify_packages.agents'
        '.windows_agent_url',
    'WORKFLOW_TASK_RETRIES':
        'node_templates.manager.properties.cloudify.workflows.task_retries',
}

packages_manager_blueprint_properties = {
    'COMPONENTS_PACKAGE_URL':
        'node_templates.manager.properties.cloudify_packages.server'
        '.components_package_url',
    'CORE_PACKAGE_URL':
        'node_templates.manager.properties.cloudify_packages.server'
        '.core_package_url',
    'UI_PACKAGE_URL':
        'node_templates.manager.properties.cloudify_packages.server'
        '.ui_package_url',
}

docker_manager_blueprint_properties = {
    'DOCKER_IMAGE_URL':
        'node_templates.manager.properties.cloudify_packages.docker'
        '.docker_url'
}


def update_config(config_path,
                  bootstrap_using_providers,
                  bootstrap_using_docker,
                  handler_update_config,
                  manager_blueprints_dir):

    if bootstrap_using_providers:
        patch_provider_properties(config_path, provider_properties)
        patch_provider_properties(
            config_path,
            handler_update_config.provider_properties)
    else:
        patch_inputs_properties(config_path, provider_properties)
        patch_inputs_properties(config_path,
                                handler_update_config.inputs_properties)

    if bootstrap_using_providers:
        return

    # in manager blueprints mode, we also need to update the blueprints
    # themselves for some configuration parameters which are not exposed
    # as inputs
    manager_blueprints_for_patching = dict(
        manager_blueprint_properties.items() +
        (docker_manager_blueprint_properties.items() if
            bootstrap_using_docker else
            packages_manager_blueprint_properties.items()))

    for manager_blueprint in _get_manager_blueprints(
            manager_blueprints_dir):
        patch_manager_blueprint_properties(manager_blueprint,
                                           manager_blueprints_for_patching)

    if hasattr(handler_update_config, 'update_config'):
        handler_update_config.update_config(manager_blueprints_dir)

    for ssh_key_env_var, ssh_key_path in ssh_keys.items():
        ssh_key = os.environ[ssh_key_env_var]
        ssh_key_path = os.path.expanduser(ssh_key_path)
        ssh_key_dir = os.path.dirname(ssh_key_path)
        if not os.path.isdir(ssh_key_dir):
            os.makedirs(ssh_key_dir)
        with open(ssh_key_path, 'w') as f:
            f.write(ssh_key)
        os.chmod(ssh_key_path, 0600)


def patch_inputs_properties(path, properties):
    patch_properties(path, properties, is_json=True)


def patch_provider_properties(path, properties):
    patch_properties(path, properties, is_json=False)


def patch_manager_blueprint_properties(path, properties):
    patch_properties(path, properties, is_json=False)


def patch_properties(path, properties, is_json):
    with YamlPatcher(path, is_json) as patch:
        for env_var, prop_path in properties.items():
            value = os.environ.get(env_var)
            if value:
                if env_var is 'WORKFLOW_TASK_RETRIES':
                    value = int(value)
                patch.set_value(prop_path, value)


def _get_manager_blueprints(manager_blueprints_dir):
    manager_blueprints_paths = []

    manager_blueprints_dirs = \
        [os.path.join(manager_blueprints_dir, dir) for dir in os.listdir(
            manager_blueprints_dir) if os.path.isdir(os.path.join(
                manager_blueprints_dir, dir)) and not dir.startswith('.')]

    for manager_blueprint_dir in manager_blueprints_dirs:
        yaml_files = [os.path.join(manager_blueprint_dir, file) for file in
                      os.listdir(manager_blueprint_dir) if
                      file.endswith('.yaml')]
        if len(yaml_files) != 1:
            raise RuntimeError(
                'Expected exactly one .yaml file at {0}, but found {1}'
                .format(manager_blueprint_dir, len(yaml_files)))

        manager_blueprints_paths.append(yaml_files[0])

    return manager_blueprints_paths
