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

from contextlib import contextmanager
import json
import os

import retrying
from cosmo_tester.framework.cluster import (
    CloudifyCluster,
    MANAGERS,
)
from cosmo_tester.framework.util import (
    assert_snapshot_created,
)
# CFY-6912
from cloudify_cli.commands.executions import (
    _get_deployment_environment_creation_execution,
    )
from cloudify_cli.constants import CLOUDIFY_TENANT_HEADER


HELLO_WORLD_URL = 'https://github.com/cloudify-cosmo/cloudify-hello-world-example/archive/4.0.zip'  # noqa
# We need this because 3.4 (and 4.0!) snapshots don't handle agent_config,
# but 3.4 example blueprints use it instead of cloudify_agent
OLD_WORLD_URL = 'https://github.com/cloudify-cosmo/cloudify-hello-world-example/archive/3.3.1.zip' # noqa
BASE_ID = 'helloworld'
BLUEPRINT_ID = '{base}_bp'.format(base=BASE_ID)
DEPLOYMENT_ID = '{base}_dep'.format(base=BASE_ID)
NOINSTALL_BLUEPRINT_ID = '{base}_noinstall_bp'.format(base=BASE_ID)
NOINSTALL_DEPLOYMENT_ID = '{base}_noinstall_dep'.format(base=BASE_ID)
SNAPSHOT_ID = 'testsnapshot'
# This is used purely for testing that plugin restores have occurred.
# Any plugin should work.
TEST_PLUGIN_URL = 'http://repository.cloudifysource.org/cloudify/wagons/cloudify-openstack-plugin/2.0.1/cloudify_openstack_plugin-2.0.1-py27-none-linux_x86_64-centos-Core.wgn'  # noqa
BASE_PLUGIN_PATH = '/opt/mgmtworker/env/plugins/{tenant}/'
INSTALLED_PLUGIN_PATH = BASE_PLUGIN_PATH + '{name}-{version}'
FROM_SOURCE_PLUGIN_PATH = BASE_PLUGIN_PATH + '{deployment}-{plugin}'
TENANT_DEPLOYMENTS_PATH = (
    '/opt/mgmtworker/work/deployments/{tenant}'
)
DEPLOYMENT_ENVIRONMENT_PATH = (
    TENANT_DEPLOYMENTS_PATH + '/{name}'
)


def upgrade_agents(cfy, manager, logger, tenants=('default_tenant',)):
    manager.use()
    for tenant in tenants:
        _log('Upgrading agents', logger, tenant)
        cfy.agents.install(['-t', tenant])


def remove_and_check_deployments(hello_vms, manager, logger,
                                 tenants=('default_tenant',),
                                 with_prefixes=False):
    for tenant in tenants:
        _log(
            'Uninstalling hello world deployments from manager',
            logger,
            tenant,
        )
        _log(
            'Found deployments: {deployments}'.format(
                deployments=', '.join(get_deployments_list(manager, tenant)),
            ),
            logger,
            tenant,
        )
        with set_client_tenant(manager, tenant):
            if with_prefixes:
                deployment_id = tenant + DEPLOYMENT_ID
            else:
                deployment_id = DEPLOYMENT_ID
            execution = manager.client.executions.start(
                deployment_id,
                'uninstall',
            )

        logger.info('Waiting for uninstall to finish')
        wait_for_execution(
            manager,
            execution,
            logger,
            tenant,
        )
        _log('Uninstalled deployments', logger, tenant)

    assert_hello_worlds(hello_vms, installed=False, logger=logger)


def delete_manager(manager, logger):
    logger.info('Deleting {version} manager..'.format(
        version=manager.branch_name))
    manager.delete()


def create_helloworld_just_deployment(manager, logger, tenant=None):
    """
        Upload an AWS hello world blueprint and create a deployment from it.
        This is used for checking that plugins installed from source work as
        expected.
    """
    upload_helloworld(
        manager,
        'ec2-blueprint.yaml',
        NOINSTALL_BLUEPRINT_ID,
        tenant,
        logger,
    )

    inputs = {
        'image_id': 'does not matter',
    }

    deploy_helloworld(
        manager,
        inputs,
        NOINSTALL_BLUEPRINT_ID,
        NOINSTALL_DEPLOYMENT_ID,
        tenant,
        logger,
    )


