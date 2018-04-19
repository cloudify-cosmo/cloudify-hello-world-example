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
import yaml

from cosmo_tester.framework.examples.hello_world import HelloWorldExample
from cosmo_tester.framework.fixtures import image_based_manager
from cosmo_tester.framework.util import prepare_and_get_test_tenant

manager = image_based_manager


def test_hello_world(hello_world):
    hello_world.verify_all()


def test_hello_world_backwards(hello_world_backwards_compat):
    hello_world_backwards_compat.verify_all()


@pytest.fixture(
    scope='function',
    params=[
        'centos_6',
        'centos_7',
        'rhel_6',
        'rhel_7',
        'ubuntu_14_04',
        'ubuntu_16_04',
        'windows_2012',
    ],
)
def hello_world(request, cfy, manager, attributes, ssh_key, tmpdir, logger):
    tenant = prepare_and_get_test_tenant(request.param, manager, cfy)
    hw = HelloWorldExample(
            cfy, manager, attributes, ssh_key, logger, tmpdir,
            tenant=tenant, suffix=request.param)
    if 'windows' in request.param:
        hw.blueprint_file = 'openstack-windows-blueprint.yaml'
        hw.inputs.update({
            'flavor': attributes['large_flavor_name'],
        })
    else:
        hw.blueprint_file = 'openstack-blueprint.yaml'
        hw.inputs.update({
            'agent_user': attributes['{os}_username'.format(os=request.param)],
        })
    if request.param == 'rhel_7':
        hw.inputs.update({
            'flavor': attributes['medium_flavor_name'],
        })

    hw.inputs.update({
        'image': attributes['{os}_image_name'.format(os=request.param)],
    })

    if request.param == 'centos_6':
        hw.disable_iptables = True
    yield hw
    hw.cleanup()


@pytest.fixture(
    scope='function',
    params=[
        '1_2',
    ],
)
def hello_world_backwards_compat(request, cfy, manager, attributes, ssh_key,
                                 tmpdir, logger):
    tenant_param = 'dsl_{ver}'.format(ver=request.param)
    tenant = prepare_and_get_test_tenant(tenant_param, manager, cfy)

    # Using 1_2 instead of 1.2 because diamond deliminates using dots (.),
    # so having a dot in the deployment name (passed as the suffix to the
    # HelloWorldExample constructor) messes things up
    dsl_git_checkout_mappings = {
        # dsl versions 1.0 and 1.1 cannot be tested with this because they do
        # not have usable singlehost blueprints in the hello world repo
        '1_2': '3.3.1',
        # 1.3 is current, and is on git checkout 4.1, but this is tested by
        # the OS tests above
    }

    hw = HelloWorldExample(
            cfy, manager, attributes, ssh_key, logger, tmpdir,
            tenant=tenant, suffix=request.param)

    hw.branch = dsl_git_checkout_mappings[request.param]
    hw.blueprint_file = 'singlehost-blueprint.yaml'

    hw.clone_example()
    with open(hw.blueprint_path) as blueprint_handle:
        blueprint = yaml.load(blueprint_handle)
    blueprint_dsl_version = blueprint['tosca_definitions_version']
    assert blueprint_dsl_version.endswith(request.param)

    yield hw

    # For older CLIs we need to explicitly pass this param
    hw.cleanup(allow_custom_params=True)
