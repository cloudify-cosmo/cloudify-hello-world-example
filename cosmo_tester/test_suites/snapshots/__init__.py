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

from uuid import uuid4
from retrying import retry

# CFY-6912
from cloudify_cli.commands.executions import (
    _get_deployment_environment_creation_execution,
    )
from cloudify_cli.constants import CLOUDIFY_TENANT_HEADER


HELLO_WORLD_URL = 'https://github.com/cloudify-cosmo/cloudify-hello-world-example/archive/4.0.zip'  # noqa

blueprint_id = deployment_id = str(uuid4())


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


@retry(
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


def _get_helloworld_inputs(attributes, manager):
    return {
        'floating_network_id': attributes.floating_network_id,
        'key_pair_name': attributes.keypair_name,
        'private_key_path': manager.remote_private_key_path,
        'flavor': attributes.small_flavor_name,
        'network_name': attributes.network_name,
        'agent_user': attributes.centos7_username,
        'image': attributes.centos7_image_name
    }


def update_client_tenant(client, tenant_name):
    client._client.headers[CLOUDIFY_TENANT_HEADER] = tenant_name


def deploy_helloworld(attributes, logger, manager):
    logger.info('Uploading helloworld blueprint to {version} manager..'.format(
        version=manager.branch_name))
    inputs = _get_helloworld_inputs(attributes, manager)
    manager.client.blueprints.publish_archive(
        HELLO_WORLD_URL,
        blueprint_id,
        'openstack-blueprint.yaml',
        )

    logger.info('Deploying helloworld on {version} manager..'.format(
        version=manager.branch_name))
    manager.client.deployments.create(
        blueprint_id,
        deployment_id,
        inputs,
        )

    creation_execution = _get_deployment_environment_creation_execution(
        manager.client, deployment_id)
    logger.info('waiting for execution environment')
    wait_for_execution(
        manager.client,
        creation_execution,
        logger,
        )

    manager.client.deployments.list()

    execution = manager.client.executions.start(
        deployment_id,
        'install',
        )
    logger.info('waiting for installation to finish')
    wait_for_execution(
        manager.client,
        execution,
        logger,
        )
