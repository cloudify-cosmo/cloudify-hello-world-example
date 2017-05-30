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

import json
import os
import uuid

import pytest
import retrying

from cosmo_tester.framework.cluster import (
    CloudifyCluster,
    MANAGERS,
)
from cosmo_tester.framework.util import (
    create_rest_client,
    assert_snapshot_created,
)

# CFY-6912
from cloudify_cli.commands.executions import (
    _get_deployment_environment_creation_execution,
    )


HELLO_WORLD_URL = 'https://github.com/cloudify-cosmo/cloudify-hello-world-example/archive/4.0.zip'  # noqa


@pytest.fixture(
        scope='module',
        params=['master', '4.0.1', '4.0', '3.4.2'])
def cluster(request, cfy, ssh_key, module_tmpdir, attributes, logger):
    managers = (
        MANAGERS[request.param](),
        MANAGERS['master'](upload_plugins=False),
    )

    cluster = CloudifyCluster.create_image_based(
            cfy,
            ssh_key,
            module_tmpdir,
            attributes,
            logger,
            managers=managers,
            )

    if request.param.startswith('3'):
        # Install dev tools & python headers
        with cluster.managers[1].ssh() as fabric_ssh:
            fabric_ssh.sudo('yum -y groupinstall "Development Tools"')
            fabric_ssh.sudo('yum -y install python-devel')

    yield cluster

    cluster.destroy()


@pytest.fixture(autouse=True)
def _hello_world_example(cluster, attributes, logger, tmpdir):
    _deploy_helloworld(attributes, logger, cluster.managers[0], tmpdir)

    yield

    manager1 = cluster.managers[0]
    if not manager1.deleted:
        try:
            logger.info('Cleaning up hello_world_example deployment...')
            execution = manager1.client.executions.start(
                deployment_id,
                'uninstall',
                parameters=(
                    None
                    if manager1.branch_name.startswith('3')
                    else {'ignore_failure': True}
                ),
                )
            wait_for_execution(
                manager1.client,
                execution,
                logger,
                )
        except Exception as e:
            logger.error('Error on test cleanup: %s', e)


blueprint_id = deployment_id = str(uuid.uuid4())


def test_restore_snapshot_and_agents_upgrade(
        cfy, cluster, attributes, logger, tmpdir):
    manager1 = cluster.managers[0]
    manager2 = cluster.managers[1]

    snapshot_id = str(uuid.uuid4())

    logger.info('Creating snapshot on manager1..')
    manager1.client.snapshots.create(snapshot_id, False, False, False)
    assert_snapshot_created(manager1, snapshot_id, attributes)

    local_snapshot_path = str(tmpdir / 'snapshot.zip')

    logger.info('Downloading snapshot from old manager..')
    manager1.client.snapshots.list()
    manager1.client.snapshots.download(snapshot_id, local_snapshot_path)

    manager2.use()
    logger.info('Uploading snapshot to latest manager..')
    snapshot = manager2.client.snapshots.upload(local_snapshot_path,
                                                snapshot_id)
    logger.info('Uploaded snapshot:%s%s',
                os.linesep,
                json.dumps(snapshot, indent=2))

    cfy.snapshots.list()

    logger.info('Restoring snapshot on latest manager..')
    restore_execution = manager2.client.snapshots.restore(
        snapshot_id,
        tenant_name=manager1.restore_tenant_name,
        )
    logger.info('Snapshot restore execution:%s%s',
                os.linesep,
                json.dumps(restore_execution, indent=2))

    cfy.executions.list(['--include-system-workflows'])

    restore_execution = wait_for_execution(
        manager2.client,
        restore_execution,
        logger)
    assert restore_execution.status == 'terminated'

    cfy.executions.list(['--include-system-workflows'])

    manager2.use(tenant=manager1.restore_tenant_name)
    client = create_rest_client(
        manager2.ip_address,
        username=cluster._attributes.cloudify_username,
        password=cluster._attributes.cloudify_password,
        tenant=manager1.tenant_name,
        api_version=manager2.api_version,
        )

    cfy.deployments.list()
    deployments = client.deployments.list()
    assert 1 == len(deployments)

    logger.info('Upgrading agents..')
    cfy.agents.install()

    logger.info('Deleting original {version} manager..'.format(
        version=manager1.branch_name))
    manager1.delete()

    logger.info('Uninstalling deployment from latest manager..')
    cfy.executions.start.uninstall(['-d', deployment_id])
    cfy.deployments.delete(deployment_id)


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
def wait_for_execution(client, execution, logger):
    logger.info('Getting workflow execution.. [id=%s]', execution['id'])
    execution = client.executions.get(execution['id'])
    logger.info('- execution.status = %s', execution.status)
    if execution.status not in execution.END_STATES:
        raise ExecutionWaiting(execution.status)
    if execution.status != execution.TERMINATED:
        raise ExecutionFailed(execution.status)
    return execution


def _deploy_helloworld(attributes, logger, manager1, tmpdir):
    logger.info('Uploading helloworld blueprint to {version} manager..'.format(
        version=manager1.branch_name))
    inputs = {
        'floating_network_id': attributes.floating_network_id,
        'key_pair_name': attributes.keypair_name,
        'private_key_path': manager1.remote_private_key_path,
        'flavor': attributes.small_flavor_name,
        'network_name': attributes.network_name,
        'agent_user': attributes.centos7_username,
        'image': attributes.centos7_image_name
    }
    manager1.client.blueprints.publish_archive(
        HELLO_WORLD_URL,
        blueprint_id,
        'openstack-blueprint.yaml',
        )

    logger.info('Deploying helloworld on {version} manager..'.format(
        version=manager1.branch_name))
    manager1.client.deployments.create(
        blueprint_id,
        deployment_id,
        inputs,
        )

    creation_execution = _get_deployment_environment_creation_execution(
        manager1.client, deployment_id)
    logger.info('waiting for execution environment')
    wait_for_execution(
        manager1.client,
        creation_execution,
        logger,
        )

    manager1.client.deployments.list()

    execution = manager1.client.executions.start(
        deployment_id,
        'install',
        )
    logger.info('waiting for installation to finish')
    wait_for_execution(
        manager1.client,
        execution,
        logger,
        )
