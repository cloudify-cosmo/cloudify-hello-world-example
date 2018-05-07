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
import pytest

from cosmo_tester.framework.examples.nodecellar import NodeCellarExample
from cosmo_tester.framework.test_hosts import BootstrapBasedCloudifyManagers
from cosmo_tester.framework.util import prepare_and_get_test_tenant

from cosmo_tester.test_suites.snapshots import (
    create_snapshot,
    download_snapshot,
    upload_snapshot,
    restore_snapshot,
    # upgrade_agents,    # bug in agents upgrade
    verify_services_status
)

# from cosmo_tester.test_suites.ha.ha_helper \    # agents upgrade bug CY-278
#     import HighAvailabilityHelper as ha_helper

USER_NAME = "sanity_user"
USER_PASS = "user123"
TENANT_NAME = "tenant"


@pytest.fixture(scope='module')
def managers(cfy, ssh_key, module_tmpdir, attributes, logger):
    """Bootstraps 3 Cloudify managers on a VM in Rackspace OpenStack."""

    hosts = BootstrapBasedCloudifyManagers(
        cfy, ssh_key, module_tmpdir, attributes, logger,
        number_of_instances=3)

    for manager in hosts.instances[1:]:
        manager.upload_plugins = False

    try:
        hosts.create()
        yield hosts.instances
    finally:
        hosts.destroy()


@pytest.fixture(scope='function')
def nodecellar(request, cfy, managers, attributes, ssh_key, tmpdir, logger):
    manager = managers[0]
    manager.use()
    tenant = prepare_and_get_test_tenant(TENANT_NAME, manager, cfy)
    nc = NodeCellarExample(
        cfy, manager, attributes, ssh_key, logger, tmpdir,
        tenant=tenant, suffix='simple')
    nc.blueprint_file = 'simple-blueprint-with-secrets.yaml'
    yield nc


def test_sanity_scenario(managers,
                         cfy,
                         logger,
                         tmpdir,
                         attributes,
                         nodecellar):
    manager1 = managers[0]
    manager2 = managers[1]
    manager3 = managers[2]

    logger.info('Cfy version')
    cfy('--version')

    logger.info('Cfy status')
    cfy.status()

    # Create user and add the new user to the tenant
    _create_and_add_user_to_tenant(cfy, logger)

    _set_sanity_user(cfy, manager1, logger)

    # Creating secrets
    _create_secrets(cfy, logger, attributes, manager1)

    nodecellar.upload_and_verify_install()

    _set_admin_user(cfy, manager1, logger)

    _start_cluster(cfy, manager1, logger)

    _set_admin_user(cfy, manager2, logger)

    _join_cluster(cfy, manager1, manager2, logger)

    logger.info('Setting replica manager')
    # ha_helper.set_active(manager2, cfy, logger)   # bug in agents upgrade

    snapshot_id = 'SNAPSHOT_ID'
    local_snapshot_path = str(tmpdir / 'snap.zip')
    logger.info('Creating snapshot')
    create_snapshot(manager1, snapshot_id, attributes, logger)
    download_snapshot(manager1, local_snapshot_path, snapshot_id, logger)

    _set_admin_user(cfy, manager3, logger)

    logger.info('Uploading and restoring snapshot')
    upload_snapshot(manager3, local_snapshot_path, snapshot_id, logger)
    restore_snapshot(manager3, snapshot_id, cfy, logger)
    verify_services_status(manager3)
    # wait for agents reconnection
    time.sleep(30)

    # upgrade_agents(cfy, manager3, logger)          # bug in agents upgrade

    _set_sanity_user(cfy, manager3, logger)

    # nodecellar.uninstall()                         # bug in agents upgrade


def _create_secrets(cfy, logger, attributes, manager1):
    logger.info('Creating secret agent_user as blueprint input')
    cfy.secrets.create('agent_user', '-s', attributes.default_linux_username)

    logger.info('Creating secret agent_private_key_path as blueprint input')
    cfy.secrets.create('agent_private_key_path', '-s',
                       manager1.remote_private_key_path)

    logger.info('Creating secret host_ip as blueprint input')
    cfy.secrets.create('host_ip', '-s', manager1.ip_address)


def _create_and_add_user_to_tenant(cfy, logger):
    logger.info('Creating new user')
    cfy.users.create(USER_NAME, '-p', USER_PASS)

    logger.info('Adding user to tenant')
    cfy.tenants('add-user', USER_NAME, '-t', TENANT_NAME, '-r', 'user')


def _set_sanity_user(cfy, manager, logger):
    manager.use()
    logger.info('Using manager `{0}`'.format(manager.ip_address))
    cfy.profiles.set('-u', USER_NAME, '-p', USER_PASS, '-t', TENANT_NAME)


def _set_admin_user(cfy, manager, logger):
    manager.use()
    logger.info('Using manager `{0}`'.format(manager.ip_address))
    cfy.profiles.set('-u', 'admin', '-p', 'admin', '-t', 'default_tenant')


def _start_cluster(cfy, manager1, logger):
    logger.info('Starting HA cluster')
    cfy.cluster.start(timeout=600,
                      cluster_host_ip=manager1.private_ip_address,
                      cluster_node_name=manager1.ip_address)


def _join_cluster(cfy, manager1, manager2, logger):
    logger.info('Joining HA cluster')
    cfy.cluster.join(manager1.ip_address,
                     timeout=600,
                     cluster_host_ip=manager2.private_ip_address,
                     cluster_node_name=manager2.ip_address)
    cfy.cluster.nodes.list()
