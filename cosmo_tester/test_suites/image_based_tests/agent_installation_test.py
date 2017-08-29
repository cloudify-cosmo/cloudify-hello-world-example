########
# Copyright (c) 2015 GigaSpaces Technologies Ltd. All rights reserved
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

import os
import time
import uuid

from cloudify import constants
from cloudify.compute import create_multi_mimetype_userdata
from cloudify.mocks import MockCloudifyContext
from cloudify.state import current_ctx
from cloudify_agent.api import defaults
from cloudify_agent.installer import script
from cosmo_tester.framework import util
from cosmo_tester.framework.fixtures import image_based_manager

manager = image_based_manager


EXPECTED_FILE_CONTENT = 'CONTENT'


def test_3_2_agent(cfy, manager, attributes):
    blueprint_path = util.get_resource_path(
            'agent/3-2-agent-blueprint/3-2-agent-mispelled-blprint.yaml')

    blueprint_id = deployment_id = str(uuid.uuid4())

    manager.client.blueprints.upload(blueprint_path, blueprint_id)
    manager.client.deployments.create(
            deployment_id, blueprint_id, inputs={
                'ip_address': manager.ip_address,
                'user': attributes.centos7_username,
                'private_key_path': manager.remote_private_key_path
            }, skip_plugins_validation=True)
    try:
        cfy.executions.start.install(['-d', deployment_id])
    finally:
        cfy.executions.start.uninstall(['-d', deployment_id])


def test_ssh_agent(cfy, manager, attributes):
    blueprint_path = util.get_resource_path(
            'agent/ssh-agent-blueprint/ssh-agent-blueprint.yaml')

    blueprint_id = deployment_id = str(uuid.uuid4())

    manager.client.blueprints.upload(blueprint_path, blueprint_id)
    manager.client.deployments.create(
            deployment_id, blueprint_id, inputs={
                'ip_address': manager.ip_address,
                'user': attributes.centos7_username,
                'private_key_path': manager.remote_private_key_path
            }, skip_plugins_validation=True)
    try:
        cfy.executions.start.install(['-d', deployment_id])
    finally:
        cfy.executions.start.uninstall(['-d', deployment_id])


def _test_agent_alive_after_reboot(cfy, manager, blueprint_name, inputs):

    blueprint_path = util.get_resource_path(blueprint_name)
    value = str(uuid.uuid4())
    inputs['value'] = value
    blueprint_id = deployment_id = str(uuid.uuid4())

    manager.client.blueprints.upload(blueprint_path, blueprint_id)
    manager.client.deployments.create(
            deployment_id,
            blueprint_id,
            inputs=inputs,
            skip_plugins_validation=True)

    cfy.executions.start.install(['-d', deployment_id])
    cfy.executions.start.execute_operation(
            deployment_id=deployment_id,
            parameters={
                'operation': 'cloudify.interfaces.reboot_test.reboot',
                'node_ids': ['host']
            })
    cfy.executions.start.uninstall(['-d', deployment_id])
    app = manager.client.node_instances.list(node_id='application',
                                             deployment_id=deployment_id)[0]
    assert value == app.runtime_properties['value']


def test_ubuntu_agent_alive_after_reboot(cfy, manager, attributes):

    _test_agent_alive_after_reboot(
            cfy,
            manager,
            blueprint_name='agent/reboot-vm-blueprint/'
                           'reboot-unix-vm-blueprint.yaml',
            inputs={
                'image': attributes.ubuntu_14_04_image_name,
                'flavor': attributes.medium_flavor_name,
                'user': attributes.ubuntu_username,
                'network_name': attributes.network_name,
                'private_key_path': manager.remote_private_key_path,
                'keypair_name': attributes.keypair_name
            })


def test_centos_agent_alive_after_reboot(cfy, manager, attributes):

    _test_agent_alive_after_reboot(
            cfy,
            manager,
            blueprint_name='agent/reboot-vm-blueprint/'
                           'reboot-unix-vm-blueprint.yaml',
            inputs={
                'image': attributes.centos7_image_name,
                'flavor': attributes.small_flavor_name,
                'user': attributes.centos7_username,
                'network_name': attributes.network_name,
                'private_key_path': manager.remote_private_key_path,
                'keypair_name': attributes.keypair_name
            })


