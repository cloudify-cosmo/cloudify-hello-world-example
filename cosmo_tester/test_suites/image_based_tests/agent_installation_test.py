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

from cloudify import constants
from cloudify.compute import create_multi_mimetype_userdata
from cloudify.mocks import MockCloudifyContext
from cloudify.state import current_ctx
from cloudify_agent.api import defaults
from cloudify_agent.installer import script
from cosmo_tester.framework import util
from cosmo_tester.framework.fixtures import image_based_manager
from cosmo_tester.framework.util import (
    set_client_tenant,
    prepare_and_get_test_tenant,
)

manager = image_based_manager


EXPECTED_FILE_CONTENT = 'CONTENT'


def test_3_2_agent(cfy, manager, attributes):
    _test_agent('a3_2', cfy, manager, attributes)


def test_ssh_agent(cfy, manager, attributes):
    _test_agent('ssh', cfy, manager, attributes)


def test_ubuntu_14_04_agent_reboot(cfy, manager, attributes):
    _test_agent_alive_after_reboot(cfy, manager, attributes, 'ubuntu_14_04',
                                   suffix='ubuntu_14_04_reboot')


def test_centos_7_agent_reboot(cfy, manager, attributes):
    _test_agent_alive_after_reboot(cfy, manager, attributes, 'centos_7',
                                   suffix='centos_7_reboot')


def test_winrm_agent_alive_after_reboot(cfy, manager, attributes):

    _test_agent_alive_after_reboot(cfy, manager, attributes, 'windows_2012',
                                   suffix='windows_2012_reboot')


# Two different tests for ubuntu/centos
# because of different disable requiretty logic
def test_centos_7_userdata_agent(cfy, manager, attributes):
    os_name = 'centos_7'
    tenant = prepare_and_get_test_tenant(
        'userdata_{}'.format(os_name),
        manager,
        cfy,
    )
    _test_linux_userdata_agent(
        cfy,
        manager,
        attributes,
        os_name=os_name,
        tenant=tenant,
    )


def test_ubuntu_trusty_userdata_agent(cfy, manager, attributes):
    os_name = 'ubuntu_14_04'
    tenant = prepare_and_get_test_tenant(
        'userdata_{}'.format(os_name),
        manager,
        cfy,
    )
    _test_linux_userdata_agent(
        cfy,
        manager,
        attributes,
        os_name=os_name,
        tenant=tenant,
    )


def test_ubuntu_trusty_provided_userdata_agent(cfy,
                                               manager,
                                               attributes,
                                               tmpdir,
                                               logger):
    name = 'cloudify_agent'
    os_name = 'ubuntu_14_04'
    tenant = prepare_and_get_test_tenant(
        'userdataprov_{}'.format(os_name),
        manager,
        cfy,
    )
    install_userdata = _install_script(
        name=name,
        windows=False,
        user=attributes.ubuntu_14_04_username,
        manager=manager,
        attributes=attributes,
        tmpdir=tmpdir,
        logger=logger,
        tenant=tenant,
    )
    _test_linux_userdata_agent(
        cfy,
        manager,
        attributes,
        os_name,
        install_method='provided',
        name=name,
        install_userdata=install_userdata,
        tenant=tenant,
    )


def test_windows_provided_userdata_agent(cfy,
                                         manager,
                                         attributes,
                                         tmpdir,
                                         logger):
    name = 'cloudify_agent'
    tenant = prepare_and_get_test_tenant(
        'userdataprov_windows_2012',
        manager,
        cfy,
    )
    install_userdata = _install_script(
        name=name,
        windows=True,
        user=attributes.windows_2012_username,
        manager=manager,
        attributes=attributes,
        tmpdir=tmpdir,
        logger=logger,
        tenant=tenant,
    )
    test_windows_userdata_agent(
        cfy,
        manager,
        attributes,
        install_method='provided',
        name=name,
        install_userdata=install_userdata,
        tenant=tenant,
    )


