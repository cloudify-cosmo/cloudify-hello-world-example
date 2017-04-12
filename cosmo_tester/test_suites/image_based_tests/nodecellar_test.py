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

from cosmo_tester.framework.examples.nodecellar import NodeCellarExample
from cosmo_tester.framework.fixtures import image_based_manager

manager = image_based_manager


@pytest.fixture(scope='function')
def nodecellar(cfy, manager, attributes, ssh_key, tmpdir, logger):
    nc = NodeCellarExample(
            cfy, manager, attributes, ssh_key, logger, tmpdir)
    nc.blueprint_file = 'openstack-blueprint.yaml'
    yield nc
    nc.cleanup()


def test_nodecellar_example(nodecellar):
    nodecellar.verify_all()


@pytest.fixture(scope='function')
def nodecellar_singlehost(cfy, manager, attributes, ssh_key, tmpdir, logger):
    nc = NodeCellarExample(
            cfy, manager, attributes, ssh_key, logger, tmpdir)
    nc.blueprint_file = 'simple-blueprint.yaml'
    return nc


def test_nodecellar_singlehost_example(nodecellar_singlehost):
    nodecellar_singlehost.verify_all()
