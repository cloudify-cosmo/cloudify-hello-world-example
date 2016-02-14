########
# Copyright (c) 2016 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import shutil
import tempfile
from contextlib import contextmanager

import sh
from path import path


PASSWORD_STORE_DIR = 'PASSWORD_STORE_DIR'
EXTRA_GPG_OPTS = 'EXTRA_GPG_OPTS'
GNUPGHOME = 'GNUPGHOME'
gpg = sh.gpg
git = sh.git
password = sh.Command('pass')
system_tests = 'system-tests'


def read_pass(gpg_secret_key_path,
              password_store_repo,
              store_path=system_tests):
    with pass_context(gpg_secret_key_path) as password_store:
        git.clone(password_store_repo, password_store)
        result = {}
        for item in (password_store / store_path).files('*.gpg'):
            key = item.basename()[:-len('.gpg')]
            key_path = '{0}/{1}'.format(store_path, key)
            value = password.show(key_path).stdout.strip()
            result[key] = value
        return result


def write_pass(gpg_secret_key_name,
               gpg_secret_key_path,
               password_store_output_path,
               passwords,
               store_path=system_tests):
    with pass_context(gpg_secret_key_path) as password_store:
        password.init(gpg_secret_key_name)
        for key, value in passwords.items():
            password.insert('{0}/{1}'.format(store_path, key),
                            multiline=True, _in=value)
        shutil.move(password_store, password_store_output_path)


@contextmanager
def pass_context(gpg_secret_key_path):
    workdir = path(tempfile.mkdtemp(prefix='vars-work-'))
    gpg_home = workdir / 'gpg'
    gpg_home.mkdir()
    os.chmod(gpg_home, 0o0700)
    password_store = workdir / 'password-store'
    os.environ[GNUPGHOME] = gpg_home
    os.environ[PASSWORD_STORE_DIR] = password_store
    os.environ[EXTRA_GPG_OPTS] = '--always-trust'
    try:
        gpg('--quiet', '--yes', '--import', gpg_secret_key_path)
        yield password_store
    finally:
        del os.environ[GNUPGHOME]
        del os.environ[PASSWORD_STORE_DIR]
        del os.environ[EXTRA_GPG_OPTS]
        shutil.rmtree(workdir, ignore_errors=True)
