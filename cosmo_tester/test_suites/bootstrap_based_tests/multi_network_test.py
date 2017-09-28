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

import yaml
import pytest

from cosmo_tester.framework.cluster import BootstrapBasedCloudifyCluster
from cosmo_tester.framework.examples.hello_world import HelloWorldExample
from cosmo_tester.framework.util import prepare_and_get_test_tenant

from cosmo_tester.test_suites.snapshots import (
    create_snapshot,
    download_snapshot,
    upload_snapshot,
    restore_snapshot,
    upgrade_agents,
    delete_manager
)


@pytest.fixture(scope='module', params=[3])
def managers(request, cfy, ssh_key, module_tmpdir, attributes, logger):
    """Bootstraps 2 cloudify managers on a VM in rackspace OpenStack."""

    cluster = BootstrapBasedCloudifyCluster(
        cfy, ssh_key, module_tmpdir, attributes, logger,
        number_of_managers=2,
        tf_template='openstack-multi-network-test.tf.template',
        template_inputs={
            'num_of_networks': request.param,
            'num_of_managers': 2,
            'image_name': attributes.centos_7_image_name
        })
    cluster.preconfigure_callback = _preconfigure_callback
    try:
        cluster.create()
        yield cluster.managers
    finally:
        cluster.destroy()


def _preconfigure_callback(_managers):
    # Calling the param `_managers` to avoid confusion with fixture

    # The preconfigure callback populates the networks config prior to the BS
    for mgr in _managers:
        mgr.bs_inputs = {'manager_networks': mgr.networks}

        # Configure NICs in order for networking to work properly
        mgr.enable_nics()


def test_multiple_networks(managers,
                           cfy,
                           multi_network_hello_worlds,
                           logger,
                           tmpdir,
                           attributes):
    logger.info('Testing managers with multiple networks')

    # We should have at least 3 hello world objects. We will verify the first
    # one completely on the first manager.
    # All the other ones will be installed on the first manager,
    # then we'll create a snapshot and restore it on the second manager, and
    # finally, to complete the verification, we'll uninstall the remaining
    # hellos on the new manager

    old_manager = managers[0]
    new_manager = managers[1]
    snapshot_id = 'SNAPSHOT_ID'
    local_snapshot_path = str(tmpdir / 'snap.zip')

    first_hello = multi_network_hello_worlds[0]
    first_hello.verify_all()

    for hello in multi_network_hello_worlds[1:]:
        hello.upload_blueprint()
        hello.create_deployment()
        hello.install()
        hello.verify_installation()

    create_snapshot(old_manager, snapshot_id, attributes, logger)
    download_snapshot(old_manager, local_snapshot_path, snapshot_id, logger)
    upload_snapshot(new_manager, local_snapshot_path, snapshot_id, logger)
    restore_snapshot(new_manager, snapshot_id, cfy, logger)

    upgrade_agents(cfy, new_manager, logger)
    delete_manager(old_manager, logger)

    new_manager.use()
    for hello in multi_network_hello_worlds[1:]:
        hello.manager = new_manager
        hello.uninstall()
        hello.delete_deployment()


class MultiNetworkHelloWorld(HelloWorldExample):
    def _patch_blueprint(self):
        with open(self.blueprint_path, 'r') as f:
            blueprint_dict = yaml.load(f)

        node_props = blueprint_dict['node_templates']['vm']['properties']
        agent_config = node_props['agent_config']
        agent_config['network'] = {'get_input': 'manager_network_name'}

        inputs = blueprint_dict['inputs']
        inputs['manager_network_name'] = {}

        with open(self.blueprint_path, 'w') as f:
            yaml.dump(blueprint_dict, f)


@pytest.fixture(scope='function')
def multi_network_hello_worlds(cfy, managers, attributes, ssh_key, tmpdir,
                               logger):
    # The first manager is the initial one
    manager = managers[0]
    manager.use()
    hellos = []

    # Add a MultiNetworkHelloWorld per management network
    for network_name, network_id in attributes.network_names.iteritems():
        tenant = prepare_and_get_test_tenant(
            '{0}_tenant'.format(network_name), manager, cfy
        )
        hello = MultiNetworkHelloWorld(
            cfy, manager, attributes, ssh_key, logger, tmpdir,
            tenant=tenant, suffix=tenant)
        hello.blueprint_file = 'openstack-blueprint.yaml'
        hello.inputs.update({
            'agent_user': attributes.centos_7_username,
            'image': attributes.centos_7_image_name,
            'manager_network_name': network_name,
            'network_name': network_id
        })
        hellos.append(hello)

    # Add one more hello world, that will run on the `default` network
    # implicitly
    hw = HelloWorldExample(cfy, manager, attributes, ssh_key, logger, tmpdir)
    hw.blueprint_file = 'openstack-blueprint.yaml'
    hw.inputs.update({
        'agent_user': attributes.centos_7_username,
        'image': attributes.centos_7_image_name
    })
    hellos.append(hw)

    yield hellos
    for hello in hellos:
        hello.cleanup()