def upload_helloworld(manager, blueprint, blueprint_id, tenant, logger):
    version = manager.branch_name
    url = OLD_WORLD_URL if version in ('3.4.2', '4.0') else HELLO_WORLD_URL
    logger.info(
        'Uploading blueprint {blueprint} from archive {archive} as {name} '
        'for manager version {version}'.format(
            blueprint=blueprint,
            archive=url,
            name=blueprint_id,
            version=version,
        )
    )
    with set_client_tenant(manager, tenant):
        manager.client.blueprints.publish_archive(
            url,
            blueprint_id,
            blueprint,
        )


def deploy_helloworld(manager, inputs, blueprint_id,
                      deployment_id, tenant, logger):
    version = manager.branch_name
    _log(
        'Deploying {deployment} on {version} manager'.format(
            deployment=deployment_id,
            version=version,
        ),
        logger,
        tenant,
    )
    with set_client_tenant(manager, tenant):
        manager.client.deployments.create(
            blueprint_id,
            deployment_id,
            inputs,
        )

        creation_execution = _get_deployment_environment_creation_execution(
            manager.client, deployment_id)
    logger.info('Waiting for execution environment')
    wait_for_execution(
        manager,
        creation_execution,
        logger,
        tenant,
    )
    logger.info('Deployment environment created')


def upload_and_install_helloworld(attributes, logger, manager, target_vm,
                                  tmpdir, prefix='', tenant=None):
    assert not is_hello_world(target_vm), (
        'Hello world blueprint already installed!'
    )
    version = manager.branch_name
    _log(
        'Uploading helloworld blueprint to {version} manager'.format(
            version=version,
        ),
        logger,
        tenant,
    )
    blueprint_id = prefix + BLUEPRINT_ID
    deployment_id = prefix + DEPLOYMENT_ID
    inputs = {
        'server_ip': target_vm.ip_address,
        'agent_user': attributes.centos7_username,
        'agent_private_key_path': manager.remote_private_key_path,
    }
    upload_helloworld(
        manager,
        'singlehost-blueprint.yaml',
        blueprint_id,
        tenant,
        logger,
    )

    deploy_helloworld(
        manager,
        inputs,
        blueprint_id,
        deployment_id,
        tenant,
        logger,
    )

    with set_client_tenant(manager, tenant):
        execution = manager.client.executions.start(
            deployment_id,
            'install',
            )
    logger.info('Waiting for installation to finish')
    wait_for_execution(
        manager,
        execution,
        logger,
        tenant,
    )
    assert is_hello_world(target_vm), (
        'Hello world blueprint did not install correctly.'
    )


class ExecutionWaiting(Exception):
    """
    raised by `wait_for_execution` if it should be retried
    """
    pass


class ExecutionFailed(Exception):
    """
    raised by `wait_for_execution` if a bad state is reached
    """
    pass


def retry_if_not_failed(exception):
    return not isinstance(exception, ExecutionFailed)


@retrying.retry(
    stop_max_delay=5 * 60 * 1000,
    wait_fixed=10000,
    retry_on_exception=retry_if_not_failed,
)
def wait_for_execution(manager, execution, logger, tenant=None):
    _log(
        'Getting workflow execution [id={execution}]'.format(
            execution=execution['id'],
        ),
        logger,
        tenant,
    )
    with set_client_tenant(manager, tenant):
        execution = manager.client.executions.get(execution['id'])
    logger.info('- execution.status = %s', execution.status)
    if execution.status not in execution.END_STATES:
        raise ExecutionWaiting(execution.status)
    if execution.status != execution.TERMINATED:
        raise ExecutionFailed(execution.status)
    return execution


def check_from_source_plugin(manager, plugin, deployment_id, logger,
                             tenant='default_tenant'):
    with manager.ssh() as fabric_ssh:
        _log(
            'Checking plugin {plugin} was installed from source for '
            'deployment {deployment}'.format(
                plugin=plugin,
                deployment=deployment_id,
            ),
            logger,
            tenant,
        )
        path = FROM_SOURCE_PLUGIN_PATH.format(
            plugin=plugin,
            deployment=deployment_id,
            tenant=tenant,
        )
        fabric_ssh.run('test -d {path}'.format(path=path))
        logger.info('Plugin installed from source successfully.')


