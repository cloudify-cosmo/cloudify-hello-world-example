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
from cosmo_tester.framework.fixtures import bootstrap_based_manager
from cosmo_tester.framework.util import is_community
from cloudify_rest_client.client import CloudifyClient
from os.path import join

manager = bootstrap_based_manager
DEFAULT_TENANT_ROLE = 'user'


def test_ssl(cfy, manager, module_tmpdir, attributes, ssh_key, logger):
    cert_path = join(module_tmpdir, '.cloudify', 'profiles',
                     manager.ip_address, 'public_rest_cert.crt')
    cfy.profiles.set('-c', cert_path)

    assert 'SSL disabled' in cfy.ssl.status()
    current_profile = cfy.profiles.show()
    assert ' 80 ' in current_profile
    assert ' http ' in current_profile

    cfy.ssl.enable()
    cfy.profiles.set('--ssl', 'on', '--skip-credentials-validation')
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
    assert 'SSL disabled' in cfy.ssl.status()

    current_profile = cfy.profiles.show()
    assert ' 80 ' in current_profile
    assert ' http ' in current_profile

    manager.client = _manager_client
    hello_world.uninstall()
    hello_world.delete_deployment()
