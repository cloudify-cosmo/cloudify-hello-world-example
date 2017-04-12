########
# Copyright (c) 2015 GigaSpaces Technologies Ltd. All rights reserved
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

import uuid

import pytest

from cosmo_tester.framework import util
from cosmo_tester.framework.fixtures import image_based_manager

manager = image_based_manager


@pytest.mark.skip(reason='Ongoing implementation..')
def test_openstack_types_functionality(cfy, manager, attributes, tmpdir):
    blueprint_path = util.get_resource_path(
            'blueprints/neutron-galore/blueprint.yaml')

    unique_id = blueprint_id = deployment_id = str(uuid.uuid4())

    manager.client.blueprints.upload(blueprint_path, blueprint_id)
    inputs = {
        'unique_id': unique_id,
        'image': attributes.centos7_image_name,
        'flavor': attributes.small_flavor_name,
        'network_name': attributes.network_name,
        'floating_network_id': attributes.floating_network_id,
        'key_pair_name': attributes.keypair_name,
        'private_key_path': manager.remote_private_key_path
    }
    manager.client.deployments.create(
            deployment_id, blueprint_id, inputs=inputs)
    try:
        cfy.executions.start.install(['-d', deployment_id])
    finally:
        cfy.executions.start.uninstall(['-d', deployment_id])
