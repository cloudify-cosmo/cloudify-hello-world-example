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

from cosmo_tester.framework.examples.hello_world import centos_hello_world
from cosmo_tester.framework.fixtures import image_based_manager
from cosmo_tester.framework.util import is_community
from cloudify_rest_client.client import CloudifyClient
from os.path import join
import time

manager = image_based_manager
DEFAULT_TENANT_ROLE = 'user'
REMOTE_EXTERNAL_CERT_PATH = '/etc/cloudify/ssl/cloudify_external_cert.pem'


def test_ssl(cfy, manager, module_tmpdir, attributes, ssh_key, logger):
    cert_path = join(module_tmpdir, '.cloudify', 'profiles',
                     manager.ip_address, 'public_rest_cert.crt')
    _generate_external_cert(manager, logger)
    _download_external_cert(manager, logger, local_cert_path=cert_path)

    cfy.profiles.set('-c', cert_path)

    assert 'SSL disabled' in cfy.ssl.status()
    current_profile = cfy.profiles.show()
    assert ' 80 ' in current_profile
    assert ' http ' in current_profile

    cfy.ssl.enable()
    cfy.profiles.set('--ssl', 'on', '--skip-credentials-validation')
    time.sleep(5)
    assert 'SSL enabled' in cfy.ssl.status()

    current_profile = cfy.profiles.show()
    assert ' 443 ' in current_profile
    assert ' https ' in current_profile

    _manager_client = manager.client
    ssl_client = CloudifyClient(username='admin',
                                password='admin',
                                host=manager.ip_address,
                                tenant='default_tenant',
                                protocol='https',
                                cert=cert_path)
    manager.client = ssl_client

    if not is_community():
        tenant_name = 'ssl_tenant'
        cfy.users.create('ssl_user', '-p', 'ssl_pass')
        cfy.tenants.create(tenant_name)

        cfy.tenants('add-user',
                    'ssl_user',
                    '-t',
                    tenant_name,
                    '-r',
                    DEFAULT_TENANT_ROLE)

    hello_world = centos_hello_world(cfy, manager, attributes, ssh_key,
                                     logger, module_tmpdir)

    hello_world.upload_and_verify_install()

    cfy.ssl.disable()
    cfy.profiles.set('--ssl', 'off', '--skip-credentials-validation')
    time.sleep(5)
    assert 'SSL disabled' in cfy.ssl.status()

    current_profile = cfy.profiles.show()
    assert ' 80 ' in current_profile
    assert ' http ' in current_profile

    manager.client = _manager_client
    hello_world.uninstall()
    hello_world.delete_deployment()


def _generate_external_cert(_manager, logger):
    with _manager.ssh() as fabric_ssh:
        # This is necessary when using an image-based manager
        logger.info('Generating new external cert...')
        fabric_ssh.sudo(
            'cfy_manager create-external-certs '
            '--private-ip {0} --public-ip {1}'.format(
                _manager.private_ip_address,
                _manager.ip_address
            )
        )


def _download_external_cert(_manager, logger, local_cert_path):
    with _manager.ssh() as fabric_ssh:
        logger.info('Downloading external cert from the manager...')
        fabric_ssh.get(
            REMOTE_EXTERNAL_CERT_PATH, local_cert_path, use_sudo=True
        )
