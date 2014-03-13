import getpass
from fabric.context_managers import prefix, cd
from fabric.operations import put
from fabric.api import run
from fabric.api import env
from resources import test_client_props

__author__ = 'nirb'


user_prefix = getpass.getuser()

env.host_string = test_client_props.host_address
env.user = test_client_props.user
env.password = test_client_props.password
env.key_filename = test_client_props.keyfile_path

env_name = user_prefix + '-cosmo-test2'
work_dir_name = user_prefix + '-cosmo-dev-dir2'


def bootstrap(cloud_config_file_name):
    """Edit the test client props file (under resources) according to your client machine, prepare your cloud config
    file, put it under resources and pass it as cloud_config_file_name"""
    run('sudo apt-get update')
    run('sudo apt-get -y install python-pip')
    run('sudo apt-get -y install git')
    run('sudo pip install virtualenv')
    run('virtualenv ' + env_name)

    with prefix('source ' + env_name + '/bin/activate'):
        run('pip install --process-dependency https://github.com/CloudifySource/cosmo-cli/archive/develop.zip')
        run('sudo apt-get -y install python-dev')
        run('pip install https://github.com/CloudifySource/cloudify-openstack/archive/develop.zip')
        run('mkdir ' + work_dir_name)

    with prefix('source ../' + env_name + '/bin/activate'):
        with cd(work_dir_name):
            run('cfy init openstack')
            run('mv cloudify-config.yaml cloudify-config.yaml.backup')

    put('../resources/' + cloud_config_file_name, work_dir_name)
    with cd(work_dir_name):
        run('mv ' + cloud_config_file_name + ' cloudify-config.yaml')

    with prefix('source ../' + env_name + '/bin/activate'):
        with cd(work_dir_name):
            run('cfy bootstrap -a -v')
