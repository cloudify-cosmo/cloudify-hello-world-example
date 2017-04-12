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

from cosmo_tester.framework.fixtures import bootstrap_based_manager
from cosmo_tester.framework.examples.hello_world import HelloWorldExample


manager = bootstrap_based_manager


@pytest.fixture(scope='function')
def hello_world(cfy, manager, attributes, ssh_key, tmpdir,
                logger):
    hw = HelloWorldExample(
            cfy, manager, attributes, ssh_key, logger, tmpdir)
    hw.blueprint_file = 'openstack-blueprint.yaml'
    yield hw
    hw.cleanup()


def test_manager_bootstrap_and_deployment(hello_world, attributes):
    hello_world.inputs.update({
        'agent_user': attributes.centos7_username,
        'image': attributes.centos7_image_name,
    })
    hello_world.verify_all()
