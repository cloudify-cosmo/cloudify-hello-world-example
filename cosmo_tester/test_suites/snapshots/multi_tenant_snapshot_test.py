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

from . import (
    assert_hello_worlds,
    check_credentials,
    check_deployments,
    verify_services_status,
    check_from_source_plugin,
    check_plugins,
    hosts,
    confirm_manager_empty,
    create_helloworld_just_deployment,
    create_snapshot,
    delete_manager,
    download_snapshot,
    get_deployments_list,
    get_plugins_list,
    get_multi_tenant_versions_list,
    get_secrets_list,
    manager_supports_users_in_snapshot_creation,
    NOINSTALL_DEPLOYMENT_ID,
    prepare_credentials_tests,
    remove_and_check_deployments,
    restore_snapshot,
    set_client_tenant,
    SNAPSHOT_ID,
    upgrade_agents,
    upload_and_install_helloworld,
    upload_snapshot,
    upload_test_plugin,
)


def test_restore_snapshot_and_agents_upgrade_multitenant(
        cfy, hosts_multitenant, attributes, logger, tmpdir):
    local_snapshot_path = str(tmpdir / 'snapshot.zip')
    new_tenants = ('tenant1', 'tenant2')
    # These tenants will have hello world deployments installed on them
    hello_tenants = ('default_tenant', new_tenants[0])
    # These tenants will have additional hello world deployments which will
    # not have the install workflow run on them
    noinstall_tenants = new_tenants

    old_manager = hosts_multitenant.instances[0]
    new_manager = hosts_multitenant.instances[1]
    hello_vms = hosts_multitenant.instances[2:]

    hello_vm_mappings = {
        hello_tenants[0]: hosts_multitenant.instances[2],
        hello_tenants[1]: hosts_multitenant.instances[3],
    }

    confirm_manager_empty(new_manager)

    create_tenants(old_manager, logger, tenants=new_tenants)
    tenants = ['default_tenant']
    tenants.extend(new_tenants)

    for tenant in hello_tenants:
        upload_and_install_helloworld(attributes, logger, old_manager,
                                      hello_vm_mappings[tenant],
                                      tmpdir, tenant=tenant, prefix=tenant)
    for tenant in noinstall_tenants:
        create_helloworld_just_deployment(old_manager, logger, tenant=tenant)

    for tenant in tenants:
        upload_test_plugin(old_manager, logger, tenant)

    create_tenant_secrets(old_manager, tenants, logger)

    old_plugins = {
        tenant: get_plugins_list(old_manager, tenant)
        for tenant in tenants
    }
    old_secrets = {
        tenant: get_secrets_list(old_manager, tenant)
        for tenant in tenants
    }
    old_deployments = {
        tenant: get_deployments_list(old_manager, tenant)
        for tenant in tenants
    }

    # Credentials tests only apply to 4.2 and later
    if manager_supports_users_in_snapshot_creation(old_manager):
        prepare_credentials_tests(cfy, logger, old_manager)

    create_snapshot(old_manager, SNAPSHOT_ID, attributes, logger)
    download_snapshot(old_manager, local_snapshot_path, SNAPSHOT_ID, logger)
    upload_snapshot(new_manager, local_snapshot_path, SNAPSHOT_ID, logger)

    restore_snapshot(new_manager, SNAPSHOT_ID, cfy, logger)

    verify_services_status(new_manager, logger)

    # Credentials tests only apply to 4.2 and later
    if manager_supports_users_in_snapshot_creation(old_manager):
        check_credentials(cfy, logger, new_manager)

    # Make sure we still have the hello worlds after the restore
    assert_hello_worlds(hello_vms, installed=True, logger=logger)

    # We don't check agent keys are converted to secrets because that is only
    # expected to happen for 3.x restores now.
    check_tenant_secrets(new_manager, tenants, old_secrets, logger)
    check_tenant_plugins(new_manager, old_plugins, tenants, logger)
    check_tenant_deployments(new_manager, old_deployments, tenants, logger)
    check_tenant_source_plugins(new_manager, 'aws', NOINSTALL_DEPLOYMENT_ID,
                                noinstall_tenants, logger)

    upgrade_agents(cfy, new_manager, logger)

    # The old manager needs to exist until the agents install is run
    delete_manager(old_manager, logger)

    # Make sure the agent upgrade and old manager removal didn't
    # damage the hello worlds
    assert_hello_worlds(hello_vms, installed=True, logger=logger)

    remove_and_check_deployments(hello_vms, new_manager, logger,
                                 hello_tenants, with_prefixes=True)


