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


import time
import os

from requests.exceptions import ConnectionError
from cloudify_rest_client.exceptions import CloudifyClientError


def set_active(manager, cfy, logger):
    try:
        logger.info('Setting active manager %s',
                    manager.ip_address)
        cfy.cluster('set-active', manager.ip_address)
    except Exception as e:
        logger.info('Setting active manager error message: %s', e.message)
    finally:
        wait_nodes_online([manager], logger)


def wait_leader_election(managers, logger):
    """Wait until there is a leader in the cluster"""
    def _is_there_a_leader(nodes):
        # we only consider there to be a leader, if it is online and
        # passing all checks
        for node in nodes:
            if node['master'] and node['online'] and \
                    all(node['checks'].values()):
                return True
    logger.info('Waiting for a leader election...')
    _wait_cluster_status(_is_there_a_leader, managers, logger)


def wait_nodes_online(managers, logger):
    """Wait until all of the cluster nodes are online"""
    def _all_nodes_online(nodes):
        return all(node['online'] for node in nodes)
    logger.info('Waiting for all nodes to be online...')
    _wait_cluster_status(_all_nodes_online, managers, logger)


def _wait_cluster_status(predicate, managers, logger, timeout=150,
                         poll_interval=1):
    """Wait until the cluster is in a state decided by predicate

    :param predicate: a function deciding if the cluster is in the desired
                      state, when passed in the list of nodes
    :param managers: a list of managers that will be polled for status
    :type managers: list of _CloudifyManager
    :param logger: The logger to use
    :param timeout: How long to wait for leader election
    :param poll_interval: Interval to wait between requests
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        for manager in managers:
            try:
                nodes = manager.client.cluster.nodes.list()
                if predicate(nodes):
                    return
            except (ConnectionError, CloudifyClientError):
                logger.debug('_wait_cluster_status: manager {0} did not '
                             'respond'.format(manager))

        logger.debug('_wait_cluster_status: none of the nodes responded')
        time.sleep(poll_interval)

    raise RuntimeError('Timeout when waiting for cluster status')


def verify_nodes_status(manager, cfy, logger):
    logger.info('Verifying that manager %s is a leader '
                'and others are replicas', manager.ip_address)
    cfy.cluster.nodes.list()
    nodes = manager.client.cluster.nodes.list()
    for node in nodes:
        if node.name == str(manager.ip_address):
            assert node.master is True
            logger.info('Manager %s is a leader ', node.name)
        else:
            assert node.master is not True
            logger.info('Manager %s is a replica ', node.name)


def delete_active_profile():
    active_profile_path = os.path.join(os.environ['CFY_WORKDIR'],
                                       '.cloudify/active.profile')
    if os.path.exists(active_profile_path):
        os.remove(active_profile_path)


def start_cluster(manager, cfy):
    delete_active_profile()
    manager.use()

    cfy.cluster.start(timeout=600,
                      cluster_host_ip=manager.private_ip_address,
                      cluster_node_name=manager.ip_address)

    return manager


def setup_cluster(hosts, cfy, logger):
    manager1 = start_cluster(hosts[0], cfy)

    for manager in hosts[1:]:
        manager.use()
        cfy.cluster.join(manager1.ip_address,
                         timeout=600,
                         cluster_host_ip=manager.private_ip_address,
                         cluster_node_name=manager.ip_address)

    cfy.cluster.nodes.list()
    wait_nodes_online(hosts, logger)
    return hosts
