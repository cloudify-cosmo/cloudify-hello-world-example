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
import time

from cosmo_tester.framework.examples.hello_world import HelloWorldExample
from cosmo_tester.framework.cluster import CloudifyCluster
from cosmo_tester.framework.util import prepare_and_get_test_tenant
from .ha_helper import HighAvailabilityHelper as ha_helper
from . import skip_community


# Skip all tests in this module if we're running community tests,
# using the pytestmark magic variable name
pytestmark = skip_community


@pytest.fixture(scope='function', params=[2, 3])
def cluster(
        request, cfy, ssh_key, module_tmpdir, attributes, logger):
    """Creates a HA cluster from an image in rackspace OpenStack."""
    logger.info('Creating HA cluster of %s managers', request.param)
    cluster = CloudifyCluster.create_image_based(
        cfy,
        ssh_key,
        module_tmpdir,
        attributes,
        logger,
        number_of_managers=request.param,
        create=False)

    for manager in cluster.managers[1:]:
        manager.upload_plugins = False

    cluster.create()

    try:
        manager1 = cluster.managers[0]
        ha_helper.delete_active_profile()
        manager1.use()

        cfy.cluster.start(timeout=600,
                          cluster_host_ip=manager1.private_ip_address,
                          cluster_node_name=manager1.ip_address)

        for manager in cluster.managers[1:]:
            manager.use()
            cfy.cluster.join(manager1.ip_address,
                             timeout=600,
                             cluster_host_ip=manager.private_ip_address,
                             cluster_node_name=manager.ip_address)

        cfy.cluster.nodes.list()

        yield cluster

    finally:
        cluster.destroy()


@pytest.fixture(scope='function')
def ha_hello_worlds(cfy, cluster, attributes, ssh_key, tmpdir, logger):
    # Pick a manager to operate on, and trust the cluster to work with us
    manager = cluster.managers[0]

    hws = []
    for i in range(0, 2):
        tenant = prepare_and_get_test_tenant(
            'clusterhello{num}'.format(num=i),
            manager,
            cfy,
        )
        hw = HelloWorldExample(
            cfy, manager, attributes, ssh_key, logger, tmpdir,
            tenant=tenant, suffix=str(i),
        )
        hw.blueprint_file = 'openstack-blueprint.yaml'
        hw.inputs.update({
            'agent_user': attributes.centos_7_username,
            'image': attributes.centos_7_image_name,
        })
        hws.append(hw)

    yield hws
    for hw in hws:
        if hw.cleanup_required:
            logger.info('Cleaning up hello world...')
            manager.use()
            hw.cleanup()


def test_data_replication(cfy, cluster, ha_hello_worlds,
                          logger):
    manager1 = cluster.managers[0]
    ha_helper.delete_active_profile()
    manager1.use()
    ha_helper.verify_nodes_status(manager1, cfy, logger)
    _test_hellos(ha_hello_worlds, install=True)

    logger.info('Manager %s resources', manager1.ip_address)
    m1_blueprints_list = cfy.blueprints.list()
    m1_deployments_list = cfy.deployments.list()
    m1_plugins_list = cfy.plugins.list()

    for manager in cluster.managers[1:]:
        ha_helper.set_active(manager, cfy, logger)
        ha_helper.delete_active_profile()
        manager.use()
        ha_helper.verify_nodes_status(manager, cfy, logger)

        logger.info('Manager %s resources', manager.ip_address)
        assert m1_blueprints_list == cfy.blueprints.list()
        assert m1_deployments_list == cfy.deployments.list()
        assert m1_plugins_list == cfy.plugins.list()

    ha_helper.set_active(manager1, cfy, logger)
    ha_helper.delete_active_profile()
    manager1.use()


def test_set_active(cfy, cluster,
                    logger):
    manager1 = cluster.managers[0]
    ha_helper.delete_active_profile()
    manager1.use()
    ha_helper.verify_nodes_status(manager1, cfy, logger)

    for manager in cluster.managers[1:]:
        ha_helper.set_active(manager, cfy, logger)
        ha_helper.delete_active_profile()
        manager.use()
        ha_helper.verify_nodes_status(manager, cfy, logger)


