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
import json
import pytest
from os.path import join
from copy import deepcopy
from StringIO import StringIO

from cloudify_cli.constants import DEFAULT_TENANT_NAME

from cosmo_tester.framework.test_hosts import (
    BootstrapBasedCloudifyManagers,
    CURRENT_MANAGER,
    VM,
)
from cosmo_tester.framework.examples.hello_world import HelloWorldExample
from cosmo_tester.framework.util import prepare_and_get_test_tenant

from cosmo_tester.test_suites.snapshots import (
    create_snapshot,
    download_snapshot,
    upload_snapshot,
    restore_snapshot,
    upgrade_agents,
    delete_manager
)

NETWORK_2 = 'network_2'


@pytest.fixture(scope='module')
def managers(cfy, ssh_key, module_tmpdir, attributes, logger):
    """Bootstraps 2 cloudify managers on a VM in rackspace OpenStack."""

    hosts = BootstrapBasedCloudifyManagers(
        cfy, ssh_key, module_tmpdir, attributes, logger,
        number_of_instances=2,
        tf_template='openstack-multi-network-test.tf.template',
        template_inputs={
            'num_of_networks': 3,
            'num_of_managers': 2,
            'image_name': attributes.centos_7_image_name
        })
    hosts.preconfigure_callback = _preconfigure_callback

    try:
        hosts.create()
        yield hosts.instances
    finally:
        hosts.destroy()


def _preconfigure_callback(_managers):
    # Calling the param `_managers` to avoid confusion with fixture

    # The preconfigure callback populates the networks config prior to the BS
    for mgr in _managers:
        # Remove one of the networks - it will be added post-bootstrap
        all_networks = deepcopy(mgr.networks)
        all_networks.pop(NETWORK_2)

        mgr.bs_inputs = {'manager_networks': all_networks}

        # Configure NICs in order for networking to work properly
        mgr.enable_nics()


def test_multiple_networks(managers,
                           cfy,
                           multi_network_hello_worlds,
                           logger,
                           tmpdir,
                           attributes):
    logger.info('Testing managers with multiple networks')

    # We should have at least 3 hello world objects. We will verify the first
    # one completely on the first manager.
    # All the other ones will be installed on the first manager,
    # then we'll create a snapshot and restore it on the second manager, and
    # finally, to complete the verification, we'll uninstall the remaining
    # hellos on the new manager

    old_manager = managers[0]
    new_manager = managers[1]
    snapshot_id = 'SNAPSHOT_ID'
    local_snapshot_path = str(tmpdir / 'snap.zip')

    # The first hello is the one that belongs to a network that will be added
    # manually post bootstrap to the new manager
    post_bootstrap_hello = multi_network_hello_worlds.pop(0)
    post_bootstrap_hello.manager = new_manager

    for hello in multi_network_hello_worlds:
        hello.upload_blueprint()
        hello.create_deployment()
        hello.install()
        hello.verify_installation()

    create_snapshot(old_manager, snapshot_id, attributes, logger)
    download_snapshot(old_manager, local_snapshot_path, snapshot_id, logger)
    upload_snapshot(new_manager, local_snapshot_path, snapshot_id, logger)
    restore_snapshot(new_manager, snapshot_id, cfy, logger)

    upgrade_agents(cfy, new_manager, logger)
    delete_manager(old_manager, logger)

    new_manager.use()
    for hello in multi_network_hello_worlds:
        hello.manager = new_manager
        hello.uninstall()
        hello.delete_deployment()

    _add_new_network(new_manager, tmpdir, logger)
    post_bootstrap_hello.verify_all()


