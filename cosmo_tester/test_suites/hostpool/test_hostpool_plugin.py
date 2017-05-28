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

import uuid
import pytest
import requests

from cosmo_tester.framework.examples import AbstractExample
from cosmo_tester.framework.fixtures import image_based_manager
from cosmo_tester.framework.examples.nodecellar import NodeCellarExample
from cosmo_tester.framework import util


manager = image_based_manager


UBUNTU_HOST = 'ubuntu_host_template'
CENTOS_HOST = 'centos_host_template'
WINDOWS_HOST = 'windows_host_template'
HOST_TEMPLATES = [WINDOWS_HOST, CENTOS_HOST, UBUNTU_HOST]


class HostPoolExample(AbstractExample):
    REPOSITORY_URL = 'https://github.com/cloudify-cosmo/cloudify-host-pool-plugin.git'  # noqa
    _inputs = None

    @property
    def inputs(self):
        if self._inputs is None:
            attributes = self.attributes
            self._inputs = {
                'centos_image_id': attributes.centos7_image_name,
                'windows_image_id': attributes.windows_server_2012_image_name,
                'ubuntu_image_id': attributes.ubuntu_14_04_image_name,
                'flavor_id': attributes.medium_flavor_name,
                'floating_network_id': attributes.floating_network_id,
                'network_name': attributes.network_name,
                'key_pair_name': attributes.keypair_name,
                'private_key_path': self.manager.remote_private_key_path,
                # key_path is where the hostpool service host will store the
                # key to the hosts; it is not the same as the agent key
                'key_path': '/tmp/' + str(uuid.uuid4()),
            }
        return self._inputs

    def verify_installation(self):
        """Check that 3 hosts are added to the pool, but not used. Then,
        scale up, and check that another host has been added.
        """
        super(HostPoolExample, self).verify_installation()
        hosts = self.get_hosts()
        self.assertEqual(len(HOST_TEMPLATES), len(hosts))
        for host in hosts:
            self.assert_host_state(host, allocated=False)
        self._scale(UBUNTU_HOST)
        hosts = self.get_hosts()
        self.assertEqual(len(HOST_TEMPLATES) + 1, len(hosts))

    def get_hosts(self):
        """Hosts added to the pool"""
        endpoint_url = self.get_endpoint_url()
        response = requests.get('{0}/hosts'.format(endpoint_url))
        return response.json()

    def get_endpoint_url(self):
        """Address of the hostpool service API"""
        return 'http://{0}:{1}'.format(
            self.outputs['endpoint']['ip_address'],
            self.outputs['endpoint']['port']
        )

    def assert_host_state(self, host, allocated=False):
        self.assertEqual(host.get('allocated'), allocated)

    def _scale(self, node_id, delta=+1):
        parameters = ('delta={0};scalable_entity_name={1}'
                      .format(delta, node_id))
        self.cfy.executions.start('scale', deployment_id=self.deployment_id,
                                  parameters=parameters)


class HostpoolNodeCellarExample(NodeCellarExample):
    def __init__(self, hostpool, *args, **kwargs):
        super(HostpoolNodeCellarExample, self).__init__(*args, **kwargs)
        self._hostpool = hostpool

    @property
    def inputs(self):
        if self._inputs is None:
            self._inputs = {
                'host_pool_service_endpoint': self._hostpool.get_endpoint_url()
            }
        return self._inputs

    def verify_installation(self):
        super(HostpoolNodeCellarExample, self).verify_installation()
        # after installation, the ubuntu hosts were used for the nodecellar
        # app, but other hosts are still free
        for host in self._hostpool.get_hosts():
            if UBUNTU_HOST in host.get('name'):
                self._hostpool.assert_host_state(host, allocated=True)
            else:
                self._hostpool.assert_host_state(host, allocated=False)

    def verify_all(self):
        super(HostpoolNodeCellarExample, self).verify_all()
        # after uninstalling - which is done at the end of parent class'
        # verify_all - all the hosts are free again
        for host in self._hostpool.get_hosts():
            self._hostpool.assert_host_state(host, allocated=False)

    def assert_nodecellar_working(self, endpoint):
        # unfortunately, we can't access the nodecellar app directly,
        # because
        # 1) the nodecellar hostpool blueprint isn't an _openstack_
        #    blueprint, so doesn't export the ip correctly in outputs;
        # 2) the nodecellar nodejs host doesn't even have a floating ip
        #    assigned
        # 3) the hostpool service blueprint doesn't know about nodecellar,
        #    so the security group doesn't allow connections on the nodecellar
        #    port
        # Instead, we will figure out the host ip from runtime properties
        # (to overcome 1), ssh to the manager (to help 2), and from the
        # manager, ssh to the nodejs host, where we will simply curl
        # localhost (3)

        port = endpoint['port']
        nodejs_node = self.manager.client.node_instances.list(
            node_name='nodejs_host')[0]
        cloudify_agent = nodejs_node.runtime_properties['cloudify_agent']
        ssh_command = ('ssh -o StrictHostKeyChecking=no {user}@{ip} -i {key} '
                       '"curl -I localhost:{port}"'
                       .format(user=cloudify_agent['user'],
                               ip=nodejs_node.runtime_properties['ip'],
                               key=cloudify_agent['key'],
                               port=port))
        with self.manager.ssh() as fabric:
            response = fabric.sudo(ssh_command)
        self.assertIn('200 OK', response)


@pytest.fixture(scope='function')
def hostpool(cfy, manager, attributes, ssh_key, logger, tmpdir):
    hp = HostPoolExample(cfy, manager, attributes, ssh_key, logger, tmpdir)
    hp.blueprint_file = util.get_resource_path('hostpool/service-blueprint.yaml')  # noqa
    hp.skip_plugins_validation = True

    # verification is unrolled here because we want to validate and yield
    # the service for further testing before uninstalling it
    hp.upload_blueprint()
    hp.create_deployment()
    hp.install()
    hp.verify_installation()
    yield hp
    hp.uninstall()
    hp.delete_deployment()
    hp.cleanup()


@pytest.fixture(scope='function')
def nodecellar_hostpool(hostpool, cfy, manager, attributes, ssh_key, tmpdir,
                        logger):
    nc = HostpoolNodeCellarExample(
        hostpool, cfy, manager, attributes, ssh_key, logger, tmpdir)
    nc.blueprint_file = 'host-pool-blueprint.yaml'
    nc.skip_plugins_validation = True
    return nc


def test_nodecellar_hostpool(nodecellar_hostpool):
    nodecellar_hostpool.verify_all()
