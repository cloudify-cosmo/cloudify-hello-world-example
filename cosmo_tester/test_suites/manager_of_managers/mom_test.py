########
# Copyright (c) 2018 Cloudify Platform Ltd. All rights reserved
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

from cosmo_tester.framework import util
from cosmo_tester.framework.test_hosts import TestHosts

from cosmo_tester.test_suites.snapshots import restore_snapshot

from . import constants
from .tier_1_clusters import FloatingIpTier1Cluster, FixedIpTier1Cluster


fixed_ip_clusters = []
floating_ip_clusters = []

tier_2_hosts = None


# Using module scope here, in order to only bootstrap one Tier 2 manager
@pytest.fixture(scope='module')
def tier_2_manager(cfy, ssh_key, module_tmpdir, attributes, logger):
    """
    Creates a Tier 2 Cloudify manager with all the necessary resources on it
    """
    global tier_2_hosts
    tier_2_hosts = TestHosts(
            cfy, ssh_key, module_tmpdir, attributes, logger)
    tier_2_hosts.create()
    manager = tier_2_hosts.instances[0]
    manager.use()
    _upload_resources_to_tier_2_manager(cfy, manager, logger)
    yield manager

    # We don't need to teardown - this is handled by `teardown_module`


def _upload_resources_to_tier_2_manager(cfy, manager, logger):
    cfy.plugins.upload(
        constants.MOM_PLUGIN_WGN_URL,
        '-y', constants.MOM_PLUGIN_YAML_URL
    )
    cfy.plugins.upload(
        constants.OS_PLUGIN_WGN_URL,
        '-y', constants.OS_PLUGIN_YAML_URL
    )

    files_to_download = [
        (util.get_manager_install_rpm_url(), constants.INSTALL_RPM_PATH),
        (constants.HW_OS_PLUGIN_WGN_URL, constants.HW_OS_PLUGIN_WGN_PATH),
        (constants.HW_OS_PLUGIN_YAML_URL, constants.HW_OS_PLUGIN_YAML_PATH),
        (constants.HELLO_WORLD_URL, constants.BLUEPRINT_ZIP_PATH)
    ]
    files_to_create = [
        (constants.SH_SCRIPT, constants.SCRIPT_SH_PATH),
        (constants.PY_SCRIPT, constants.SCRIPT_PY_PATH)
    ]

    logger.info('Downloading necessary files to the Tier 2 manager...')
    for src_url, dst_path in files_to_download:
        manager.run_command(
            'curl -L {0} -o {1}'.format(src_url, dst_path),
            use_sudo=True
        )

    for src_content, dst_path in files_to_create:
        manager.put_remote_file_content(dst_path, src_content, use_sudo=True)

    logger.info('Giving `cfyuser` permissions to downloaded files...')
    for _, dst_path in files_to_download + files_to_create:
        manager.run_command(
            'chown cfyuser:cfyuser {0}'.format(dst_path),
            use_sudo=True
        )
    logger.info('All permissions granted to `cfyuser`')


@pytest.fixture(scope='module')
def floating_ip_2_tier_1_clusters(cfy, tier_2_manager,
                                  attributes, ssh_key, module_tmpdir, logger):
    """ Yield 2 Tier 1 clusters set up with floating IPs """

    global floating_ip_clusters
    if not floating_ip_clusters:
        floating_ip_clusters = _get_tier_1_clusters(
            'cfy_manager_floating_ip',
            2,
            FloatingIpTier1Cluster,
            cfy, logger, module_tmpdir, attributes, ssh_key, tier_2_manager
        )

    yield floating_ip_clusters

    # We don't need to teardown - this is handled by `teardown_module`


@pytest.fixture(scope='module')
def fixed_ip_2_tier_1_clusters(cfy, tier_2_manager,
                               attributes, ssh_key, module_tmpdir, logger):
    """ Yield 2 Tier 1 clusters set up with fixed private IPs """

    global fixed_ip_clusters
    if not fixed_ip_clusters:
        fixed_ip_clusters = _get_tier_1_clusters(
            'cfy_manager_fixed_ip',
            2,
            FixedIpTier1Cluster,
            cfy, logger, module_tmpdir, attributes, ssh_key, tier_2_manager
        )

    yield fixed_ip_clusters

    # We don't need to teardown - this is handled by `teardown_module`


