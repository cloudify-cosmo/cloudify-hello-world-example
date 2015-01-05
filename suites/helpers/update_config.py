import os

ssh_keys = {
    'SYSTEM_TESTS_MANAGER_KEY': '~/.ssh/shared-systemt-tests-manager.pem',
    'SYSTEM_TESTS_AGENT_KEY': '~/.ssh/shared-systemt-tests-agent.pem'
}


def update_config(handler,
                  manager_blueprints_dir):

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
