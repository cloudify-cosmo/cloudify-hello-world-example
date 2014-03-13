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

__author__ = 'nirb'

import getpass

from fabric.context_managers import prefix, cd
from fabric.operations import put
from fabric.api import run
from fabric.api import env

from cosmo_tester.resources import test_client_props

user_prefix = getpass.getuser()

env.host_string = test_client_props.host_address
env.user = test_client_props.user
env.password = test_client_props.password
env.key_filename = test_client_props.keyfile_path

env_name = user_prefix + '-cosmo-test2'
work_dir_name = user_prefix + '-cosmo-dev-dir2'


def bootstrap(cloud_config_file_name):
    """Edit the test client props file (under resources) according to your
    client machine, prepare your cloud config
    file, put it under resources and pass it as cloud_config_file_name"""
    run('sudo apt-get update')
    run('sudo apt-get -y install python-pip')
    run('sudo apt-get -y install git')
    run('sudo pip install virtualenv')
    run('virtualenv ' + env_name)

    with prefix('source ' + env_name + '/bin/activate'):
        run('pip install --process-dependency https://github.com/'
            'CloudifySource/cosmo-cli/archive/develop.zip')
        run('sudo apt-get -y install python-dev')
        run('pip install https://github.com/CloudifySource/'
            'cloudify-openstack/archive/develop.zip')
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
