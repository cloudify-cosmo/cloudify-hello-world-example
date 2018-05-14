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

# import pytest

from cosmo_tester.framework.fixtures import image_based_manager

manager = image_based_manager
STAGE_E2E_SELENIUM_HOST = '10.239.0.203'


def test_ui(cfy, manager, module_tmpdir, attributes, ssh_key, logger):

    # Example of using fabric_ssh

    # with manager.ssh() as fabric_ssh:
    #     logger.info('Validating old `certificate_metadata`...')
    #     fabric_ssh.get(
    #         remote_metadata_path, local_old_metadata_path, use_sudo=True
    #     )
    #     with open(local_old_metadata_path, 'r') as f:
    #         old_metadata = yaml.load(f)
    #
    #     assert old_metadata['networks'] == old_networks
    #
    #     logger.info('Putting the new `certificate_metadata`...')
    #     fabric_ssh.put(
    #         local_metadata_path, remote_metadata_path, use_sudo=True
    #     )
    #
    #     ip_setter_path = '/opt/cloudify/manager-ip-setter/'
    #     restservice_python = '/opt/manager/env/bin/python'
    #     update_ctx_script = join(ip_setter_path,
    #                       'update-provider-context.py')
    #
    #     logger.info('Updating the provider context...')
    #     fabric_ssh.sudo('{python} {script} --networks {networks} {ip}'.
    #         format(
    #         python=restservice_python,
    #         script=update_ctx_script,
    #         networks=remote_metadata_path,
    #         ip=private_ip
    #     ))
    #
    #     logger.info('Recreating internal certs')
    #     fabric_ssh.sudo(
    #         '{cfy_manager} create-internal-certs '
    #         '--metadata {metadata} '
    #         '--manager-ip {ip}'
    #             .format(
    #             cfy_manager='/usr/bin/cfy_manager',
    #             metadata=remote_metadata_path,
    #             ip=private_ip
    #         )
    #     )
    pass
