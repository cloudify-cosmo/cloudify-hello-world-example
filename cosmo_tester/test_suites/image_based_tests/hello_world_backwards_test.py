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

from path import Path
import pytest

from cosmo_tester.framework.examples.hello_world import HelloWorldExample
from cosmo_tester.framework.fixtures import image_based_manager

manager = image_based_manager


@pytest.fixture(scope='function')
def hello_world(cfy, manager, attributes, ssh_key, tmpdir, logger):
    hw = HelloWorldExample(
            cfy, manager, attributes, ssh_key, logger, tmpdir)
    hw.blueprint_file = 'singlehost-blueprint.yaml'
    yield hw
    hw.cleanup()


def test_hello_world_single_host_3_4_2(hello_world):
    hello_world.branch = '3.4.2'
    hello_world.verify_all()
    assert '3.4.2' in Path(hello_world.blueprint_path).text()


def test_hello_world_single_host_3_3_1(hello_world):
    hello_world.branch = '3.3.1'
    hello_world.verify_all()
    assert '3.3.1' in Path(hello_world.blueprint_path).text()
