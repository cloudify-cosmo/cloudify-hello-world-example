#######
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

import base64
from contextlib import contextmanager
import hashlib
import hmac
import json
import os

from passlib.context import CryptContext
import retrying

from cosmo_tester.framework.test_hosts import (
    TestHosts,
    IMAGES,
)
from cosmo_tester.framework.util import (
    assert_snapshot_created,
    create_rest_client,
    is_community,
)
# CFY-6912
from cloudify_cli.commands.executions import (
    _get_deployment_environment_creation_execution,
)
from cloudify_cli.constants import CLOUDIFY_TENANT_HEADER
from cloudify_rest_client.exceptions import UserUnauthorizedError


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
    '/opt/mgmtworker/work/deployments/{tenant}/{name}'
)
CHANGED_ADMIN_PASSWORD = 'changedmin'

# These manager versions only support single tenant snapshot restores in
# premium
SINGLE_TENANT_MANAGERS = (
    '3.4.2',
    # Technically this supports multiple tenants, but we can't restore
    # snapshots from it with multiple tenants.
    '4.0',
)
# These manager versions support multiple tenant snapshot restores in premium
MULTI_TENANT_MANAGERS = (
    '4.0.1',
    '4.1',
    'master',
)


def get_single_tenant_versions_list():
    if is_community():
        # Community only works single tenanted so should eventually be testing
        # SINGLE_TENANT_MANAGERS + MULTI_TENANT_MANAGERS here...
        # Unfortunately, at the moment there are resource constraints in the
        # test environment so it will only be testing current.
        return ['master']
    else:
        return SINGLE_TENANT_MANAGERS


def get_multi_tenant_versions_list():
    if is_community():
        # Community only works single tenanted
        return ()
    else:
        return MULTI_TENANT_MANAGERS


def upgrade_agents(cfy, manager, logger):
    logger.info('Upgrading agents')
    args = [] if is_community() else ['--all-tenants']
    cfy.agents.install(args)


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
        'agent_user': attributes.centos_7_username,
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
            'install')
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
    try:
        with set_client_tenant(manager, tenant):
            execution = manager.client.executions.get(execution['id'])
    except UserUnauthorizedError:
        if manager_supports_users_in_snapshot_creation(manager):
            # This will happen on a restore with modified users
            change_rest_client_password(manager, CHANGED_ADMIN_PASSWORD)
        raise
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
    if manager_supports_users_in_snapshot_creation(manager):
        password = CHANGED_ADMIN_PASSWORD
    else:
        password = 'admin'
    assert_snapshot_created(manager, snapshot_id, password)


def manager_supports_users_in_snapshot_creation(manager):
    return (
        manager.branch_name not in ('3.4.2', '4.0', '4.0.1', '4.1',
                                    '4.1.1')
        and not is_community()
    )


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


def prepare_credentials_tests(cfy, logger, manager):
    manager.use()

    change_salt(manager, 'this_is_a_test_salt', cfy, logger)

    logger.info('Creating test user')
    create_user('testuser', 'testpass', cfy)
    logger.info('Updating admin password')
    update_admin_password(CHANGED_ADMIN_PASSWORD, cfy)
    change_rest_client_password(manager, CHANGED_ADMIN_PASSWORD)


def check_credentials(cfy, logger, manager):
    logger.info('Changing to modified admin credentials')
    change_profile_credentials('admin', CHANGED_ADMIN_PASSWORD, cfy)
    change_rest_client_password(manager, CHANGED_ADMIN_PASSWORD)
    logger.info('Checking test user still works')
    test_user('testuser', 'testpass', cfy, logger, CHANGED_ADMIN_PASSWORD)


def change_rest_client_password(manager, new_password):
    manager.client = create_rest_client(manager.ip_address,
                                        password=new_password)


def create_user(username, password, cfy):
    cfy.users.create(['-r', 'sys_admin', '-p', password, username])


def change_password(username, password, cfy):
    cfy.users(['set-password', '-p', password, username])


