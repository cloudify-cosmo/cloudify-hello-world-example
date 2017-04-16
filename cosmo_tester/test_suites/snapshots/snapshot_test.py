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

from cosmo_tester.framework.examples.hello_world import HelloWorldExample
from cosmo_tester.framework.cluster import CloudifyCluster


@pytest.fixture(scope='module')
def cluster(
        request, cfy, ssh_key, module_tmpdir, attributes, logger):
    """Creates a cloudify manager from an image in rackspace OpenStack."""
    cluster = CloudifyCluster.create_image_based(
            cfy,
            ssh_key,
            module_tmpdir,
            attributes,
            logger,
            number_of_managers=2)

    manager2 = cluster.managers[1]
    logger.info('Removing all plugins from manager2..')
    plugins = manager2.client.plugins.list()
    for plugin in plugins:
        logger.info('Removing plugin: %s - %s', plugin.package_name, plugin.id)
        manager2.client.plugins.delete(plugin.id)

    yield cluster

    cluster.destroy()


@pytest.fixture(scope='function')
def hello_world(cfy, cluster, attributes, ssh_key, tmpdir, logger):
    hw = HelloWorldExample(
            cfy, cluster.managers[0], attributes, ssh_key, logger, tmpdir)
    hw.blueprint_file = 'openstack-blueprint.yaml'
    hw.inputs.update({
        'agent_user': attributes.centos7_username,
        'image': attributes.centos7_image_name,
    })

    yield hw
    if hw.cleanup_required:
        logger.info('Hello world cleanup required..')
        cluster.managers[0].use()
        hw.cleanup()


@retrying.retry(stop_max_attempt_number=10, wait_fixed=5000)
def _assert_snapshot_created(snapshot_id, client):
    snapshot = client.snapshots.get(snapshot_id)
    assert snapshot.status == 'created', 'Snapshot not in created status'


@retrying.retry(stop_max_attempt_number=6, wait_fixed=5000)
def _assert_restore_workflow_terminated(execution_id, client, logger):
    logger.info('Getting restore workflow execution.. [id=%s]', execution_id)
    execution = client.executions.get(execution_id)
    logger.info('- execution.status = %s', execution.status)
    assert execution.status == 'terminated'


def test_restore_snapshot_and_agents_upgrade(
        cfy, cluster, hello_world, attributes, ssh_key, logger, tmpdir):
    manager1 = cluster.managers[0]
    manager2 = cluster.managers[1]

    manager1.use()
    hello_world.upload_blueprint()
    hello_world.create_deployment()
    hello_world.install()

    snapshot_id = str(uuid.uuid4())

    logger.info('Creating snapshot on manager1..')
    manager1.client.snapshots.create(snapshot_id, True, True)

    _assert_snapshot_created(snapshot_id, manager1.client)
    cfy.snapshots.list()

    snapshot_archive_path = str(tmpdir / 'snapshot.zip')

    logger.info('Downloading snapshot from manager1..')
    manager1.client.snapshots.download(snapshot_id,
                                       snapshot_archive_path)

    manager2.use()
    logger.info('Uploading snapshot to manager2..')
    snapshot = manager2.client.snapshots.upload(snapshot_archive_path,
                                                snapshot_id)
    logger.info('Uploaded snapshot:%s%s',
                os.linesep,
                json.dumps(snapshot, indent=2))

    cfy.snapshots.list()

    logger.info('Restoring snapshot on manager2..')
    restore_execution = manager2.client.snapshots.restore(snapshot_id)
    logger.info('Snapshot restore execution:%s%s',
                os.linesep,
                json.dumps(restore_execution, indent=2))

    cfy.executions.list(['--include-system-workflows'])

    _assert_restore_workflow_terminated(restore_execution.id,
                                        manager2.client,
                                        logger)

    cfy.executions.list(['--include-system-workflows'])

    logger.info('Upgrading agents..')
    cfy.agents.install()

    logger.info('Deleting manager1..')
    manager1.delete()

    logger.info('Uninstalling deployment from manager2..')
    hello_world.manager = manager2
    hello_world.uninstall()
    hello_world.delete_deployment()


def test_3_4_1_to_latest_snapshot_restore():
    pytest.skip('Not implemented!')


def test_3_4_2_to_latest_snapshot_restore():
    pytest.skip('Not implemented!')
