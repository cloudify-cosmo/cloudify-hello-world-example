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

import sh
import shutil
import uuid

from path import Path
import pytest
import retrying
import winrm

from cosmo_tester.framework.util import (
    AttributesDict,
    get_cli_package_url,
    get_openstack_server_password,
    get_resource_path,
    sh_bake,
)

WINRM_PORT = 5985


@pytest.fixture(scope='function')
def cli_package_tester(ssh_key, attributes, tmpdir, logger):
    logger.info('Using temp dir: %s', tmpdir)
    tmpdir = Path(tmpdir)

    tf_inputs = get_terraform_inputs(attributes, ssh_key)
    tester = _CliPackageTester(tmpdir, tf_inputs, ssh_key, logger)

    yield tester

    tester.perform_cleanup()


@pytest.fixture(scope='function')
def windows_cli_package_tester(ssh_key, attributes, tmpdir, logger):
    logger.info('Using temp dir: %s', tmpdir)
    tmpdir = Path(tmpdir)

    tf_inputs = get_terraform_inputs(attributes, ssh_key)
    tester = _WindowsCliPackageTester(tmpdir, tf_inputs, ssh_key, logger)

    yield tester

    tester.perform_cleanup()


@pytest.fixture(scope='function')
def osx_cli_package_tester(ssh_key, attributes, tmpdir, logger):
    logger.info('Using temp dir: %s', tmpdir)
    tmpdir = Path(tmpdir)

    tf_inputs = get_terraform_inputs(attributes, ssh_key)
    tester = _OSXCliPackageTester(tmpdir, tf_inputs, ssh_key, logger)

    yield tester

    tester.perform_cleanup()


def test_cli_on_centos_7(cli_package_tester, attributes):
    cli_package_tester.inputs.update({
        'cli_image': attributes.centos_7_image_name,
        'cli_user': attributes.centos_7_username,
        'manager_image': attributes.centos_7_image_name,
        'manager_user': attributes.centos_7_username,
        'cli_package_url': get_cli_package_url('rhel_centos_cli_package_url')
    })
    cli_package_tester.run_test()


def test_cli_on_centos_6(cli_package_tester, attributes):
    cli_package_tester.inputs.update({
        'cli_image': attributes.centos_6_image_name,
        'cli_user': attributes.centos_6_username,
        'manager_image': attributes.centos_7_image_name,
        'manager_user': attributes.centos_7_username,
        'cli_package_url': get_cli_package_url('rhel_centos_cli_package_url')
    })
    cli_package_tester.run_test()


def test_cli_on_ubuntu_14_04(cli_package_tester, attributes):
    cli_package_tester.inputs.update({
        'cli_image': attributes.ubuntu_14_04_image_name,
        'cli_user': attributes.ubuntu_14_04_username,
        'manager_image': attributes.centos_7_image_name,
        'manager_user': attributes.centos_7_username,
        'cli_package_url': get_cli_package_url('debian_cli_package_url')
    })
    cli_package_tester.run_test()


def test_cli_on_windows_2012(windows_cli_package_tester, attributes):
    windows_cli_package_tester.inputs.update({
        'cli_image': attributes.windows_2012_image_name,
        'cli_user': attributes.windows_2012_username,
        'manager_image': attributes.centos_7_image_name,
        'manager_user': attributes.centos_7_username,
        'cli_flavor': attributes.medium_flavor_name,
    })
    windows_cli_package_tester.run_test()


def test_cli_on_rhel_7(cli_package_tester, attributes):
    cli_package_tester.inputs.update({
        'cli_image': attributes.rhel_7_image_name,
        'cli_user': attributes.rhel_7_username,
        'manager_image': attributes.centos_7_image_name,
        'manager_user': attributes.centos_7_username,
        'cli_package_url': get_cli_package_url('rhel_centos_cli_package_url')
    })
    cli_package_tester.run_test()