def test_winrm_agent_alive_after_reboot(cfy, manager, attributes):

    _test_agent_alive_after_reboot(
            cfy,
            manager,
            blueprint_name='agent/reboot-vm-blueprint/'
                           'reboot-winrm-vm-blueprint.yaml',
            inputs={
                'image': attributes.windows_server_2012_image_name,
                'flavor': attributes.medium_flavor_name,
                'user': attributes.windows_server_2012_username,
                'network_name': attributes.network_name,
                'private_key_path': manager.remote_private_key_path,
                'keypair_name': attributes.keypair_name
            })


def test_winrm_agent(cfy, manager, attributes, logger):
    blueprint_path = util.get_resource_path(
            'agent/winrm-agent-blueprint/winrm-agent-blueprint.yaml')
    blueprint_id = deployment_id = str(uuid.uuid4())

    manager.client.blueprints.upload(blueprint_path, blueprint_id)
    manager.client.deployments.create(
            deployment_id, blueprint_id, inputs={
                'image': attributes.windows_server_2012_image_name,
                'flavor': attributes.medium_flavor_name,
                'user': attributes.windows_server_2012_username,
                'network_name': attributes.network_name,
                'private_key_path': manager.remote_private_key_path,
                'keypair_name': attributes.keypair_name
            }, skip_plugins_validation=True)
    try:
        cfy.executions.start.install(['-d', deployment_id])
    finally:
        cfy.executions.start.uninstall(['-d', deployment_id])


# Two different tests for ubuntu/centos
# because of different disable requiretty logic
def test_centos_core_userdata_agent(cfy, manager, attributes):
    _test_linux_userdata_agent(
            cfy,
            manager,
            attributes,
            image=attributes.centos7_image_name,
            flavor=attributes.small_flavor_name,
            user=attributes.centos7_username,
            install_method='init_script')


def test_ubuntu_trusty_userdata_agent(cfy, manager, attributes):
    _test_linux_userdata_agent(
            cfy,
            manager,
            attributes,
            image=attributes.ubuntu_14_04_image_name,
            flavor=attributes.small_flavor_name,
            user=attributes.ubuntu_username,
            install_method='init_script')


def test_ubuntu_trusty_provided_userdata_agent(cfy,
                                               manager,
                                               attributes,
                                               tmpdir,
                                               logger):
    name = 'cloudify_agent'
    user = attributes.ubuntu_username
    install_userdata = _install_script(name=name,
                                       windows=False,
                                       user=user,
                                       manager=manager,
                                       attributes=attributes,
                                       tmpdir=tmpdir,
                                       logger=logger)
    _test_linux_userdata_agent(
            cfy,
            manager,
            attributes,
            image=attributes.ubuntu_14_04_image_name,
            flavor=attributes.small_flavor_name,
            user=user,
            install_method='provided',
            name=name,
            install_userdata=install_userdata)


def test_windows_userdata_agent(cfy,
                                manager,
                                attributes,
                                install_method='init_script',
                                name=None,
                                install_userdata=None):
    user = attributes.windows_server_2012_username
    file_path = 'C:\\Users\\{0}\\test_file'.format(user)
    userdata = '#ps1_sysnative \nSet-Content {1} "{0}"'.format(
            EXPECTED_FILE_CONTENT, file_path)
    if install_userdata:
        userdata = create_multi_mimetype_userdata([userdata,
                                                   install_userdata])
    inputs = {
        'image': attributes.windows_server_2012_image_name,
        'user': user,
        'flavor': attributes.medium_flavor_name,
        'os_family': 'windows',
        'userdata': userdata,
        'file_path': file_path,
        'install_method': install_method,
        'name': name,
        'keypair_name': attributes.keypair_name,
        'private_key_path': manager.remote_private_key_path,
        'network_name': attributes.network_name
    }
    _test_userdata_agent(cfy, manager, inputs)


