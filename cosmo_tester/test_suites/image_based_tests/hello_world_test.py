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

from cosmo_tester.framework.examples.hello_world import HelloWorldExample
from cosmo_tester.framework.fixtures import image_based_manager

manager = image_based_manager


@pytest.fixture(scope='function')
def hello_world(cfy, manager, attributes, ssh_key, tmpdir, logger):
    hw = HelloWorldExample(
            cfy, manager, attributes, ssh_key, logger, tmpdir)
    hw.blueprint_file = 'openstack-blueprint.yaml'
    yield hw
    hw.cleanup()


def test_hello_world_on_centos_7(hello_world, attributes):
    hello_world.inputs.update({
        'agent_user': attributes.centos7_username,
        'image': attributes.centos7_image_name,
    })
    hello_world.verify_all()


def test_hello_world_on_centos_6(hello_world, attributes):
    hello_world.inputs.update({
        'agent_user': attributes.centos6_username,
        'image': attributes.centos6_image_name,
    })
    hello_world.disable_iptables = True
    hello_world.verify_all()


def test_hello_world_on_ubuntu_14_04(hello_world, attributes):
    hello_world.inputs.update({
        'agent_user': attributes.ubuntu_username,
        'image': attributes.ubuntu_14_04_image_name,
    })
    hello_world.verify_all()


def test_hello_world_on_ubuntu_16_04(hello_world, attributes):
    hello_world.inputs.update({
        'agent_user': attributes.ubuntu_username,
        'image': attributes.ubuntu_16_04_image_name,
    })
    hello_world.verify_all()


def test_hello_world_on_windows_2012_server(hello_world, attributes):
    hello_world.blueprint_file = 'openstack-windows-blueprint.yaml'
    hello_world.inputs.update({
        'image': attributes.windows_server_2012_image_name,
        'flavor': attributes.medium_flavor_name
    })
    hello_world.verify_all()


def test_hello_world_single_host(hello_world):
    hello_world.blueprint_file = 'singlehost-blueprint.yaml'
    hello_world.verify_all()
