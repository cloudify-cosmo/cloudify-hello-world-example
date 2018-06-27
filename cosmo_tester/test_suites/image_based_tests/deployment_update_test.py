########
# Copyright (c) 2016 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.

import json
import uuid
import shutil

import pytest
import requests

from path import Path
from retrying import retry

from cosmo_tester.framework import util
from cosmo_tester.framework.fixtures import image_based_manager
from cosmo_tester.framework.examples.hello_world import centos_hello_world
from cosmo_tester.framework.util import (prepare_and_get_test_tenant,
                                         set_client_tenant)


update_counter = 0
manager = image_based_manager


@pytest.fixture(scope='function')
def hello_world(cfy, manager, attributes, ssh_key, tmpdir, logger):
    tenant = prepare_and_get_test_tenant('dep_update', manager, cfy)
    hw = centos_hello_world(cfy,
                            manager,
                            attributes,
                            ssh_key,
                            logger,
                            tmpdir,
                            tenant=tenant,
                            suffix='update')
    yield hw
    hw.cleanup()


def test_hello_world_deployment_update(cfy,
                                       manager,
                                       hello_world,
                                       tmpdir,
                                       logger):
    logger.info('Deploying hello world example..')
    hello_world.upload_and_verify_install()
    http_endpoint = hello_world.outputs['http_endpoint']
    modified_port = '9090'

    # Update the deployment - shutdown the http_web_server, and the
    # security_group node. Remove the relationship between the vm
    # and the security_group node. Remove the output - since no new outputs
    # have been outputted, the check will be based on the old outputs.
    blueprint_base_path = hello_world.blueprint_path.dirname()

    # Remove the .git folder because its permissions mess up the upload
    shutil.rmtree(blueprint_base_path / '.git')

    modified_blueprint_path = blueprint_base_path / 'modified_blueprint.yaml'
    hello_world.blueprint_path.copy(modified_blueprint_path)
    _modify_blueprint(modified_blueprint_path)

    logger.info('Updating hello world deployment..')
    _update_deployment(cfy,
                       manager,
                       hello_world.deployment_id,
                       hello_world.tenant,
                       modified_blueprint_path,
                       tmpdir,
                       skip_reinstall=True)

    # Verify hello world is not responding
    logger.info('Verifying hello world is down..')
    try:
        requests.get(http_endpoint)
        pytest.fail('Hello world is responsive after deployment update but '
                    'should be down!')
    except requests.exceptions.RequestException:
        pass

    # Startup the initial blueprint (with 9090 as port)
    logger.info('Updating hello world deployment to use a different port..')
    _update_deployment(cfy,
                       manager,
                       hello_world.deployment_id,
                       hello_world.tenant,
                       hello_world.blueprint_path,
                       tmpdir,
                       inputs={'webserver_port': modified_port})
    logger.info('Verifying hello world updated deployment..')
    hello_world.verify_installation()


def _wait_for_deployment_update_to_finish(func):
    def _update_and_wait_to_finish(cfy,
                                   manager,
                                   deployment_id,
                                   tenant,
                                   *args,
                                   **kwargs):
        func(cfy, manager, deployment_id, tenant, *args, **kwargs)

        @retry(stop_max_attempt_number=10,
               wait_fixed=5000,
               retry_on_result=lambda r: not r)
        def repetitive_check():
            with set_client_tenant(manager, tenant):
                dep_updates_list = manager.client.deployment_updates.list(
                        deployment_id=deployment_id)
                executions_list = manager.client.executions.list(
                        deployment_id=deployment_id,
                        workflow_id='update',
                        _include=['status']
                )
            if len(dep_updates_list) != update_counter:
                return False
            for deployment_update in dep_updates_list:
                if deployment_update.state not in ['failed', 'successful']:
                    return False
            for execution in executions_list:
                if execution['status'] not in ['terminated',
                                               'failed',
                                               'cancelled']:
                    return False
            return True
        repetitive_check()
    return _update_and_wait_to_finish


@_wait_for_deployment_update_to_finish
def _update_deployment(cfy,
                       manager,
                       deployment_id,
                       tenant,
                       blueprint_path,
                       tmpdir,
                       skip_reinstall=False,
                       inputs=None):
    if inputs:
        inputs_file = Path(tmpdir) / 'deployment_update_inputs.json'
        inputs_file.write_text(json.dumps(inputs))
        kwargs = {'inputs': inputs_file.abspath()}
    else:
        kwargs = {}
    global update_counter
    update_counter += 1
    cfy.deployments.update(deployment_id,
                           blueprint_id='b-{0}'.format(uuid.uuid4()),
                           blueprint_path=blueprint_path,
                           tenant_name=tenant,
                           skip_reinstall=skip_reinstall,
                           **kwargs)


def _modify_blueprint(blueprint_path):
    with util.YamlPatcher(blueprint_path) as patcher:
        # Remove security group
        patcher.delete_property('node_templates.security_group')
        # Remove the webserver node
        patcher.delete_property('node_templates.http_web_server')
        # Remove the output
        patcher.delete_property('outputs', 'http_endpoint')
        # Remove vm to security_group relationships
        blueprint = util.get_yaml_as_dict(blueprint_path)
        vm_relationships = blueprint['node_templates']['vm'][
            'relationships']
        vm_relationships = [r for r in vm_relationships if r['target'] !=
                            'security_group']
        patcher.set_value('node_templates.vm.relationships', vm_relationships)
        # Remove vm interfaces - this is needed because it contains
        # a get_attribute with a reference to the deleted security group node.
        patcher.delete_property('node_templates.vm.interfaces')