def test_windows_provided_userdata_agent(cfy,
                                         manager,
                                         attributes,
                                         tmpdir,
                                         logger):
    name = 'cloudify_agent'
    install_userdata = _install_script(
            name=name,
            windows=True,
            user=attributes.windows_server_2012_username,
            manager=manager,
            attributes=attributes,
            tmpdir=tmpdir,
            logger=logger)
    test_windows_userdata_agent(
            cfy,
            manager,
            attributes,
            install_method='provided',
            name=name,
            install_userdata=install_userdata)


def _test_linux_userdata_agent(cfy, manager, attributes, image, flavor, user,
                               install_method, install_userdata=None,
                               name=None):
    file_path = '/tmp/test_file'
    userdata = '#! /bin/bash\necho {0} > {1}\nchmod 777 {1}'.format(
            EXPECTED_FILE_CONTENT, file_path)
    if install_userdata:
        userdata = create_multi_mimetype_userdata([userdata,
                                                   install_userdata])
    inputs = {
        'image': image,
        'user': user,
        'flavor': flavor,
        'os_family': 'linux',
        'userdata': userdata,
        'file_path': file_path,
        'install_method': install_method,
        'name': name,
        'keypair_name': attributes.keypair_name,
        'private_key_path': manager.remote_private_key_path,
        'network_name': attributes.network_name
    }

    _test_userdata_agent(cfy, manager, inputs)


def _test_userdata_agent(cfy, manager, inputs):
    blueprint_id = deployment_id = 'userdata{0}'.format(time.time())
    blueprint_path = util.get_resource_path(
            'agent/userdata-agent-blueprint/userdata-agent-blueprint.yaml')

    manager.client.blueprints.upload(blueprint_path, blueprint_id)
    manager.client.deployments.create(
            deployment_id,
            blueprint_id,
            inputs=inputs,
            skip_plugins_validation=True)

    cfy.executions.start.install(['-d', deployment_id])

    try:
        assert {
            'MY_ENV_VAR': 'MY_ENV_VAR_VALUE',
            'file_content': EXPECTED_FILE_CONTENT
        } == manager.client.deployments.outputs.get(deployment_id).outputs
    finally:
        cfy.executions.start.uninstall(['-d', deployment_id])


def _install_script(name, windows, user, manager, attributes, tmpdir, logger):
    # Download cert from manager in order to include its content
    # in the init_script.
    local_cert_path = str(tmpdir / 'cloudify_internal_cert.pem')
    logger.info('Downloading internal cert from manager: %s -> %s',
                attributes.LOCAL_REST_CERT_FILE,
                local_cert_path)
    with manager.ssh() as fabric:
        fabric.get(attributes.LOCAL_REST_CERT_FILE, local_cert_path)

    env_vars = {
        constants.REST_HOST_KEY: manager.private_ip_address,
        constants.REST_PORT_KEY: str(defaults.INTERNAL_REST_PORT),
        constants.BROKER_SSL_CERT_PATH: local_cert_path,
        constants.LOCAL_REST_CERT_FILE_KEY: local_cert_path,
        constants.MANAGER_FILE_SERVER_URL_KEY:
            'https://{0}:{1}/resources'.format(manager.private_ip_address,
                                               defaults.INTERNAL_REST_PORT),
        constants.MANAGER_FILE_SERVER_ROOT_KEY: str(tmpdir)
    }
    (tmpdir / 'cloudify_agent').mkdir()

    ctx = MockCloudifyContext(
            node_id='node',
            tenant={'name': 'default_tenant'},
            rest_token=manager.client.tokens.get().value,
            properties={'agent_config': {
                'user': user,
                'windows': windows,
                'install_method': 'init_script',
                'rest_host': manager.private_ip_address,
                'broker_ip': manager.private_ip_address,
                'name': name
            }})

    try:
        current_ctx.set(ctx)
        os.environ.update(env_vars)
        script_builder = script._get_script_builder()
        install_script = script_builder.install_script()
    finally:
        for var_name in list(env_vars):
            os.environ.pop(var_name, None)

        current_ctx.clear()

    # Replace the `main` call with an install call - as we only want to
    # install the agent, but not configure/start it
    install_method = 'InstallAgent' if windows else 'install_agent'
    install_script = '\n'.join(install_script.split('\n')[:-1])
    return '{0}\n{1}'.format(install_script, install_method)