def confirm_manager_empty(manager):
    assert get_plugins_list(manager) == []
    assert get_deployments_list(manager) == []


def is_hello_world(vm):
    with vm.ssh() as fabric_ssh:
        result = fabric_ssh.sudo(
            'curl localhost:8080 || echo "Curl failed."'
        )
        return 'Cloudify Hello World' in result


def assert_hello_worlds(hello_vms, installed, logger):
    """
        Assert that all hello worlds are saying hello if installed is True.

        If installed is False then instead confirm that they are all not
        saying hello, to allow for detection of uninstall workflow failures.

        :param hello_vms: A list of all hello world VMs.
        :param installed: Boolean determining whether we are checking for
                          hello world deployments that are currently
                          installed (True) or not installed (False).
        :param logger: A logger to provide useful output.
    """
    logger.info('Confirming that hello world services are {state}.'.format(
        state='running' if installed else 'not running',
    ))
    for hello_vm in hello_vms:
        if installed:
            assert is_hello_world(hello_vm), (
                'Hello world was not running after restore.'
            )
        else:
            assert not is_hello_world(hello_vm), (
                'Hello world blueprint did not uninstall correctly.'
            )
    logger.info('Hello world services are in expected state.')


def create_snapshot(manager, snapshot_id, attributes, logger):
    logger.info('Creating snapshot on old manager..')
    manager.client.snapshots.create(
        snapshot_id=snapshot_id,
        include_metrics=True,
        include_credentials=True,
    )
    assert_snapshot_created(manager, snapshot_id, attributes)


def download_snapshot(manager, local_path, snapshot_id, logger):
    logger.info('Downloading snapshot from old manager..')
    manager.client.snapshots.list()
    manager.client.snapshots.download(snapshot_id, local_path)


def upload_snapshot(manager, local_path, snapshot_id, logger):
    logger.info('Uploading snapshot to latest manager..')
    snapshot = manager.client.snapshots.upload(local_path,
                                               snapshot_id)
    logger.info('Uploaded snapshot:%s%s',
                os.linesep,
                json.dumps(snapshot, indent=2))


def restore_snapshot(manager, snapshot_id, cfy, logger):
    # Show the snapshots, to aid troubleshooting on failures
    manager.use()
    cfy.snapshots.list()

    logger.info('Restoring snapshot on latest manager..')
    restore_execution = manager.client.snapshots.restore(
        snapshot_id,
    )
    try:
        restore_execution = wait_for_execution(
            manager,
            restore_execution,
            logger)
    except ExecutionFailed:
        # See any errors
        cfy.executions.list(['--include-system-workflows'])
        raise


def check_plugins(manager, old_plugins, logger, tenant='default_tenant'):
    """
        Make sure that all plugins on the manager are correctly installed.
        This checks not just for their existence in the API, but also that
        they exist in the correct place on the manager filesystem.
        This is intended for use checking a new manager has all plugins
        correctly restored by a snapshot.

        :param manager: The manager to check.
        :param old_plugins: A list of plugins on the old manager. This will be
                            checked to confirm that all of the plugins have
                            been restored on the new manager.
        :param logger: A logger to provide useful output.
        :param tenant: Set to check tenants other than the default tenant.
                       Whichever tenant name this is set to will be checked.
                       Defaults to default_tenant.
    """
    _log('Checking plugins', logger, tenant)
    plugins = get_plugins_list(manager, tenant)
    assert plugins == old_plugins

    # Now make sure they're correctly installed
    with manager.ssh() as fabric_ssh:
        for plugin_name, plugin_version, _ in plugins:
            path = INSTALLED_PLUGIN_PATH.format(
                tenant=tenant,
                name=plugin_name,
                version=plugin_version,
            )
            logger.info('Checking plugin {name} is in {path}'.format(
                name=plugin_name,
                path=path,
            ))
            fabric_ssh.run('test -d {path}'.format(path=path))
            logger.info('Plugin is correctly installed.')

    _log('Plugins as expected', logger, tenant)


