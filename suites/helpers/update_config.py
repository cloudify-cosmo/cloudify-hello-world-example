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
                  handler,
                  manager_blueprints_dir,
                  manager_blueprint):

    if bootstrap_using_providers:
        patch_properties(config_path, provider_properties)
    else:
        patch_properties(config_path, inputs_properties)

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

    patch_properties(os.path.join(manager_blueprints_dir,
                                  manager_blueprint),
                     manager_blueprints_for_patching)

    if hasattr(handler, 'update_config'):
        handler.update_config(manager_blueprints_dir)

    for ssh_key_env_var, ssh_key_path in ssh_keys.items():
        ssh_key = os.environ[ssh_key_env_var]
        ssh_key_path = os.path.expanduser(ssh_key_path)
        ssh_key_dir = os.path.dirname(ssh_key_path)
        if not os.path.isdir(ssh_key_dir):
            os.makedirs(ssh_key_dir)
        with open(ssh_key_path, 'w') as f:
            f.write(ssh_key)
        os.chmod(ssh_key_path, 0600)


def patch_properties(path, properties):
    with YamlPatcher(path) as patch:
        for env_var, prop_path in properties.items():
            value = os.environ.get(env_var)
            if value:
                if env_var is 'WORKFLOW_TASK_RETRIES':
                    value = int(value)
                patch.set_value(prop_path, value)
