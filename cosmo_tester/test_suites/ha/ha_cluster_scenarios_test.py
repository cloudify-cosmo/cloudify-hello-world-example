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
from cosmo_tester.framework.cluster import CloudifyCluster
from .ha_helper import HighAvailabilityHelper as ha_helper


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
def hello_world(cfy, cluster, attributes, ssh_key, tmpdir, logger):
    hw = HelloWorldExample(
        cfy, cluster.managers[0], attributes, ssh_key, logger, tmpdir)
    hw.blueprint_file = 'openstack-blueprint.yaml'
    hw.inputs.update({
        'agent_user': attributes.centos7_username,
        'image': attributes.centos7_image_name,
    })

    yield hw
    if hw.cleanup_required:
        logger.info('Hello world cleanup required..')
        cluster.managers[0].use()
        hw.cleanup()


def test_data_replication(cfy, cluster, hello_world,
                          logger):
    manager1 = cluster.managers[0]
    ha_helper.delete_active_profile()
    manager1.use()
    ha_helper.verify_nodes_status(manager1, cfy, logger)
    hello_world.upload_blueprint()
    hello_world.create_deployment()
    hello_world.install()

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


def test_delete_manager_node(cfy, cluster, hello_world,
                             logger):
    ha_helper.set_active(cluster.managers[1], cfy, logger)
    expected_master = cluster.managers[0]

    for manager in cluster.managers[1:]:
        logger.info('Deleting manager %s', manager.ip_address)
        manager.delete()
        ha_helper.wait_leader_election(logger)

    logger.info('Expected leader %s', expected_master)
    ha_helper.verify_nodes_status(expected_master, cfy, logger)
    hello_world.upload_blueprint()


def test_failover(cfy, cluster, hello_world,
                  logger):
    for manager in cluster.managers[:-1]:
        logger.info('Simulating manager %s failure by stopping'
                    ' nginx service', manager.ip_address)
        with manager.ssh() as fabric:
            fabric.run('sudo systemctl stop nginx')
        ha_helper.wait_leader_election(logger)
        cfy.cluster.nodes.list()

    expected_master = cluster.managers[-1]
    ha_helper.delete_active_profile()
    expected_master.use()
    ha_helper.verify_nodes_status(expected_master, cfy, logger)

    with expected_master.ssh() as fabric:
        logger.info('Simulating manager %s failure by stopping '
                    'cloudify-mgmtworker service',
                    expected_master.ip_address)
        fabric.run('sudo systemctl stop cloudify-mgmtworker')
    ha_helper.wait_leader_election(logger)
    cfy.cluster.nodes.list()

    expected_master = cluster.managers[0]
    logger.info('Starting nginx service on manager %s',
                expected_master.ip_address)
    with expected_master.ssh() as fabric:
        fabric.run('sudo systemctl start nginx')
    ha_helper.wait_leader_election(logger)
    ha_helper.delete_active_profile()
    expected_master.use()
    ha_helper.verify_nodes_status(expected_master, cfy, logger)
    hello_world.upload_blueprint()


def test_remove_manager_from_cluster(cfy, cluster, hello_world,
                                     logger):
    ha_helper.set_active(cluster.managers[1], cfy, logger)
    ha_helper.delete_active_profile()

    for manager in cluster.managers[1:]:
        manager.use()
        logger.info('Removing the manager %s from HA cluster',
                    manager.ip_address)
        cfy.cluster.nodes.remove(manager.ip_address)
        ha_helper.wait_leader_election(logger)

    expected_master = cluster.managers[0]
    ha_helper.delete_active_profile()
    expected_master.use()

    ha_helper.verify_nodes_status(expected_master, cfy, logger)
    hello_world.upload_blueprint()