def test_windows_userdata_agent(cfy,
                                manager,
                                attributes,
                                install_method='init_script',
                                name=None,
                                install_userdata=None,
                                os_name='windows_2012',
                                tenant=None):
    user = attributes.windows_2012_username
    file_path = 'C:\\Users\\{0}\\test_file'.format(user)
    userdata = '#ps1_sysnative\n' \
               'Set-Content {1} "{0}"'.format(EXPECTED_FILE_CONTENT, file_path)
    if install_userdata:
        userdata = create_multi_mimetype_userdata([userdata,
                                                   install_userdata])
        if not tenant:
            tenant = prepare_and_get_test_tenant(
                'inst_userdata_{}'.format(os_name),
                manager,
                cfy,
            )
    else:
        if not tenant:
            tenant = prepare_and_get_test_tenant(
                'userdata_{}'.format(os_name),
                manager,
                cfy,
            )

    inputs = {
        'image': attributes.windows_2012_image_name,
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
    _test_userdata_agent(cfy, manager, inputs, tenant)


def test_windows_with_service_user_winrm(
        cfy,
        manager,
        attributes,
        os_name='windows_2012',
        tenant=None):
    _test_windows_with_service_user(
        cfy, manager, attributes, 'remote', os_name, tenant,
        'winrm_service_user')


def test_windows_with_service_user_init_script(
        cfy,
        manager,
        attributes,
        os_name='windows_2012',
        tenant=None):
    _test_windows_with_service_user(
        cfy, manager, attributes, 'init_script', os_name, tenant,
        'initscript_service_user')


def _test_windows_with_service_user(
        cfy,
        manager,
        attributes,
        install_method,
        os_name,
        tenant,
        deployment_id_prefix):
    _test_windows_common(
        cfy, manager, attributes,
        'agent/windows-service-user-blueprint/blueprint.yaml',
        {
            'service_user': '.\\testuser',
            'service_password': 'syvcASdn3a$q1',
            'install_method': install_method
        },
        os_name, tenant, deployment_id_prefix)


def test_windows_winrm(
        cfy,
        manager,
        attributes,
        os_name='windows_2012',
        tenant=None):
    _test_windows_common(
        cfy, manager, attributes,
        'agent/winrm-agent-blueprint/winrm-agent-blueprint.yaml',
        None,
        os_name, tenant, 'winrm')


def _test_windows_common(
        cfy,
        manager,
        attributes,
        blueprint_path,
        inputs,
        os_name,
        tenant,
        deployment_id_prefix):
    user = attributes.windows_2012_username
    if not tenant:
        tenant = prepare_and_get_test_tenant(
            '{0}_{1}'.format(deployment_id_prefix, os_name),
            manager,
            cfy
        )

    effective_inputs = {
        'image': attributes.windows_2012_image_name,
        'flavor': attributes.medium_flavor_name,
        'user': user,
        'network_name': attributes.network_name,
        'private_key_path': manager.remote_private_key_path,
        'keypair_name': attributes.keypair_name,
    }

    if inputs:
        effective_inputs.update(inputs)

    blueprint_id = deployment_id = '{0}_{1}'.format(
        deployment_id_prefix, time.time())
    blueprint_path = util.get_resource_path(blueprint_path)

    with set_client_tenant(manager, tenant):
        manager.client.blueprints.upload(blueprint_path, blueprint_id)
        manager.client.deployments.create(
            deployment_id,
            blueprint_id,
            inputs=effective_inputs,
            skip_plugins_validation=True)

    cfy.executions.start.install(['-d', deployment_id,
                                  '--tenant-name', tenant])

    try:
        cfy.executions.start.execute_operation(
            deployment_id=deployment_id,
            parameters={
                'operation': 'test.interface.test',
                'node_ids': ['test_app']
            },
            tenant_name=tenant)
    finally:
        cfy.executions.start.uninstall(['-d', deployment_id,
                                        '--tenant-name', tenant])


def _test_agent(agent_type, cfy, manager, attributes):
    agent_blueprints = {
        'a3_2': 'agent/3-2-agent-blueprint/3-2-agent-mispelled-blprint.yaml',
        'ssh': 'agent/ssh-agent-blueprint/ssh-agent-blueprint.yaml',
    }

    blueprint_path = util.get_resource_path(agent_blueprints[agent_type])

    tenant = prepare_and_get_test_tenant(
        'agent_{}'.format(agent_type),
        manager,
        cfy,
    )
    blueprint_id = deployment_id = agent_type

    with set_client_tenant(manager, tenant):
        manager.client.blueprints.upload(blueprint_path, blueprint_id)
        manager.client.deployments.create(
            deployment_id, blueprint_id, inputs={
                'ip_address': manager.ip_address,
                'user': attributes.default_linux_username,
                'private_key_path': manager.remote_private_key_path
            }, skip_plugins_validation=True)
    try:
        cfy.executions.start.install(['-d', deployment_id,
                                      '--tenant-name', tenant])
    finally:
        cfy.executions.start.uninstall(['-d', deployment_id,
                                        '--tenant-name', tenant])


def _test_agent_alive_after_reboot(cfy, manager, attributes, os_name,
                                   suffix=None):
    suffix = suffix or os_name
    os_blueprints = {
        'centos_7': 'agent/reboot-vm-blueprint/reboot-unix-vm-blueprint.yaml',
        'ubuntu_14_04': (
            'agent/reboot-vm-blueprint/reboot-unix-vm-blueprint.yaml'
        ),
        'windows_2012': (
            'agent/reboot-vm-blueprint/reboot-winrm-vm-blueprint.yaml'
        ),
    }
    blueprint_name = os_blueprints[os_name]

    tenant = prepare_and_get_test_tenant(suffix, manager, cfy)

    inputs = {
        'image': attributes['{os}_image_name'.format(os=os_name)],
        'flavor': attributes['medium_flavor_name'],
        'user': attributes['{os}_username'.format(os=os_name)],
        'network_name': attributes['network_name'],
        'private_key_path': manager.remote_private_key_path,
        'keypair_name': attributes['keypair_name'],
    }

    blueprint_path = util.get_resource_path(blueprint_name)
    inputs['value'] = os_name
    blueprint_id = deployment_id = os_name

    with set_client_tenant(manager, tenant):
        manager.client.blueprints.upload(blueprint_path, blueprint_id)
        manager.client.deployments.create(
            deployment_id,
            blueprint_id,
            inputs=inputs,
            skip_plugins_validation=True)

    try:
        cfy.executions.start.install(['-d', deployment_id,
                                      '--tenant-name', tenant])
        cfy.executions.start.execute_operation(
            deployment_id=deployment_id,
            parameters={
                'operation': 'cloudify.interfaces.reboot_test.reboot',
                'node_ids': ['host']
            },
            tenant_name=tenant)
    finally:
        cfy.executions.start.uninstall(['-d', deployment_id,
                                        '--tenant-name', tenant])
    with set_client_tenant(manager, tenant):
        app = manager.client.node_instances.list(
            node_id='application',
            deployment_id=deployment_id,
        )[0]
    assert os_name == app.runtime_properties['value']


def _test_linux_userdata_agent(cfy, manager, attributes, os_name, tenant,
                               install_userdata=None, name=None,
                               install_method='init_script'):
    file_path = '/tmp/test_file'
    userdata = '#! /bin/bash\necho {0} > {1}\nchmod 777 {1}'.format(
        EXPECTED_FILE_CONTENT, file_path)
    if install_userdata:
        userdata = create_multi_mimetype_userdata([userdata,
                                                   install_userdata])

    inputs = {
        'image': attributes['{os}_image_name'.format(os=os_name)],
        'user': attributes['{os}_username'.format(os=os_name)],
        'flavor': attributes['small_flavor_name'],
        'os_family': 'linux',
        'userdata': userdata,
        'file_path': file_path,
        'install_method': install_method,
        'name': name,
        'keypair_name': attributes.keypair_name,
        'private_key_path': manager.remote_private_key_path,
        'network_name': attributes.network_name
    }

    _test_userdata_agent(cfy, manager, inputs, tenant)


def _test_userdata_agent(cfy, manager, inputs, tenant):
    blueprint_id = deployment_id = 'userdata{0}'.format(time.time())
    blueprint_path = util.get_resource_path(
        'agent/userdata-agent-blueprint/userdata-agent-blueprint.yaml')

    with set_client_tenant(manager, tenant):
        manager.client.blueprints.upload(blueprint_path, blueprint_id)
        manager.client.deployments.create(
            deployment_id,
            blueprint_id,
            inputs=inputs,
            skip_plugins_validation=True)

    cfy.executions.start.install(['-d', deployment_id,
                                  '--tenant-name', tenant])

    try:
        with set_client_tenant(manager, tenant):
            assert {
                'MY_ENV_VAR': 'MY_ENV_VAR_VALUE',
                'file_content': EXPECTED_FILE_CONTENT
            } == manager.client.deployments.outputs.get(deployment_id).outputs
    finally:
        cfy.executions.start.uninstall(['-d', deployment_id,
                                        '--tenant-name', tenant])


def _install_script(name, windows, user, manager, attributes, tmpdir, logger,
                    tenant):
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
        constants.MANAGER_FILE_SERVER_URL_KEY: (
            'https://{0}:{1}/resources'.format(manager.private_ip_address,
                                               defaults.INTERNAL_REST_PORT)
        ),
        constants.MANAGER_FILE_SERVER_ROOT_KEY: str(tmpdir),
    }
    (tmpdir / 'cloudify_agent').mkdir()

    ctx = MockCloudifyContext(
        node_id='node',
        tenant={'name': tenant},
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