def test_cli_on_rhel_6(cli_package_tester, attributes):
    cli_package_tester.inputs.update({
        'cli_image': attributes.rhel_6_image_name,
        'cli_user': attributes.rhel_6_username,
        'manager_image': attributes.centos_7_image_name,
        'manager_user': attributes.centos_7_username,
        'cli_package_url': get_cli_package_url('rhel_centos_cli_package_url')
    })
    cli_package_tester.run_test()


def test_cli_on_osx(osx_cli_package_tester, attributes):
    osx_cli_package_tester.inputs.update({
        'manager_image': attributes.centos_7_AMI,
        'manager_flavor': attributes.large_AWS_type,
        'manager_user': attributes.centos_7_username,
        'osx_public_ip': os.environ["MACINCLOUD_HOST"],
        'osx_user': os.environ["MACINCLOUD_USERNAME"],
        'osx_password': os.environ["MACINCLOUD_PASSWORD"],
        'osx_ssh_key': os.environ["MACINCLOUD_SSH_KEY"],
        'cli_package_url': get_cli_package_url('osx_cli_package_url'),
    })
    osx_cli_package_tester.run_test()


class _CliPackageTester(object):

    def __init__(self, tmpdir, inputs, ssh_key, logger):
        self.terraform = sh_bake(sh.terraform)
        self.tmpdir = tmpdir
        self.inputs = inputs
        self.ssh_key = ssh_key
        self.logger = logger
        self.inputs_file = self.tmpdir / 'inputs.json'
        os.mkdir(self.tmpdir / 'scripts')

    def _copy_terraform_files(self):
        shutil.copy(get_resource_path(
                'terraform/openstack-linux-cli-test.tf'),
                self.tmpdir / 'openstack-linux-cli-test.tf')
        shutil.copy(get_resource_path(
                'terraform/scripts/linux-cli-test.sh'),
                self.tmpdir / 'scripts/linux-cli-test.sh')

    def run_test(self):
        self._copy_terraform_files()
        self.write_inputs_file()
        self.logger.info('Testing CLI package..')
        with self.tmpdir:
            self.terraform.apply(['-var-file', self.inputs_file])

    def write_inputs_file(self):
        self.inputs_file.write_text(json.dumps(self.inputs, indent=2))

    def perform_cleanup(self):
        self.logger.info('Performing cleanup..')
        with self.tmpdir:
            self.terraform.destroy(['-var-file', self.inputs_file, '-force'])


