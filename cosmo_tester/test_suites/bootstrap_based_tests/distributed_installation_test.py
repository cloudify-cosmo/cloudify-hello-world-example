########
# Copyright (c) 2018 Cloudify Platform Ltd. All rights reserved
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

import pytest

from cosmo_tester.framework.examples.nodecellar import NodeCellarExample
from cosmo_tester.framework.test_hosts import (
    DistributedInstallationCloudifyManager
)
from cosmo_tester.framework.util import prepare_and_get_test_tenant
from cosmo_tester.test_suites.snapshots import (
    create_snapshot,
    download_snapshot,
    upload_snapshot,
    restore_snapshot,
    verify_services_status
)
from ..ha.ha_helper import (
    set_active,
    verify_nodes_status
)
from sanity_scenario_test import (
    _create_and_add_user_to_tenant,
    _copy_ssl_cert_from_manager_to_tmpdir,
    _create_secrets,
    _set_admin_user,
    _set_sanity_user
)
from ..ha.ha_cluster_scenarios_test import (
    test_delete_manager_node,
    test_failover,
    test_fail_and_recover,
    test_remove_manager_from_cluster,
    centos_hello_world
)

USER_NAME = "test_user"
USER_PASS = "testuser123"
TENANT_NAME = "tenant"

SKIP_SANITY = {'skip_sanity': 'true'}

DATABASE_SERVICES_TO_INSTALL = [
    'database_service'
]
MANAGER_SERVICES_TO_INSTALL = [
    'queue_service',
    'composer_service',
    'manager_service'
]


@pytest.fixture(scope='function')
def distributed_installation(cfy, ssh_key, module_tmpdir, attributes, logger,
                             request):
    """
    Bootstraps a cloudify manager distributed installation based on the request
    parameters
    If request.param has a 'cluster' value: 4 nodes are built (1 DB 3 managers)
    If request.param has a 'sanity' value: 5 nodes are built (1 DB 3 managers
    and an AIO manager)
    """
    # request isn't created with a 'param' attribute if no params are sent
    cluster = \
        'cluster' in request.param if hasattr(request, "param") else False
    sanity = 'sanity' in request.param if hasattr(request, "param") else False

    # The preconfigure callback populates the files structure prior to the BS
    def _preconfigure_callback_cluster(distributed_installation):
        # Updating the database VM first
        distributed_installation[0].additional_install_config.update({
            'sanity': SKIP_SANITY,
            'postgresql_server': {
                'enable_remote_connections': 'true',
                'postgres_password': 'postgres'
            },
            'services_to_install': DATABASE_SERVICES_TO_INSTALL
        })
        # Updating the master machine
        distributed_installation[1].additional_install_config.update({
            'sanity': SKIP_SANITY,
            'postgresql_client': {
                'host': str(distributed_installation[0].private_ip_address),
                'postgres_password': 'postgres'
            },
            'services_to_install': MANAGER_SERVICES_TO_INSTALL
        })
        if cluster:
            # Updating both VMs to point to the master
            distributed_installation[2].additional_install_config.update({
                'sanity': SKIP_SANITY,
                'cluster': {
                    'master_ip':
                        str(distributed_installation[1].private_ip_address),
                    'node_name': str(distributed_installation[2].ip_address),
                    'host_ip':
                        str(distributed_installation[2].private_ip_address)
                },
                'postgresql_client': {
                    'host':
                        str(distributed_installation[0].private_ip_address),
                    'postgres_password': 'postgres'
                },
                'services_to_install': MANAGER_SERVICES_TO_INSTALL
            })
            distributed_installation[3].additional_install_config.update({
                'sanity': SKIP_SANITY,
                'cluster': {
                    'master_ip':
                        str(distributed_installation[1].private_ip_address),
                    # cluster_host_ip intentionally left blank
                    'node_name': str(distributed_installation[3].ip_address),
                    'host_ip': ''
                },
                'postgresql_client': {
                    'host':
                        str(distributed_installation[0].private_ip_address),
                    'postgres_password': 'postgres'
                },
                'services_to_install': MANAGER_SERVICES_TO_INSTALL
            })
            if sanity:
                distributed_installation[4].additional_install_config = {
                    'sanity': SKIP_SANITY
                }

    hosts = DistributedInstallationCloudifyManager(cfy=cfy,
                                                   ssh_key=ssh_key,
                                                   tmpdir=module_tmpdir,
                                                   attributes=attributes,
                                                   logger=logger,
                                                   upload_plugins=False,
                                                   cluster=cluster,
                                                   sanity=sanity)

    hosts.preconfigure_callback = _preconfigure_callback_cluster

    all_hosts_list = hosts.instances
    try:
        hosts.create()
        # At this point, we have 3 managers in a cluster with 1 external
        # database inside of hosts
        if cluster:
            hosts.instances = hosts.instances[1:]
        yield hosts
    finally:
        if cluster:
            hosts.instances = all_hosts_list
        hosts.destroy()