def test_delete_manager_node(cfy, cluster, ha_hello_worlds,
                             logger):
    ha_helper.set_active(cluster.managers[1], cfy, logger)
    expected_master = cluster.managers[0]
    for manager in cluster.managers[1:]:
        logger.info('Deleting manager %s', manager.ip_address)
        manager.delete()
        ha_helper.wait_leader_election(
            [m for m in cluster.managers if not m.deleted], logger)

    logger.info('Expected leader %s', expected_master)
    ha_helper.verify_nodes_status(expected_master, cfy, logger)
    _test_hellos(ha_hello_worlds)


def test_failover(cfy, cluster, ha_hello_worlds,
                  logger):
    """Test that the cluster fails over in case of a service failure

    - stop nginx on leader
    - check that a new leader is elected
    - stop mgmtworker on that new leader, and restart nginx on the former
    - check that the original leader was elected
    """
    expected_master = cluster.managers[-1]
    # stop nginx on all nodes except last - force choosing the last as the
    # leader (because only the last one has services running)
    for manager in cluster.managers[:-1]:
        logger.info('Simulating manager %s failure by stopping'
                    ' nginx service', manager.ip_address)
        with manager.ssh() as fabric:
            fabric.run('sudo systemctl stop nginx')
        # wait for checks to notice the service failure
        time.sleep(20)
        ha_helper.wait_leader_election(cluster.managers, logger)
        cfy.cluster.nodes.list()

    ha_helper.verify_nodes_status(expected_master, cfy, logger)

    new_expected_master = cluster.managers[0]
    # force going back to the original leader - start nginx on it, and
    # stop mgmtworker on the current leader (simulating failure)
    with new_expected_master.ssh() as fabric:
        logger.info('Starting nginx service on manager %s',
                    new_expected_master.ip_address)
        fabric.run('sudo systemctl start nginx')

    with expected_master.ssh() as fabric:
        logger.info('Simulating manager %s failure by stopping '
                    'cloudify-mgmtworker service',
                    expected_master.ip_address)
        fabric.run('sudo systemctl stop cloudify-mgmtworker')

    # wait for checks to notice the service failure
    time.sleep(20)
    ha_helper.wait_leader_election(cluster.managers, logger)
    cfy.cluster.nodes.list()

    ha_helper.verify_nodes_status(new_expected_master, cfy, logger)

    _test_hellos(ha_hello_worlds)


def test_remove_manager_from_cluster(cfy, cluster, ha_hello_worlds,
                                     logger):
    ha_helper.set_active(cluster.managers[1], cfy, logger)
    ha_helper.delete_active_profile()

    expected_master = cluster.managers[0]
    nodes_to_check = list(cluster.managers)
    for manager in cluster.managers[1:]:
        manager.use()
        logger.info('Removing the manager %s from HA cluster',
                    manager.ip_address)
        cfy.cluster.nodes.remove(manager.ip_address)
        nodes_to_check.remove(manager)
        ha_helper.wait_leader_election(nodes_to_check, logger)

    ha_helper.delete_active_profile()
    expected_master.use()

    ha_helper.verify_nodes_status(expected_master, cfy, logger)
    _test_hellos(ha_hello_worlds)


def test_uninstall_dep(cfy, cluster, ha_hello_worlds,
                       logger):
    manager1 = cluster.managers[0]
    ha_helper.delete_active_profile()
    manager1.use()
    ha_helper.verify_nodes_status(manager1, cfy, logger)
    _test_hellos(ha_hello_worlds, install=True)

    manager2 = cluster.managers[-1]
    ha_helper.set_active(manager2, cfy, logger)
    ha_helper.delete_active_profile()
    manager2.use()
    for hello_world in ha_hello_worlds:
        hello_world.uninstall()


def _test_hellos(hello_worlds, install=False):
    for hello_world in hello_worlds:
        hello_world.upload_blueprint()
        if install:
            hello_world.create_deployment()
            hello_world.install()
