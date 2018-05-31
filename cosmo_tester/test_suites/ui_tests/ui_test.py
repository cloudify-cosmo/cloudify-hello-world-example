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

# import pytest

from cosmo_tester.framework.fixtures import image_based_manager

import subprocess
import os

manager = image_based_manager


def test_ui(cfy, manager, module_tmpdir, attributes, ssh_key, logger):

    os.environ["STAGE_E2E_MANAGER_URL"] = manager.ip_address
    subprocess.call(['npm', 'run', 'e2e'])
