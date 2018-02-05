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

from time import sleep
from os.path import join

from cosmo_tester.framework import util
from cosmo_tester.framework.fixtures import image_based_manager

from cosmo_tester.framework.examples.hello_world import get_hello_worlds

manager = image_based_manager


def test_inplace_upgrade(cfy,
                         manager,
                         attributes,
                         ssh_key,
                         module_tmpdir,
                         logger):
    snapshot_name = 'inplace_upgrade_snapshot'
    snapshot_path = join(str(module_tmpdir), snapshot_name) + '.zip'

    # We can't use the hello_worlds fixture here because this test has
    # multiple managers rather than just one (the hosts vs a single
    # manager).
    hellos = get_hello_worlds(cfy, manager, attributes, ssh_key,
                              module_tmpdir, logger)
    for hello_world in hellos:
        hello_world.upload_and_verify_install()
    cfy.snapshots.create([snapshot_name])
    util.wait_for_all_executions(manager)
    cfy.snapshots.download([snapshot_name, '-o', snapshot_path])
    manager.teardown()
    manager.bootstrap()
    manager.upload_necessary_files()
    cfy.snapshots.upload([snapshot_path, '-s', snapshot_name])
    cfy.snapshots.restore([snapshot_name, '--restore-certificates'])
    util.wait_for_all_executions(manager)
    util.wait_for_manager(manager)

    # we need to give the agents enough time to reconnect to the manager;
    # celery retries with a backoff of up to 32 seconds
    sleep(50)

    for hello_world in hellos:
        cfy.agents.install(['-t', hello_world.tenant])
        hello_world.uninstall()
        hello_world.delete_deployment()
