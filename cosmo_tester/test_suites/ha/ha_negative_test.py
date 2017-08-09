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


@pytest.fixture(scope='function')
def cluster(
        request, cfy, ssh_key, module_tmpdir, attributes, logger):
    """Creates a HA cluster from an image in rackspace OpenStack."""
    logger.info('Creating HA cluster of 2 managers')
    cluster = CloudifyCluster.create_image_based(
        cfy,
        ssh_key,
        module_tmpdir,
        attributes,
        logger,
        number_of_managers=2,
        create=False)

    # manager2 - Cloudify latest - don't install plugins
    cluster.managers[1].upload_plugins = False

    cluster.create()

    try:
        manager1 = cluster.managers[0]
        manager2 = cluster.managers[1]

        ha_helper.delete_active_profile()
        manager1.use()
        cfy.cluster.start(timeout=600,
                          cluster_host_ip=manager1.private_ip_address,
                          cluster_node_name=manager1.ip_address)

        manager2.use()
        cfy.cluster.join(manager1.ip_address,
                         timeout=600,
                         cluster_host_ip=manager2.private_ip_address,
                         cluster_node_name=manager2.ip_address)
        cfy.cluster.nodes.list()

        yield cluster

    finally:
        cluster.destroy()


def test_nonempty_manager_join_cluster_negative(cfy, attributes, ssh_key,
                                                logger, tmpdir, module_tmpdir):
    logger.info('Creating HA cluster of 2 managers')
    cluster = CloudifyCluster.create_image_based(
        cfy,
        ssh_key,
        module_tmpdir,
        attributes,
        logger,
        number_of_managers=2,
        create=False)

    # manager2 - Cloudify latest - don't install plugins
    cluster.managers[1].upload_plugins = False

    cluster.create()

    try:
        manager1 = cluster.managers[0]
        manager2 = cluster.managers[1]

        ha_helper.delete_active_profile()
        manager1.use()
        cfy.cluster.start(timeout=600,
                          cluster_host_ip=manager1.private_ip_address,
                          cluster_node_name=manager1.ip_address)

        cfy.cluster.nodes.list()

        ha_helper.delete_active_profile()
        manager2.use()
        hello_world = HelloWorldExample(
            cfy, manager2, attributes, ssh_key, logger, tmpdir)
        hello_world.blueprint_file = 'openstack-blueprint.yaml'
        hello_world.inputs.update({
            'agent_user': attributes.centos7_username,
            'image': attributes.centos7_image_name,
        })

        hello_world.upload_blueprint()

        logger.info('Joining HA cluster from a non-empty manager')
        with pytest.raises(Exception):
            cfy.cluster.join(manager1.ip_address,
                             timeout=600,
                             cluster_host_ip=manager2.private_ip_address,
                             cluster_node_name=manager2.ip_address)

    finally:
        cluster.destroy()


def test_remove_from_cluster_and_use_negative(cfy, cluster, logger):
    manager1 = cluster.managers[0]
    manager2 = cluster.managers[1]

    logger.info('Removing the standby manager %s from the HA cluster',
                manager2.ip_address)
    cfy.cluster.nodes.remove(manager2.ip_address)

    # removing nodes from a cluster can lead to short breaks of the cluster
    # endpoints in the REST API in case Consul was using the removed node
    # as a Consul leader. Let's wait for re-election to check that after
    # removing node, the cluster still correctly shows a leader
    ha_helper.wait_leader_election([manager1], logger)

    logger.info('Trying to use a manager previously removed'
                ' from HA cluster')
    with pytest.raises(Exception) as exinfo:
        # use a separate profile name, to force creating a new profile
        # (pre-existing profile would be connected to the whole cluster,
        # which at this point consists only of manager1)
        manager2.use(profile_name='new-profile')
    assert 'This node was removed from the Cloudify Manager cluster' in \
        exinfo.value.message


def test_remove_from_cluster_and_rejoin_negative(cfy, cluster, logger):
    manager1 = cluster.managers[0]
    manager2 = cluster.managers[1]

    logger.info('Removing the standby manager %s from the HA cluster',
                manager2.ip_address)
    cfy.cluster.nodes.remove(manager2.ip_address)
    ha_helper.wait_leader_election([manager1], logger)

    # we need to use the rest-client to check rejoining - can't do this from
    # the CLI, because we can't `use` manager2 (it's impossible to use
    # nodes removed from the cluster, as checked by another test)
    logger.info('Trying to rejoin HA cluster with a manager previously'
                ' removed from cluster')
    with pytest.raises(Exception) as exinfo:
        manager2.client.cluster.join(
            host_ip=manager2.private_ip_address,
            node_name=manager2.private_ip_address,
            join_addrs=[manager1.private_ip_address],
            credentials={})
    assert 'This node was removed from the Cloudify Manager cluster' == \
        exinfo.value.message


def test_manager_already_in_cluster_join_cluster_negative(cfy,
                                                          cluster, logger):
    manager1 = cluster.managers[0]
    manager2 = cluster.managers[1]

    ha_helper.set_active(manager2, cfy, logger)
    ha_helper.delete_active_profile()
    manager2.use()
    logger.info('Joining HA cluster with the manager %s that is already'
                ' a part of the cluster', manager2.ip_address)
    with pytest.raises(Exception):
        cfy.cluster.join(manager1.ip_address,
                         timeout=600,
                         cluster_host_ip=manager2.private_ip_address,
                         cluster_node_name=manager2.ip_address)