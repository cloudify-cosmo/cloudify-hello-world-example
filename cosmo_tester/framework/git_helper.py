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
import os
import random
import string
import tempfile

__author__ = 'dank'

import sh
from path import path
import logging

from cosmo_tester.framework.util import sh_bake


logger = logging.getLogger('git_helper')
logger.setLevel(logging.INFO)
git = sh_bake(sh.git)


def create_temp_folder():
    path_join = os.path.join(tempfile.gettempdir(), id_generator(5))
    os.makedirs(path_join)
    return path_join


def id_generator(size=6, chars=string.ascii_uppercase + string.digits):
    return ''.join(random.choice(chars) for x in range(size))


def clone(url, basedir, branch='develop'):

    repo_name = url.split('.git')[0].split('/')[-1]

    target = path(os.path.join(basedir, 'git', repo_name))

    logger.info("Cloning {0} to {1}".format(url, target))
    git.clone(url, str(target)).wait()
    with target:
        logger.info("Checking out to {0} branch".format(branch))
        git.checkout(branch).wait()
    return target.abspath()