def check_deployments(manager, old_deployments, logger,
                      tenant='default_tenant'):
    deployments = get_deployments_list(manager, tenant)
    assert deployments == old_deployments

    _log('Checking deployments', logger, tenant)
    # Now make sure the envs were recreated
    with manager.ssh() as fabric_ssh:
        for deployment in deployments:
            path = DEPLOYMENT_ENVIRONMENT_PATH.format(
                tenant=tenant,
                name=deployment,
            )
            logger.info(
                'Checking deployment env for {name} was recreated.'.format(
                    name=deployment,
                )
            )
            # To aid troubleshooting when the following line fails
            _log('Listing deployments path', logger, tenant)
            fabric_ssh.run('ls -la {path}'.format(
                path=TENANT_DEPLOYMENTS_PATH.format(
                    tenant=tenant,
                ),
            ))
            _log(
                'Checking deployment path for {name}'.format(
                    name=deployment,
                ),
                logger,
                tenant,
            )
            fabric_ssh.run('test -d {path}'.format(path=path))
            logger.info('Deployment environment was recreated.')
    _log('Found correct deployments', logger, tenant)


@contextmanager
def set_client_tenant(manager, tenant):
    if tenant:
        original = manager.client._client.headers[CLOUDIFY_TENANT_HEADER]

        manager.client._client.headers[CLOUDIFY_TENANT_HEADER] = tenant

    try:
        yield
    except:
        raise
    finally:
        if tenant:
            manager.client._client.headers[CLOUDIFY_TENANT_HEADER] = original


def upload_test_plugin(manager, logger, tenant=None):
    _log('Uploading test plugin', logger, tenant)
    with set_client_tenant(manager, tenant):
        manager.client.plugins.upload(TEST_PLUGIN_URL)


def get_plugins_list(manager, tenant=None):
    with set_client_tenant(manager, tenant):
        return [
            (
                item['package_name'],
                item['package_version'],
                item['distribution'],
            )
            for item in manager.client.plugins.list()
        ]


def get_deployments_list(manager, tenant=None):
    with set_client_tenant(manager, tenant):
        return [
            item['id'] for item in manager.client.deployments.list()
        ]


def get_secrets_list(manager, tenant=None):
    with set_client_tenant(manager, tenant):
        return [
            item['key'] for item in manager.client.secrets.list()
        ]


def get_nodes(manager, tenant=None):
    with set_client_tenant(manager, tenant):
        return manager.client.nodes.list()


def cluster(request, cfy, ssh_key, module_tmpdir, attributes, logger,
            hello_count, install_dev_tools=True):

    manager_types = [request.param, 'master']
    hello_vms = ['notamanager' for i in range(hello_count)]
    managers = [
        MANAGERS[mgr_type](upload_plugins=False)
        for mgr_type in manager_types + hello_vms
    ]

    cluster = CloudifyCluster.create_image_based(
            cfy,
            ssh_key,
            module_tmpdir,
            attributes,
            logger,
            managers=managers,
            )

    if request.param == '4.0.1':
        with managers[0].ssh() as fabric_ssh:
            fabric_ssh.sudo('yum -y -q install wget')
            fabric_ssh.sudo(
                'cd /tmp && '
                'mkdir patch && '
                'cd patch && '
                'wget http://repository.cloudifysource.org/cloudify/4.0.1/patch3/cloudify-401-te-patch-3.tar.gz && '  # noqa
                'tar --strip-components=1 -xzf *.tar.gz && '
                './apply-patch.sh'
            )

    # gcc and python-devel are needed to build most of our infrastructure
    # plugins.
    # As we need to test from source installation of plugins, we must have
    # these packages installed.
    # We'll iterate over only the old and new managers (managers[0] and
    # managers[1].
    # The hello_world VMs don't need these so we won't waste time installing
    # them.
    for manager in managers[:2]:
        with manager.ssh() as fabric_ssh:
            fabric_ssh.sudo('yum -y -q install gcc')
            fabric_ssh.sudo('yum -y -q install python-devel')

    return cluster


def _log(message, logger, tenant=None):
    if tenant:
        message += ' for {tenant}'.format(tenant=tenant)
    logger.info(message)
