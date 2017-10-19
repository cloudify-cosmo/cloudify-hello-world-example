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
import logging

import sh
from path import path

from cosmo_tester.framework.util import sh_bake


logger = logging.getLogger('git_helper')
logger.setLevel(logging.INFO)
git = sh_bake(sh.git)


def clone(url, basedir, branch=None):

    branch = branch or os.environ.get('BRANCH_NAME_CORE', 'master')

    repo_name = url.split('.git')[0].split('/')[-1]

    target = path(os.path.join(basedir, 'git', repo_name, branch))

    if not target.exists():
        logger.info("Cloning {0} to {1}".format(url, target))
        git.clone(url, str(target)).wait()
        with target:
            logger.info("Checking out to {0} branch".format(branch))
            git.checkout(branch).wait()
    return target.abspath()


def checkout(repo_path, branch, force=False):
    logger.info('Checking out to {0} branch in repo {1}'
                .format(branch, repo_path))
    target = path(repo_path)
    with target:
        git.checkout(branch, force=force).wait()