def _get_tier_1_clusters(resource_id, number_of_deps, cluster_class,
                         cfy, logger, tmpdir, attributes, ssh_key,
                         tier_2_manager):
    clusters = []

    for i in range(number_of_deps):
        cluster = cluster_class(
            cfy, tier_2_manager, attributes,
            ssh_key, logger, tmpdir, suffix=resource_id
        )
        cluster.blueprint_id = '{0}_bp'.format(resource_id)
        cluster.deployment_id = '{0}_dep_{1}'.format(resource_id, i)
        cluster.blueprint_file = 'blueprint.yaml'
        clusters.append(cluster)

    return clusters


@pytest.mark.skipif(util.is_redhat(),
                    reason='MoM plugin is only available on Centos')
@pytest.mark.skipif(util.is_community(),
                    reason='Cloudify Community version does '
                           'not support clustering')
def test_tier_1_cluster_staged_upgrade(floating_ip_2_tier_1_clusters):
    """
    In this scenario the second cluster is created _alongside_ the first one
    with different floating IPs
    """
    first_cluster = floating_ip_2_tier_1_clusters[0]
    second_cluster = floating_ip_2_tier_1_clusters[1]

    first_cluster.deploy_and_validate()

    # Install hello world deployment on Tier 1 cluster
    first_cluster.execute_hello_world_workflow('install')

    first_cluster.backup()

    try:
        second_cluster.deploy_and_validate()
    finally:
        # Uninstall hello world deployment from Tier 1 cluster
        second_cluster.execute_hello_world_workflow('uninstall')


@pytest.mark.skipif(util.is_redhat(),
                    reason='MoM plugin is only available on Centos')
@pytest.mark.skipif(util.is_community(),
                    reason='Cloudify Community version does '
                           'not support clustering')
def test_tier_1_cluster_inplace_upgrade(fixed_ip_2_tier_1_clusters):
    """
    In this scenario the second cluster is created _instead_ of the first one
    with the same fixed private IPs
    """
    first_cluster = fixed_ip_2_tier_1_clusters[0]
    second_cluster = fixed_ip_2_tier_1_clusters[1]

    # Note that we can't easily validate that resources were created on the
    # Tier 1 clusters here, because they're using a fixed private IP, which
    # would not be accessible by a REST client from here. This is why we're
    # only testing that the upgrade has succeeded, and that the IPs were the
    # same for both Tier 1 deployments
    first_cluster.deploy_and_validate()

    # Install hello world deployment on Tier 1 cluster
    first_cluster.execute_hello_world_workflow('install')

    first_cluster.backup()
    first_cluster.uninstall()

    try:
        second_cluster.deploy_and_validate()
    finally:
        # Uninstall hello world deployment from Tier 1 cluster
        second_cluster.execute_hello_world_workflow('uninstall')


@pytest.mark.skipif(util.is_redhat(),
                    reason='MoM plugin is only available on Centos')
@pytest.mark.skipif(util.is_community(),
                    reason='Cloudify Community version does '
                           'not support clustering')
def test_tier_2_upgrade(floating_ip_2_tier_1_clusters, tier_2_manager,
                        cfy, tmpdir, logger):
    local_snapshot_path = str(tmpdir / 'snapshot.zip')

    tier_1_cluster = floating_ip_2_tier_1_clusters[0]
    tier_1_cluster.deploy_and_validate()

    cfy.snapshots.create([constants.TIER_2_SNAP_ID])
    tier_2_manager.wait_for_all_executions()
    cfy.snapshots.download(
        [constants.TIER_2_SNAP_ID, '-o', local_snapshot_path]
    )

    tier_2_manager.teardown()
    tier_2_manager.bootstrap()
    tier_2_manager.use()

    _upload_resources_to_tier_2_manager(cfy, tier_2_manager, logger)

    cfy.snapshots.upload([local_snapshot_path, '-s', constants.TIER_2_SNAP_ID])
    restore_snapshot(tier_2_manager, constants.TIER_2_SNAP_ID, cfy, logger,
                     restore_certificates=True)

    cfy.agents.install()

    # This will only work properly if the Tier 2 manager was restored correctly
    tier_1_cluster.uninstall()


def teardown_module():
    """
    First destroy any Tier 1 clusters, then destroy the Tier 2 manager.
    Using `teardown_module` because we want to create only a single instance
    of a Tier 2 manager, as well as the Floating IP Tier 1 cluster, no matter
    whether we run a single test or a whole module.
    """
    if floating_ip_clusters:
        for cluster in floating_ip_clusters:
            cluster.cleanup()

    if tier_2_hosts:
        tier_2_hosts.destroy()
