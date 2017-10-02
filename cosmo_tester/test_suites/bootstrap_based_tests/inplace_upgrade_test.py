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

import pytest

from time import sleep
from os.path import join

from cosmo_tester.framework.test_hosts import BootstrapBasedCloudifyManagers

from . import get_hello_worlds


@pytest.fixture(scope='module')
def hosts(request, cfy, ssh_key, module_tmpdir, attributes, logger):
    """Bootstraps a cloudify manager on a VM in rackspace OpenStack."""
    # need to keep the hosts to use its inputs in the second bootstrap
    hosts = BootstrapBasedCloudifyManagers(
            cfy, ssh_key, module_tmpdir, attributes, logger)
    try:
        hosts.create()
        yield hosts
    finally:
        hosts.destroy()


def test_inplace_upgrade(cfy,
                         hosts,
                         attributes,
                         ssh_key,
                         module_tmpdir,
                         logger):
    manager = hosts.instances[0]
    snapshot_name = 'inplace_upgrade_snapshot'
    snapshot_path = join(str(module_tmpdir), snapshot_name) + '.zip'

    # We can't use the hello_worlds fixture here because this test has
    # multiple managers rather than just one (the hosts vs a single
    # manager).
    hellos = get_hello_worlds(cfy, manager, attributes, ssh_key,
                              module_tmpdir, logger)
    for hello_world in hellos:
        hello_world.upload_blueprint()
        hello_world.create_deployment()
        hello_world.install()
        hello_world.verify_installation()
    cfy.snapshots.create([snapshot_name])
    # wait for snapshot creation to terminate
    _wait_for_func(func=_check_executions,
                   manager=manager,
                   message='Timed out: An execution did not terminate',
                   retries=60,
                   interval=1)
    cfy.snapshots.download([snapshot_name, '-o', snapshot_path])
    cfy.teardown(['-f', '--ignore-deployments'])
    hosts._bootstrap_manager(hosts._create_inputs_file(manager))
    openstack_config_file = hosts.create_openstack_config_file()
    manager._upload_necessary_files(openstack_config_file)
    cfy.snapshots.upload([snapshot_path, '-s', snapshot_name])
    cfy.snapshots.restore([snapshot_name, '--restore-certificates'])
    _wait_for_restore(manager)
    for hello_world in hellos:
        cfy.agents.install(['-t', hello_world.tenant])
        hello_world.uninstall()
        hello_world.delete_deployment()


def _check_executions(manager):
    try:
        executions = manager.client.executions.list(
            include_system_workflows=True).items
        for execution in executions:
            if execution['status'] != 'terminated':
                return False
        return True
    except BaseException:
        return False


def _check_status(manager):
    try:
        status = manager.client.manager.get_status()
        for service in status['services']:
            for instance in service['instances']:
                if instance['state'] != 'running':
                    return False
        return True
    except BaseException:
        return False


def _wait_for_func(func, manager, message, retries, interval):
    for i in range(retries):
        if func(manager):
            return
        sleep(interval)
    raise Exception(message)


def _wait_for_restore(manager, sleep_time=5):
    _wait_for_func(func=_check_executions,
                   manager=manager,
                   message='Timed out: An execution did not terminate',
                   retries=180,
                   interval=1)
    sleep(sleep_time)
    _wait_for_func(func=_check_status,
                   manager=manager,
                   message='Timed out: Reboot did not complete successfully',
                   retries=60,
                   interval=1)
