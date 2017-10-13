#########
# Copyright (c) 2017 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#  * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  * See the License for the specific language governing permissions and
#  * limitations under the License.


import logging
import os
import sys

from path import Path
import pytest
import sh

from cosmo_tester.framework import util


@pytest.fixture(scope='module')
def logger(request):
    logger = logging.getLogger(request.module.__name__)
    logger.setLevel(logging.INFO)
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    formatter = logging.Formatter(fmt='%(asctime)s [%(levelname)s] '
                                      '[%(name)s] %(message)s',
                                  datefmt='%H:%M:%S')
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    logger.propagate = False
    return logger


@pytest.fixture(scope='module')
def module_tmpdir(request, tmpdir_factory, logger):
    suffix = request.module.__name__
    temp_dir = Path(tmpdir_factory.mktemp(suffix))
    logger.info('Created temp folder: %s', temp_dir)

    return temp_dir


class SSHKey(object):

    def __init__(self, tmpdir, logger):
        self.private_key_path = tmpdir / 'ssh_key.pem'
        self.public_key_path = tmpdir / 'ssh_key.pem.pub'
        self.logger = logger
        self.tmpdir = tmpdir

    def create(self):
        self.logger.info('Creating SSH keys at: %s', self.tmpdir)
        if os.system("ssh-keygen -t rsa -f {} -q -N ''".format(
                self.private_key_path)) != 0:
            raise IOError('Error creating SSH key: {}'.format(
                    self.private_key_path))
        if os.system('chmod 400 {}'.format(self.private_key_path)) != 0:
            raise IOError('Error setting private key file permission')

    def delete(self):
        self.private_key_path.remove()
        self.public_key_path.remove()


@pytest.fixture(scope='module')
def ssh_key(module_tmpdir, logger):
    key = SSHKey(module_tmpdir, logger)
    key.create()
    return key


@pytest.fixture(scope='module')
def attributes(logger):
    return util.get_attributes(logger)


@pytest.fixture(scope='module')
def cfy(module_tmpdir, logger):
    os.environ['CFY_WORKDIR'] = module_tmpdir
    logger.info('CFY_WORKDIR is set to %s', module_tmpdir)
    # Copy CLI configuration file if exists in home folder
    # this way its easier to customize the configuration when running
    # tests locally.
    cli_config_path = Path(os.path.expanduser('~/.cloudify/config.yaml'))
    if cli_config_path.exists():
        logger.info('Using CLI configuration file from: %s', cli_config_path)
        new_cli_config_dir = module_tmpdir / '.cloudify'
        new_cli_config_dir.mkdir()
        cli_config_path.copy(new_cli_config_dir / 'config.yaml')
    cfy = util.sh_bake(sh.cfy)
    cfy(['--version'])
    return cfy