@pytest.fixture(
        scope='module',
        params=get_multi_tenant_versions_list())
def hosts_multitenant(
        request, cfy, ssh_key, module_tmpdir, attributes,
        logger, install_dev_tools=True):
    mt_hosts = hosts(
            request, cfy, ssh_key, module_tmpdir, attributes,
            logger, 2, install_dev_tools)
    yield mt_hosts
    mt_hosts.destroy()


def create_tenant_secrets(manager, tenants, logger):
    """
        Create some secrets to allow us to confirm whether secrets are
        successfully restored by snapshots.

        :param manager: The manager to create secrets on.
        :param tenants: A list of tenants to create secrets for.
        :param logger: A logger to provide useful output.
    """
    logger.info('Creating secrets...')
    for tenant in tenants:
        with set_client_tenant(manager, tenant):
            manager.client.secrets.create(
                key=tenant,
                value=tenant,
            )
        assert tenant in get_secrets_list(manager, tenant), (
            'Failed to create secret for {tenant}'.format(tenant=tenant)
        )
    logger.info('Secrets created.')


def check_tenant_secrets(manager, tenants, old_secrets, logger):
    """
        Check that secrets are correctly restored onto a new manager.
        This includes confirming that no new secrets are created except for
        those that are created as part of the SSH key -> secret migrations.

        :param manager: The manager to check for restored secrets.
        :param tenants: The tenants to check.
        :param old_secrets: A dict containing lists of secrets keyed by tenant
                            name.
        :param logger: A logger to provide useful output.
    """
    for tenant in tenants:
        logger.info('Checking secrets for {tenant}'.format(tenant=tenant))
        non_agentkey_secrets = [
            secret for secret in get_secrets_list(manager, tenant)
            if not secret.startswith('cfyagent_key__')
        ]
        non_agentkey_secrets.sort()
        logger.info('Found secrets for {tenant} on manager: {secrets}'.format(
            tenant=tenant,
            secrets=', '.join(non_agentkey_secrets),
        ))

        old_tenant_secrets = old_secrets[tenant]
        old_tenant_secrets.sort()

        assert non_agentkey_secrets == old_tenant_secrets, (
            'Secrets for {tenant} do not match old secrets!'.format(
                tenant=tenant,
            )
        )
        logger.info('Secrets for {tenant} are correct.'.format(tenant=tenant))


def check_tenant_plugins(manager, old_plugins, tenants, logger):
    logger.info('Checking uploaded plugins are correct for all tenants.')
    for tenant in tenants:
        check_plugins(manager, old_plugins[tenant], logger, tenant)
    logger.info('Uploaded plugins are correct for all tenants.')


def check_tenant_deployments(manager, old_deployments, tenants, logger):
    logger.info('Checking deployments are correct for all tenants.')
    for tenant in tenants:
        check_deployments(manager, old_deployments[tenant], logger,
                          tenant=tenant)
    logger.info('Deployments are correct for all tenants.')


def check_tenant_source_plugins(manager, plugin, deployment_id, tenants,
                                logger):
    logger.info(
        'Checking from-source plugin installs for tenants: {tenants}'.format(
            tenants=', '.join(tenants),
        )
    )
    for tenant in tenants:
        check_from_source_plugin(manager, plugin, deployment_id, logger,
                                 tenant)
    logger.info('Plugins installed from source were installed correctly.')


def create_tenants(manager, logger, tenants=('tenant1', 'tenant2')):
    for tenant in tenants:
        logger.info('Creating tenant {tenant}'.format(tenant=tenant))
        manager.client.tenants.create(tenant)
        logger.info('Tenant {tenant} created.'.format(tenant=tenant))
    return tenants
