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
from cosmo_tester.framework.test_hosts import \
    DistributedInstallationCloudifyManager
from cosmo_tester.framework.util import prepare_and_get_test_tenant
from cosmo_tester.test_suites.snapshots import (
    create_snapshot,
    restore_snapshot
)

USER_NAME = "test_user"
USER_PASS = "testuser123"
TENANT_NAME = "tenant"


@pytest.fixture(scope='module')
def database_and_manager(cfy, ssh_key, module_tmpdir, attributes, logger):
    """
    Bootstraps a cloudify manager with no DB on a VM in rackspace OpenStack.
    """
    # The preconfigure callback populates the files structure prior to the BS
    def _preconfigure_callback_manager_and_database(database_and_manager):
        # Updating the database VM first
        database_and_manager[0].additional_install_config = {
            'sanity': {'skip_sanity': 'true'},
            'postgresql_server': {'enable_remote_connections': 'true'},
            'services_to_install': [
                'database_service'
            ]
        }
        database_and_manager[1].additional_install_config = {
            'sanity': {'skip_sanity': 'true'},
            'postgresql_client': {
                'host': str(database_and_manager[0].private_ip_address)
            },
            'services_to_install': [
                'queue_service',
                'composer_service',
                'manager_service'
            ]
        }

    hosts = DistributedInstallationCloudifyManager(cfy=cfy,
                                                   ssh_key=ssh_key,
                                                   tmpdir=module_tmpdir,
                                                   attributes=attributes,
                                                   logger=logger)

    hosts.manager.upload_plugins = False

    hosts.preconfigure_callback = _preconfigure_callback_manager_and_database

    try:
        hosts.create()
        yield hosts
    finally:
        hosts.destroy()


@pytest.fixture(scope='function')
def nodecellar(cfy, database_and_manager, attributes, ssh_key, tmpdir, logger):
    # Uploading to the manager not the database
    manager = database_and_manager.manager
    manager.use()
    tenant = prepare_and_get_test_tenant(TENANT_NAME, manager, cfy)
    nc = NodeCellarExample(
        cfy, manager, attributes, ssh_key, logger, tmpdir,
        tenant=tenant, suffix='simple')
    nc.blueprint_file = 'simple-blueprint-with-secrets.yaml'
    yield nc


def test_distributed_installation_scenario(database_and_manager,
                                           cfy,
                                           logger,
                                           tmpdir,
                                           attributes,
                                           nodecellar):
    manager = database_and_manager.manager

    _create_and_add_user_to_tenant(cfy, logger)

    _set_test_user(cfy, manager, logger)

    # Creating secrets
    _create_secrets(cfy, logger, attributes, manager)

    nodecellar.upload_and_verify_install()

    snapshot_id = 'SNAPSHOT_ID'
    create_snapshot(manager, snapshot_id, attributes, logger)

    _set_admin_user(cfy, manager, logger)

    # Restore snapshot
    logger.info('Restoring snapshot')
    restore_snapshot(manager, snapshot_id, cfy, logger, force=True)

    # wait a while to allow the restore-snapshot post-workflow commands to run
    time.sleep(30)

    nodecellar.uninstall()


def _create_and_add_user_to_tenant(cfy, logger):
    logger.info('Creating new user')
    cfy.users.create(USER_NAME, '-p', USER_PASS)

    logger.info('Adding user to tenant')
    cfy.tenants('add-user', USER_NAME, '-t', TENANT_NAME, '-r', 'user')


def _set_test_user(cfy, manager, logger):
    manager.use()
    logger.info('Using manager `{0}`'.format(manager.ip_address))
    cfy.profiles.set('-u', USER_NAME, '-p', USER_PASS, '-t', TENANT_NAME)


def _set_admin_user(cfy, manager, logger):
    manager.use()
    logger.info('Using manager `{0}`'.format(manager.ip_address))
    cfy.profiles.set('-u', 'admin', '-p', 'admin', '-t', 'default_tenant')


def _create_secrets(cfy, logger, attributes, manager):
    logger.info('Creating secret agent_user as blueprint input')
    cfy.secrets.create('agent_user', '-s', attributes.default_linux_username)

    logger.info('Creating secret agent_private_key_path as blueprint input')
    cfy.secrets.create('agent_private_key_path', '-s',
                       manager.remote_private_key_path)

    logger.info('Creating secret host_ip as blueprint input')
    cfy.secrets.create('host_ip', '-s', manager.ip_address)