def _add_new_network(manager, tmpdir, logger):
    logger.info('Adding network `{0}` to the new manager'.format(NETWORK_2))

    local_metadata_path = str(tmpdir / 'certificate_metadata')
    local_old_metadata_path = str(tmpdir / 'old_certificate_metadata')
    remote_metadata_path = '/etc/cloudify/ssl/certificate_metadata'
    private_ip = manager.private_ip_address

    old_networks = deepcopy(manager.networks)
    new_networks = deepcopy(manager.networks)

    # `network_2` shouldn't be on the manager right now
    old_networks.pop(NETWORK_2)

    # This should add back `network_2` that we removed earlier, in the
    # preconfigure callback
    cert_metadata = {
        'networks': new_networks,
        'internal_rest_host': private_ip
    }
    with open(local_metadata_path, 'w') as f:
        json.dump(cert_metadata, f)

    with manager.ssh() as fabric_ssh:
        logger.info('Validating old `certificate_metadata`...')
        fabric_ssh.get(
            remote_metadata_path, local_old_metadata_path, use_sudo=True
        )
        with open(local_old_metadata_path, 'r') as f:
            old_metadata = yaml.load(f)

        assert old_metadata['networks'] == old_networks

        logger.info('Putting the new `certificate_metadata`...')
        fabric_ssh.put(
            local_metadata_path, remote_metadata_path, use_sudo=True
        )

        ip_setter_path = '/opt/cloudify/manager-ip-setter/'
        restservice_python = '/opt/manager/env/bin/python'
        mgmtworker_python = '/opt/mgmtworker/env/bin/python'
        update_ctx_script = join(ip_setter_path, 'update-provider-context.py')
        certs_script = join(ip_setter_path, 'create-internal-ssl-certs.py')

        logger.info('Updating the provider context...')
        fabric_ssh.sudo('{python} {script} --networks {networks} {ip}'.format(
            python=restservice_python,
            script=update_ctx_script,
            networks=remote_metadata_path,
            ip=private_ip
        ))

        logger.info('Recreating internal certs')
        fabric_ssh.sudo('{python} {script} --metadata {metadata} {ip}'.format(
            python=mgmtworker_python,
            script=certs_script,
            metadata=remote_metadata_path,
            ip=private_ip
        ))

        logger.info('Restarting services...')
        fabric_ssh.sudo('systemctl restart cloudify-rabbitmq')
        fabric_ssh.sudo('systemctl restart nginx')


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
def multi_network_hello_worlds(cfy, managers, attributes, ssh_key, tmpdir,
                               logger):
    # The first manager is the initial one
    manager = managers[0]
    manager.use()
    hellos = []

    # Add a MultiNetworkHelloWorld per management network
    for network_name, network_id in attributes.network_names.iteritems():
        tenant = prepare_and_get_test_tenant(
            '{0}_tenant'.format(network_name), manager, cfy
        )
        hello = MultiNetworkHelloWorld(
            cfy, manager, attributes, ssh_key, logger, tmpdir,
            tenant=tenant, suffix=network_name)
        hello.blueprint_file = 'openstack-blueprint.yaml'
        hello.inputs.update({
            'agent_user': attributes.centos_7_username,
            'image': attributes.centos_7_image_name,
            'manager_network_name': network_name,
            'network_name': network_id
        })

        # Make sure the post_bootstrap network is first
        if network_name == NETWORK_2:
            hellos.insert(0, hello)
        else:
            hellos.append(hello)

    # Add one more hello world, that will run on the `default` network
    # implicitly
    hw = HelloWorldExample(cfy, manager, attributes, ssh_key, logger, tmpdir,
                           tenant=DEFAULT_TENANT_NAME,
                           suffix='default_network')
    hw.blueprint_file = 'openstack-blueprint.yaml'
    hw.inputs.update({
        'agent_user': attributes.centos_7_username,
        'image': attributes.centos_7_image_name
    })
    hellos.append(hw)

    yield hellos
    for hello in hellos:
        hello.cleanup()


