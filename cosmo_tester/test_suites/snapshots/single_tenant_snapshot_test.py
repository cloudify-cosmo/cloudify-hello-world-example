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
    check_deployments,
    verify_services_status,
    check_from_source_plugin,
    check_plugins,
    hosts,
    check_credentials,
    confirm_manager_empty,
    create_helloworld_just_deployment,
    create_snapshot,
    delete_manager,
    download_snapshot,
    get_deployments_list,
    get_nodes,
    get_plugins_list,
    get_secrets_list,
    get_single_tenant_versions_list,
    manager_supports_users_in_snapshot_creation,
    NOINSTALL_DEPLOYMENT_ID,
    prepare_credentials_tests,
    remove_and_check_deployments,
    restore_snapshot,
    SNAPSHOT_ID,
    upgrade_agents,
    upload_and_install_helloworld,
    upload_snapshot,
    upload_test_plugin,
)


def test_restore_snapshot_and_agents_upgrade_singletenant(
        cfy, hosts_singletenant, attributes, logger, tmpdir):
    local_snapshot_path = str(tmpdir / 'snapshot.zip')
    old_manager = hosts_singletenant.instances[0]
    new_manager = hosts_singletenant.instances[1]
    hello_vm = hosts_singletenant.instances[2]

    confirm_manager_empty(new_manager)

    upload_and_install_helloworld(attributes, logger, old_manager,
                                  hello_vm, tmpdir)
    create_helloworld_just_deployment(old_manager, logger)

    upload_test_plugin(old_manager, logger)

    old_plugins = get_plugins_list(old_manager)
    old_deployments = get_deployments_list(old_manager)

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

    assert_hello_worlds([hello_vm], installed=True, logger=logger)

    if old_manager.branch_name in ('3.4.2', '4.0'):
        # Check we convert secrets for pre-service-user versions
        # In 4.0.1 and beyond we are using service users so the secrets
        # conversion was determined not to be needed any more as after
        # that change, keys could no longer be placed in locations that
        # would not be able to be read by the mgmtworker.
        check_secrets_converted(new_manager, logger)
    check_plugins(new_manager, old_plugins, logger)
    check_deployments(new_manager, old_deployments, logger)
    check_from_source_plugin(
        new_manager,
        'aws',
        NOINSTALL_DEPLOYMENT_ID,
        logger,
    )

    upgrade_agents(cfy, new_manager, logger)

    # The old manager needs to exist until the agents install is run
    delete_manager(old_manager, logger)

    remove_and_check_deployments([hello_vm], new_manager, logger)


@pytest.fixture(
        scope='module',
        params=get_single_tenant_versions_list())
def hosts_singletenant(
        request, cfy, ssh_key, module_tmpdir, attributes,
        logger, install_dev_tools=True):
    st_hosts = hosts(
            request, cfy, ssh_key, module_tmpdir, attributes,
            logger, 1, install_dev_tools)
    yield st_hosts
    st_hosts.destroy()


def check_secrets_converted(manager, logger, tenant='default_tenant'):
    logger.info(
        'Checking any applicable secrets have been converted for '
        '{tenant}'.format(tenant=tenant),
    )
    nodes = get_nodes(manager, tenant=tenant)
    secrets = get_secrets_list(manager, tenant=tenant)

    for node in nodes:
        logger.info('Checking node {name}'.format(name=node.id))
        props = node.properties
        if 'agent_config' not in props and 'cloudify_agent' not in props:
            # Not a compute node
            continue
        try:
            # Use new config where possible
            agent_key = props['agent_config']['key']
        except KeyError:
            # Get the key from the old agent config if it's there
            agent_key = props.get('cloudify_agent', {}).get('key', None)

        if agent_key is None:
            # No key provided, so it can't be wrong
            continue

        logger.info('Checking key is getting secret...')
        assert isinstance(agent_key, dict) and agent_key['get_secret'], (
            'Agent key for node {deployment}/{node} was not using secrets. '
            'Found key information: {key}'.format(
                deployment=node.deployment_id,
                node=node.id,
                key=agent_key,
            )
        )
        logger.info('...key is getting secret.')

        logger.info('Checking secret exists...')
        assert agent_key['get_secret'] in secrets, (
            'Secret {name} was not found in manager secrets!'
            'Manager secrets for {tenant} were: {secrets}'.format(
                name=agent_key,
                tenant=tenant,
                secrets=', '.join(secrets),
            )
        )
        logger.info('...secret exists.')

    logger.info('Any applicable secrets were converted for {tenant}'.format(
        tenant=tenant,
    ))
