########
# Copyright (c) 2017 GigaSpaces Technologies Ltd. All rights reserved
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

import pytest

from cosmo_tester.framework.fixtures import image_based_manager
from cosmo_tester.framework.test_hosts import TestHosts

import subprocess
import os

manager = image_based_manager


@pytest.fixture(scope='function')
def hosts(request, cfy, ssh_key, module_tmpdir, attributes, logger):
    logger.info('Creating Cloudify Manager')
    hosts = TestHosts(
        cfy, ssh_key, module_tmpdir, attributes, logger,
        number_of_instances=1)

    hosts.instances[0].upload_plugins = False
    try:
        hosts.create()
        yield hosts

    finally:
        hosts.destroy()


def test_ui(cfy, manager, module_tmpdir, attributes, ssh_key, logger):

    os.environ["STAGE_E2E_SELENIUM_HOST"] = '10.239.0.203'
    os.environ["STAGE_E2E_MANAGER_URL"] = manager.ip_address
    subprocess.call(['npm', 'run', 'e2e'],
                    cwd=os.environ["CLOUDIFY_STAGE_REPO_PATH"])