class _ProxyTestHosts(BootstrapBasedCloudifyManagers):
    """A BootstrapBasedCloudifyManagers that only bootstraps one manager.

    In the proxy test, we need a bootstrapped manager, and an additional
    host for the proxy. We want both to be created in the same terraform
    call so that they're on the same network, but we only want to bootstrap
    one of the machines - the manager, not the proxy.

    By convention, the first instance is the proxy, and the second instance
    is the manager.
    """
    def _bootstrap_managers(self):
        original_instances = self.instances
        self.instances = [self.instances[1]]
        try:
            return super(_ProxyTestHosts, self)._bootstrap_managers()
        finally:
            self.instances = original_instances


@pytest.fixture(scope='function')
def proxy_hosts(request, cfy, ssh_key, module_tmpdir, attributes, logger):
    # the convention for this test is that the proxy is instances[0] and
    # the manager is instances[1]
    # note that even though we bootstrap, we need to use CURRENT_MANAGER
    # for the manager and not the VM to setup a manager correctly
    instances = [VM(), CURRENT_MANAGER()]
    hosts = _ProxyTestHosts(
        cfy, ssh_key, module_tmpdir, attributes, logger, instances=instances)
    hosts.preconfigure_callback = _proxy_preconfigure_callback
    hosts.create()
    try:
        yield hosts.instances
    finally:
        hosts.destroy()


PROXY_SERVICE_TEMPLATE = """
[Unit]
Description=Proxy for port {port}
Wants=network-online.target
[Service]
User=root
Group=root
ExecStart=/bin/socat TCP-LISTEN:{port},fork TCP:{ip}:{port}
Restart=always
RestartSec=20s
[Install]
WantedBy=multi-user.target
"""


def _proxy_preconfigure_callback(_managers):
    proxy, manager = _managers
    proxy_ip = proxy.private_ip_address
    manager_ip = manager.private_ip_address
    # on the manager, we override the default network ip, so that by default
    # all agents will go through the proxy
    manager.bs_inputs = {'manager_networks': {'default': proxy_ip}}

    # setup the proxy - simple socat services that forward all TCP connections
    # to the manager
    with proxy.ssh() as fabric:
        fabric.sudo('yum install socat -y')
        for port in [5671, 53333]:
            service = 'proxy_{0}'.format(port)
            filename = '/usr/lib/systemd/system/{0}.service'.format(service)
            fabric.put(
                StringIO(PROXY_SERVICE_TEMPLATE.format(
                    ip=manager_ip, port=port)),
                filename, use_sudo=True)
            fabric.sudo('systemctl enable {0}'.format(service))
            fabric.sudo('systemctl start {0}'.format(service))


@pytest.fixture(scope='function')
def proxy_helloworld(cfy, proxy_hosts, attributes, ssh_key, tmpdir, logger):
    # don't use MultiNetworkTestHosts - we're testing with the default
    # network, so no need to set manager network name
    hw = HelloWorldExample(
        cfy, proxy_hosts[1], attributes, ssh_key, logger, tmpdir)
    hw.blueprint_file = 'openstack-blueprint.yaml'
    hw.inputs.update({
        'agent_user': attributes.centos_7_username,
        'image': attributes.centos_7_image_name,
    })

    yield hw
    if hw.cleanup_required:
        logger.info('Hello world cleanup required..')
        hw.cleanup()


def test_agent_via_proxy(cfy, proxy_hosts, proxy_helloworld, tmpdir, logger):
    proxy, manager = proxy_hosts

    # to make sure that the agents go through the proxy, and not connect to
    # the manager directly, we block all communication on the manager's
    # rabbitmq and internal REST endpoint, except from the proxy (and from
    # localhost)
    manager_ip = manager.private_ip_address
    proxy_ip = proxy.private_ip_address
    with manager.ssh() as fabric:
        for port in [5671, 53333]:
            fabric.sudo(
                'iptables -I INPUT -p tcp -s 0.0.0.0/0 --dport {0} -j DROP'
                .format(port))
            for ip in [proxy_ip, manager_ip, '127.0.0.1']:
                fabric.sudo(
                    'iptables -I INPUT -p tcp -s {0} --dport {1} -j ACCEPT'
                    .format(ip, port))

    manager.use()
    proxy_helloworld.verify_all()
