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

import pytest
import requests
import retrying

from cosmo_tester.framework.examples.nodecellar import NodeCellarExample
from cosmo_tester.framework.fixtures import image_based_manager
from cosmo_tester.framework import util

manager = image_based_manager
openstack = util.create_openstack_client()


@pytest.fixture(scope='function')
def nodecellar(cfy, manager, attributes, ssh_key, tmpdir, logger):
    tenant = util.prepare_and_get_test_tenant('nc_autoheal', manager, cfy)
    nc = NodeCellarExample(
            cfy, manager, attributes, ssh_key, logger, tmpdir,
            tenant=tenant, suffix='autoheal')
    nc.blueprint_file = 'openstack-blueprint.yaml'
    yield nc
    nc.cleanup()


def test_nodecellar_auto_healing(cfy, manager, nodecellar, logger):
    nodecellar.clone_example()

    logger.info('Patching nodecellar example with auto healing policy..')
    _modify_blueprint(nodecellar.blueprint_path)

    logger.info('Installing nodecellar..')
    nodecellar.upload_blueprint()
    nodecellar.create_deployment()
    nodecellar.install()
    nodecellar.verify_installation()

    logger.info('Killing nodejs host..')
    outputs = nodecellar.outputs
    _kill_nodejs_host(outputs['nodejs_host_id'], logger)

    # make sure nodecellar is down
    logger.info('Verifying nodecellar is down..')
    with pytest.raises(requests.ConnectionError):
        requests.get('http://{0}:8080'.format(
                outputs['endpoint']['ip_address']))

    try:
        _wait_for_autoheal(manager, nodecellar.deployment_id, logger,
                           nodecellar.tenant)
    finally:
        _get_heal_workflow_events(cfy,
                                  manager,
                                  nodecellar.deployment_id,
                                  logger,
                                  nodecellar.tenant)

    logger.info('Verifying nodecellar is working after auto healing..')
    nodecellar.verify_installation()
    nodecellar.uninstall()
    nodecellar.delete_deployment()


def _get_heal_workflow_events(cfy, manager, deployment_id, logger, tenant):
    logger.info('Getting heal workflow events..')
    with util.set_client_tenant(manager, tenant):
        executions = [
            e for e in manager.client.executions.list(
                deployment_id=deployment_id)
            if e.workflow_id == 'heal'
        ]
    if executions:
        assert len(executions) == 1
        cfy.events.list(['-e', executions[0].id,
                         '--tenant-name', tenant])
    else:
        logger.info('No heal executions found.')


@retrying.retry(stop_max_attempt_number=40, wait_fixed=15000)
def _wait_for_autoheal(manager, deployment_id, logger, tenant):
    logger.info('Waiting for heal workflow to start/complete..')
    with util.set_client_tenant(manager, tenant):
        executions = [
            e for e in manager.client.executions.list(
                deployment_id=deployment_id)
            if e.workflow_id == 'heal'
        ]
    logger.info('Found heal executions:%s%s',
                os.linesep,
                json.dumps(executions, indent=2))
    assert len(executions) == 1
    assert executions[0].status == 'terminated'


def _kill_nodejs_host(server_id, logger):
    logger.info('Deleting server.. [id=%s]', server_id)
    openstack.compute.delete_server(server_id)
    _wait_for_server_to_be_deleted(server_id, logger)


@retrying.retry(stop_max_attempt_number=12, wait_fixed=5000)
def _wait_for_server_to_be_deleted(server_id, logger):
    logger.info('Waiting for server to terminate..')
    servers = [x for x in openstack.compute.servers()
               if x.id == server_id]
    if servers:
        logger.info('- server.status = %s', servers[0].status)
    assert len(servers) == 0
    logger.info('Server terminated!')


def _modify_blueprint(blueprint_path):
    groups = {
        'autohealing_group': {
            'members': ['nodejs_host'],
            'policies': {
                'simple_autoheal_policy': {
                    'type': 'cloudify.policies.types.host_failure',
                    'properties': {
                        'service': ['cpu.total.system']
                    },
                    'triggers': {
                        'auto_heal_trigger': {
                            'type':
                                'cloudify.policies.triggers.execute_workflow',
                            'parameters': {
                                'workflow': 'heal',
                                'workflow_parameters': {
                                    'node_instance_id': {
                                        'get_property': ['SELF', 'node_id']
                                    },
                                    'diagnose_value': {
                                        'get_property': ['SELF', 'diagnose']
                                    },
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    outputs = {
        'nodejs_host_id': {
            'value': {
                'get_attribute': ['nodejs_host', 'external_id']
            }
        }
    }
    with util.YamlPatcher(blueprint_path) as patcher:
        patcher.merge_obj('groups', groups)
        patcher.merge_obj('outputs', outputs)
