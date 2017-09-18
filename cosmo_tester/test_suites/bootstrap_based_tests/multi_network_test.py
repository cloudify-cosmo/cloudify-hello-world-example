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

import yaml
import pytest

from cosmo_tester.framework.cluster import CloudifyCluster
from cosmo_tester.framework.examples.hello_world import HelloWorldExample
from cosmo_tester.framework.util import (
    is_community,
    prepare_and_get_test_tenant,
)

NETWORK_CONFIG_TEMPLATE = """DEVICE="eth{0}"
BOOTPROTO="static"
ONBOOT="yes"
TYPE="Ethernet"
USERCTL="yes"
PEERDNS="yes"
IPV6INIT="no"
PERSISTENT_DHCLIENT="1"
IPADDR="1{0}.0.0.5"
NETMASK="255.255.255.128"
DEFROUTE="no"
"""


@pytest.fixture(scope='module', params=[3])
def manager(request, cfy, ssh_key, module_tmpdir, attributes, logger):
    """Bootstraps a cloudify manager on a VM in rackspace OpenStack."""
    cluster = CloudifyCluster.create_bootstrap_based(
        cfy, ssh_key, module_tmpdir, attributes, logger,
        tf_template='openstack-multi-network-test.tf.template',
        template_inputs={
            'num_of_networks': request.param,
            'image_name': attributes['centos_7_image_name']
        },
        preconfigure_callback=_preconfigure_callback
    )

    yield cluster.managers[0]

    cluster.destroy()


def _preconfigure_callback(managers):
    # The preconfigure callback populates the networks config prior to the BS
    mgr = managers[0]
    networks = mgr._attributes.networks
    mgr.bs_inputs = {'manager_networks': networks}

    # Configure NICs in order for networking to work properly
    _enable_nics(mgr, networks, mgr._tmpdir, mgr._logger)


def test_multiple_networks(multi_network_hello_worlds, logger):
    logger.info('Testing manager with multiple networks')
    for hello in multi_network_hello_worlds:
        hello.verify_all()


class MultiNetworkHelloWorld(HelloWorldExample):
    def _patch_blueprint(self):
        with open(self.blueprint_path, 'r') as f:
            blueprint_dict = yaml.load(f)

        node_props = blueprint_dict['node_templates']['vm']['properties']
        agent_config = node_props['agent_config']
        agent_config['network'] = {'get_input': 'manager_network_name'}

        inputs = blueprint_dict['inputs']
        inputs['manager_network_name'] = {}

        with open(self.blueprint_path, 'w') as f:
            yaml.dump(blueprint_dict, f)


@pytest.fixture(scope='function')
def multi_network_hello_worlds(cfy, manager, attributes, ssh_key, tmpdir,
                               logger):
    hellos = get_hello_worlds(cfy, manager, attributes, ssh_key, tmpdir,
                              logger)
    yield hellos
    for hello in hellos:
        hello.cleanup()


def get_hello_worlds(cfy, manager, attributes, ssh_key, tmpdir, logger):
    hellos = []

    # Add a MultiNetworkHelloWorld per network we add
    for network_name in attributes.networks:
        if is_community():
            tenant = 'default_tenant'
        else:
            tenant = '{0}_tenant'.format(network_name)
            prepare_and_get_test_tenant(
                '{0}_tenant'.format(network_name), manager, cfy
            )
        hello = MultiNetworkHelloWorld(
            cfy, manager, attributes, ssh_key, logger, tmpdir,
            tenant=tenant, suffix=tenant)
        hello.blueprint_file = 'openstack-blueprint.yaml'
        hello.inputs.update({
            'agent_user': attributes.centos_7_username,
            'image': attributes.centos_7_image_name,
            'manager_network_name': network_name,
            'network_name': attributes.network_names[network_name]
        })
        hellos.append(hello)

    # Add one more hello world, that will run on the `default` network
    hw = HelloWorldExample(cfy, manager, attributes, ssh_key, logger, tmpdir)
    hw.blueprint_file = 'openstack-blueprint.yaml'
    hw.inputs.update({
        'agent_user': attributes.centos_7_username,
        'image': attributes.centos_7_image_name
    })
    hellos.append(hw)

    return hellos


def _enable_nics(manager, networks, tmpdir, logger):
    """ Extra network interfaces need to be manually enabled on the manager """

    logger.info('Adding extra NICs...')
    # Need to do this for each network except 0 (as eth0 is already enabled)
    for i in range(1, len(networks)):
        network_file_path = tmpdir / 'network_cfg_{0}'.format(i)
        # Create and copy the interface config
        network_file_path.write_text(NETWORK_CONFIG_TEMPLATE.format(i))
        with manager.ssh() as fabric_ssh:
            fabric_ssh.put(
                network_file_path,
                '/etc/sysconfig/network-scripts/ifcfg-eth{0}'.format(i),
                use_sudo=True
            )
            # Start the interface
            fabric_ssh.sudo('ifup eth{0}'.format(i))