def test_distributed_installation_scenario(distributed_installation,
                                           cfy,
                                           logger,
                                           tmpdir,
                                           attributes,
                                           distributed_nodecellar):
    manager = distributed_installation.manager

    _set_admin_user(cfy, manager, logger)

    # Creating secrets
    _create_secrets(cfy, logger, attributes, manager, visibility='global')

    distributed_nodecellar.upload_and_verify_install()

    snapshot_id = 'SNAPSHOT_ID'
    create_snapshot(manager, snapshot_id, attributes, logger)

    # Restore snapshot
    logger.info('Restoring snapshot')
    restore_snapshot(manager, snapshot_id, cfy, logger, force=True)

    distributed_nodecellar.uninstall()


@pytest.mark.parametrize('distributed_installation', ['cluster'],
                         indirect=True)
def test_distributed_installation_ha(distributed_installation,
                                     cfy,
                                     logger,
                                     distributed_ha_hello_worlds):
    logger.info('Testing HA functionality for cluster with an external '
                'database')
    verify_nodes_status(distributed_installation.instances[0], cfy, logger)

    test_failover(cfy, distributed_installation, distributed_ha_hello_worlds,
                  logger)
    reverse_cluster_test(cfy, distributed_installation, logger)

    # Test doesn't affect the cluster - no need to reverse
    test_fail_and_recover(cfy, distributed_installation, logger)


@pytest.mark.parametrize('distributed_installation', ['cluster'],
                         indirect=True)
def test_distributed_installation_ha_remove_from_cluster(
        distributed_installation, cfy, logger, distributed_ha_hello_worlds):
    verify_nodes_status(distributed_installation.instances[0], cfy, logger)
    test_remove_manager_from_cluster(
        cfy, distributed_installation, distributed_ha_hello_worlds,
        logger, delete_profile=False)


@pytest.mark.parametrize('distributed_installation', ['cluster'],
                         indirect=True)
def test_distributed_installation_delete_from_cluster(
        distributed_installation, cfy, logger, distributed_ha_hello_worlds):
    verify_nodes_status(distributed_installation.instances[0], cfy, logger)
    test_delete_manager_node(cfy, distributed_installation,
                             distributed_ha_hello_worlds, logger)


@pytest.mark.parametrize('distributed_installation', [('cluster', 'sanity')],
                         indirect=True)
