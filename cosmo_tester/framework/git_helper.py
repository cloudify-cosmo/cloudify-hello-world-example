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

MASTER_BRANCH = 'master'

logger = logging.getLogger('git_helper')
logger.setLevel(logging.INFO)
git = sh_bake(sh.git)


def clone(url, basedir, branch=None):
    repo_name = url.split('.git')[0].split('/')[-1]

    target = path(os.path.join(basedir, 'git', repo_name, branch))

    if not target.exists():
        logger.info("Cloning {0} to {1}".format(url, target))
        git.clone(url, str(target)).wait()
        with target:
            try:
                logger.info("Trying to check out to {0} branch".format(branch))
                git.checkout(branch).wait()
            except Exception:
                logger.info("{0} branch/tag was not found in {1} "
                            "repo, so defaults to master"
                            "branch".format(branch, url))
                git.checkout(MASTER_BRANCH)
    return target.abspath()


def checkout(repo_path, branch, force=False):
    logger.info('Checking out to {0} branch in repo {1}'
                .format(branch, repo_path))
    target = path(repo_path)
    with target:
        git.checkout(branch, force=force).wait()