class _WindowsCliPackageTester(_CliPackageTester):
    """A separate class for testing Windows CLI package bootstrap.

    Since it is impossible to retrieve a Windows VM password from OpenStack
    using terraform, we first run terraform for creating two VMs: Linux for
    the manager and Windows for CLI.

    Once the Windows machine is up, an OpenStack client is used in order
    to retrieve the VMs password. Then the terraform template is updated
    with the extra resources needed for performing bootstrap (including
    the retrieved password).
    """
    def _copy_terraform_files(self):
        shutil.copy(get_resource_path(
                'terraform/openstack-windows-cli-test.tf'),
                self.tmpdir / 'openstack-windows-cli-test.tf')
        shutil.copy(get_resource_path(
                'terraform/scripts/windows-cli-test.ps1'),
                self.tmpdir / 'scripts/windows-cli-test.ps1')
        shutil.copy(get_resource_path(
                'terraform/scripts/windows-userdata.ps1'),
                    self.tmpdir / 'scripts/windows-userdata.ps1')

    @retrying.retry(stop_max_attempt_number=30, wait_fixed=10000)
    def get_password(self, server_id):
        self.logger.info(
                'Waiting for VM password retrieval.. [server_id=%s]',
                server_id)
        password = get_openstack_server_password(
                server_id, self.ssh_key.private_key_path)
        assert password is not None and len(password) > 0
        return password

    def _run_cmd(self, session, cmd, powershell=True):
        self.logger.info('Running command: %s', cmd)
        if powershell:
            r = session.run_ps(cmd)
        else:
            r = session.run_cmd(cmd)
        self.logger.info('- stdout: %s', r.std_out)
        self.logger.info('- stderr: %s', r.std_err)
        self.logger.info('- status_code: %d', r.status_code)
        assert r.status_code == 0

    def run_test(self):
        super(_WindowsCliPackageTester, self).run_test()
        # At this stage, there are two VMs (Windows & Linux).
        # Retrieve password from OpenStack
        with self.tmpdir:
            outputs = AttributesDict(
                    {k: v['value'] for k, v in json.loads(
                            self.terraform.output(
                                    ['-json']).stdout).items()})
        self.logger.info('CLI server id is: %s', outputs.cli_server_id)
        password = self.get_password(outputs.cli_server_id)
        self.logger.info('VM password: %s', password)
        self.inputs['password'] = password

        url = 'http://{0}:{1}/wsman'.format(outputs.cli_public_ip_address,
                                            WINRM_PORT)
        user = self.inputs['cli_user']
        session = winrm.Session(url, auth=(user, password))

        with open(self.ssh_key.private_key_path, 'r') as f:
            private_key = f.read()

        work_dir = 'C:\\Users\\{0}'.format(user)
        remote_private_key_path = '{0}\\ssh_key.pem'.format(work_dir)
        cli_installer_exe_name = 'cloudify-cli.exe'
        cli_installer_exe_path = '{0}\\{1}'.format(work_dir,
                                                   cli_installer_exe_name)
        bootstrap_inputs_file = '{0}\\inputs.json'.format(work_dir)
        cfy_exe = 'C:\\Cloudify\\embedded\\Scripts\\cfy.exe'
        manager_blueprint_path = 'C:\\Cloudify\\cloudify-manager-blueprints\\simple-manager-blueprint.yaml'  # noqa

        self.logger.info('Uploading private key to Windows VM..')
        self._run_cmd(session, '''
Set-Content "{0}" "{1}"
'''.format(remote_private_key_path, private_key))

        self.logger.info('Downloading CLI package..')
        cli_package_url = get_cli_package_url('windows_cli_package_url')
        self._run_cmd(session, """
$client = New-Object System.Net.WebClient
$url = "{0}"
$file = "{1}"
$client.DownloadFile($url, $file)""".format(
                cli_package_url,
                cli_installer_exe_path))

        self.logger.info('Installing CLI...')
        self.logger.info('Using CLI package: {url}'.format(
            url=cli_package_url,
        ))
        self._run_cmd(session, '''
cd {0}
& .\{1} /SILENT /VERYSILENT /SUPPRESSMSGBOXES /DIR="C:\Cloudify"'''
                      .format(work_dir, cli_installer_exe_name))

        self.logger.info('Creating bootstrap inputs file..')
        bootstrap_inputs = json.dumps({
            'public_ip': outputs.manager_public_ip_address,
            'private_ip': outputs.manager_private_ip_address,
            'ssh_user': self.inputs['manager_user'],
            'ssh_key_filename': remote_private_key_path,
        })
        self._run_cmd(session, '''
Set-Content "{0}" '{1}'
'''.format(bootstrap_inputs_file, bootstrap_inputs))

        self.logger.info('Bootstrapping manager..')
        bootstrap_cmd = '{0} bootstrap {1} -i "{2}" -v --keep-up-on-failure'\
            .format(cfy_exe, manager_blueprint_path, bootstrap_inputs_file)
        self._run_cmd(session, bootstrap_cmd, powershell=False)


class _OSXCliPackageTester(_CliPackageTester):

    def _copy_terraform_files(self):
        shutil.copy(get_resource_path(
            'terraform/aws-osx-cli-test.tf'),
            self.tmpdir / 'aws-osx-cli-test.tf')
        shutil.copy(get_resource_path(
            'terraform/scripts/osx-cli-test.sh'),
            self.tmpdir / 'scripts/osx-cli-test.sh')

    def run_test(self):
        super(_OSXCliPackageTester, self).run_test()


def get_terraform_inputs(attributes, ssh_key):
    tf_inputs = {
        'resource_suffix': str(uuid.uuid4()),
        'public_key_path': ssh_key.public_key_path,
        'private_key_path': ssh_key.private_key_path,
        'cli_flavor': attributes.small_flavor_name,
        'manager_flavor': attributes.large_flavor_name,
    }
    return tf_inputs