def test_distributed_installation_sanity(distributed_installation,
                                         cfy,
                                         logger,
                                         tmpdir,
                                         attributes,
                                         distributed_nodecellar):
    logger.info('Running Sanity check for cluster with an external database')
    manager1 = distributed_installation.manager
    manager2, manager3 = distributed_installation.joining_managers
    manager_aio = distributed_installation.sanity_manager

    manager1.use()
    verify_nodes_status(manager1, cfy, logger)

    logger.info('Cfy version')
    cfy('--version')

    logger.info('Cfy status')
    cfy.status()

    _create_and_add_user_to_tenant(cfy, logger)

    _set_sanity_user(cfy, manager1, logger)

    # Creating secrets with 'tenant' visibility
    _create_secrets(cfy, logger, attributes, manager1)

    distributed_nodecellar.upload_and_verify_install()

    _set_admin_user(cfy, manager1, logger)

    # Simulate failover (manager2 will be the new cluster master)
    set_active(manager2, cfy, logger)

    # Create and download snapshots from the new cluster master (manager2)
    snapshot_id = 'SNAPSHOT_ID'
    local_snapshot_path = str(tmpdir / 'snap.zip')
    logger.info('Creating snapshot')
    create_snapshot(manager2, snapshot_id, attributes, logger)
    download_snapshot(manager2, local_snapshot_path, snapshot_id, logger)

    _set_admin_user(cfy, manager_aio, logger)

    # Upload and restore snapshot to manager3
    logger.info('Uploading and restoring snapshot')
    upload_snapshot(manager_aio, local_snapshot_path, snapshot_id, logger)
    restore_snapshot(manager_aio, snapshot_id, cfy, logger)
    time.sleep(7)
    verify_services_status(manager_aio, logger)

    # wait for agents reconnection
    time.sleep(30)

    # Upgrade agents
    logger.info('Upgrading agents')
    _copy_ssl_cert_from_manager_to_tmpdir(manager2, tmpdir)
    args = ['--manager-ip', manager2.private_ip_address,
            '--manager_certificate', str(tmpdir + 'new_manager_cert.txt'),
            '--all-tenants']
    cfy.agents.install(args)

    _set_sanity_user(cfy, manager_aio, logger)
    # Verify `agents install` worked as expected
    distributed_nodecellar.uninstall()


@pytest.fixture(scope='function')
def distributed_ha_hello_worlds(cfy, distributed_installation, attributes,
                                ssh_key, tmpdir, logger):
    # Pick a manager to operate on, and trust the cluster to work with us
    manager = distributed_installation.instances[0]

    hws = []
    for i in range(0, 2):
        tenant = prepare_and_get_test_tenant(
            'clusterhello{num}'.format(num=i),
            manager,
            cfy,
        )
        hw = centos_hello_world(
            cfy, manager, attributes, ssh_key, logger, tmpdir,
            tenant=tenant, suffix=str(i),
        )
        hws.append(hw)

    yield hws
    for hw in hws:
        if hw.cleanup_required:
            logger.info('Cleaning up hello world...')
            manager.use()
            hw.cleanup()


@pytest.fixture(scope='function')
def distributed_nodecellar(cfy, distributed_installation, attributes,
                           ssh_key, tmpdir, logger):
    manager = distributed_installation.manager
    manager.use()
    tenant = prepare_and_get_test_tenant(TENANT_NAME, manager, cfy)
    nc = NodeCellarExample(
        cfy, manager, attributes, ssh_key, logger, tmpdir,
        tenant=tenant, suffix='simple')
    nc.blueprint_file = 'simple-blueprint-with-secrets.yaml'
    yield nc


def _set_test_user(cfy, manager, logger):
    manager.use()
    logger.info('Using manager `{0}`'.format(manager.ip_address))
    cfy.profiles.set('-u', USER_NAME, '-p', USER_PASS, '-t', TENANT_NAME)


def toggle_cluster_node(manager, logger, disable=True):
    """
    Disable or enable a manager to avoid it from being picked as the leader
    during tests
    """
    action_msg, action = \
        ("Shutting down", 'stop') if disable else ("Starting", 'start')
    with manager.ssh() as fabric:
        logger.info('{0} nginx service on manager {1}'.format(
            action_msg, manager.ip_address))
        fabric.run('sudo systemctl {0} nginx'.format(action))


def reverse_cluster_test(cfy, cluster_machines, logger):
    for manager in cluster_machines.instances:
        toggle_cluster_node(manager, logger, disable=False)
    set_active(cluster_machines.instances[0], cfy, logger)