def test_user(username, password, cfy, logger, admin_password='admin'):
    logger.info('Checking {user} can log in.'.format(user=username))
    # This command will fail noisily if the credentials don't work
    cfy.profiles.set(['-u', username, '-p', password])

    # Now revert to the admin user
    cfy.profiles.set(['-u', 'admin', '-p', admin_password])


def change_profile_credentials(username, password, cfy):
    cfy.profiles.set(['-u', username, '-p', password])


def update_admin_password(new_password, cfy):
    # Update the admin user on the manager then in our profile
    change_password('admin', new_password, cfy)
    change_profile_credentials('admin', new_password, cfy)


def get_security_conf(manager):
    with manager.ssh() as fabric_ssh:
        output = fabric_ssh.sudo('cat /opt/manager/rest-security.conf')
    # No real error checking here; the old manager shouldn't be able to even
    # start the rest service if this file isn't json.
    return json.loads(output)


def change_salt(manager, new_salt, cfy, logger):
    """Change the salt on the manager so that we don't incorrectly succeed
    while testing non-admin users due to both copies of the master image
    having the same hash salt value."""
    logger.info('Preparting to update salt on {manager}'.format(
        manager=manager.ip_address,
    ))
    security_conf = get_security_conf(manager)

    original_salt = security_conf['hash_salt']
    security_conf['hash_salt'] = new_salt

    logger.info('Applying new salt...')
    with manager.ssh() as fabric_ssh:
        fabric_ssh.sudo(
            "sed -i 's:{original}:{replacement}:' "
            "/opt/manager/rest-security.conf".format(
                original=original_salt,
                replacement=new_salt,
            )
        )

        fabric_ssh.sudo('systemctl restart cloudify-restservice')

    logger.info('Fixing admin credentials...')
    fix_admin_account(manager, new_salt, cfy)

    logger.info('Hash updated.')


def fix_admin_account(manager, salt, cfy):
    new_hash = generate_admin_password_hash('admin', salt)
    new_hash = new_hash.replace('$', '\\$')

    with manager.ssh() as fabric_ssh:
        fabric_ssh.run(
            'sudo -u postgres psql cloudify_db -t -c '
            '"UPDATE users SET password=\'{new_hash}\' '
            'WHERE id=0"'.format(
                new_hash=new_hash,
            ),
            # No really, fabric, just leave the command alone.
            shell_escape=False,
            shell=False,
        )

    # This will confirm that the hash change worked... or it'll fail.
    change_profile_credentials('admin', 'admin', cfy)


def generate_admin_password_hash(admin_password, salt):
    # Flask password hash generation approach for Cloudify 4.x where x<=2
    pwd_hmac = base64.b64encode(
        # Encodes put in to keep hmac happy with unicode strings
        hmac.new(salt.encode('utf-8'), admin_password.encode('utf-8'),
                 hashlib.sha512).digest()
    ).decode('ascii')

    # This ctx is nothing to do with a cloudify ctx.
    pass_ctx = CryptContext(schemes=['pbkdf2_sha256'])
    return pass_ctx.encrypt(pwd_hmac)


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


def hosts(
        request, cfy, ssh_key, module_tmpdir, attributes, logger,
        hello_count, install_dev_tools=True):

    manager_types = [request.param, 'master']
    hello_vms = ['centos' for i in range(hello_count)]
    instances = [
        IMAGES[mgr_type](upload_plugins=False)
        for mgr_type in manager_types + hello_vms
    ]

    hosts = TestHosts(
            cfy, ssh_key, module_tmpdir,
            attributes, logger, instances=instances)
    hosts.create()

    if request.param == '4.0.1':
        with instances[0].ssh() as fabric_ssh:
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
    for manager in instances[:2]:
        with manager.ssh() as fabric_ssh:
            fabric_ssh.sudo('yum -y -q install gcc')
            fabric_ssh.sudo('yum -y -q install python-devel')

    return hosts


def _log(message, logger, tenant=None):
    if tenant:
        message += ' for {tenant}'.format(tenant=tenant)
    logger.info(message)
