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

from abc import ABCMeta, abstractproperty

import json
import os
import uuid
import yaml
from urllib import urlretrieve
from contextlib import contextmanager
from distutils.version import LooseVersion

import jinja2
import retrying
import sh
from fabric import api as fabric_api
from fabric import context_managers as fabric_context_managers
from influxdb import InfluxDBClient

from cosmo_tester.framework import util

from cloudify_cli.constants import DEFAULT_TENANT_NAME


REMOTE_PRIVATE_KEY_PATH = '/etc/cloudify/key.pem'
REMOTE_OPENSTACK_CONFIG_PATH = '/etc/cloudify/openstack_config.json'

RSYNC_SCRIPT_URL = 'https://raw.githubusercontent.com/cloudify-cosmo/cloudify-dev/master/scripts/rsync.sh'  # NOQA

MANAGER_API_VERSIONS = {
    'master': 'v3',
    '4.1': 'v3',
    '4.0.1': 'v3',
    '4.0': 'v3',
    '3.4.2': 'v2',
}


ATTRIBUTES = util.get_attributes()


class VM(object):

    __metaclass__ = ABCMeta

    def __init__(self, upload_plugins=False):
        """Mainly here for compatibility with other VM types"""
        self.upload_plugins = upload_plugins

    def create(
            self,
            index,
            public_ip_address,
            private_ip_address,
            networks,
            rest_client,
            ssh_key,
            cfy,
            attributes,
            logger,
            tmpdir,
            ):
        self.index = index
        self.ip_address = public_ip_address
        self.private_ip_address = private_ip_address
        self.client = rest_client
        self.deleted = False
        self._ssh_key = ssh_key
        self._cfy = cfy
        self._attributes = attributes
        self._logger = logger
        self._openstack = util.create_openstack_client()
        self._tmpdir = os.path.join(tmpdir, str(index))

    @contextmanager
    def ssh(self, **kwargs):
        with fabric_context_managers.settings(
                host_string=self.ip_address,
                user=self._attributes.centos_7_username,
                key_filename=self._ssh_key.private_key_path,
                abort_exception=Exception,
                **kwargs):
            yield fabric_api

    def __str__(self):
        return 'Cloudify Test VM ({image}) [{index}:{ip}]'.format(
                image=self.image_name,
                index=self.index,
                ip=self.ip_address,
                )

    @property
    def server_id(self):
        """Returns this server's Id from the terraform outputs."""
        key = 'server_id_{}'.format(self.index)
        return self._attributes[key]

    def delete(self):
        """Deletes this instance from the OpenStack envrionment."""
        self._logger.info('Deleting server.. [id=%s]', self.server_id)
        self._openstack.compute.delete_server(self.server_id)
        self._wait_for_server_to_be_deleted()
        self.deleted = True

    @retrying.retry(stop_max_attempt_number=12, wait_fixed=5000)
    def _wait_for_server_to_be_deleted(self):
        self._logger.info('Waiting for server to terminate..')
        servers = [x for x in self._openstack.compute.servers()
                   if x.id == self.server_id]
        if servers:
            self._logger.info('- server.status = %s', servers[0].status)
        assert len(servers) == 0
        self._logger.info('Server terminated!')

    def verify_services_are_running(self):
        return True

    def use(self, tenant=None):
        return True

    def upload_plugin(self, plugin_name):
        return True

    def upload_necessary_files(self):
        return True

    image_name = ATTRIBUTES['centos_7_image_name']
    branch_name = 'master'


class _CloudifyManager(VM):

    def __init__(self, upload_plugins=True):
        self.upload_plugins = upload_plugins

    def create(
            self,
            index,
            public_ip_address,
            private_ip_address,
            networks,
            rest_client,
            ssh_key,
            cfy,
            attributes,
            logger,
            tmpdir
            ):
        self.index = index
        self.ip_address = public_ip_address
        self.private_ip_address = private_ip_address
        self.client = rest_client
        self.deleted = False
        self.networks = networks
        self._ssh_key = ssh_key
        self._cfy = cfy
        self._attributes = attributes
        self._logger = logger
        self._rsync_path = None
        self._tmpdir = os.path.join(tmpdir, str(uuid.uuid4()))
        os.makedirs(self._tmpdir)
        self._openstack = util.create_openstack_client()
        self.influxdb_client = InfluxDBClient(public_ip_address, 8086,
                                              'root', 'root', 'cloudify')
        self.additional_install_config = {}

    def upload_necessary_files(self):
        self._logger.info('Uploading necessary files to %s', self)
        openstack_config_file = self._create_openstack_config_file()
        with self.ssh() as fabric_ssh:
            openstack_json_path = REMOTE_OPENSTACK_CONFIG_PATH
            fabric_ssh.sudo('mkdir -p "{}"'.format(
                os.path.dirname(REMOTE_PRIVATE_KEY_PATH)))
            fabric_ssh.put(openstack_config_file,
                           openstack_json_path,
                           use_sudo=True)
            fabric_ssh.put(self._ssh_key.private_key_path,
                           REMOTE_PRIVATE_KEY_PATH,
                           use_sudo=True)
            fabric_ssh.sudo('chown root:cfyuser {key_file}'.format(
                key_file=REMOTE_PRIVATE_KEY_PATH,
            ))
            fabric_ssh.sudo('chmod 440 {key_file}'.format(
                key_file=REMOTE_PRIVATE_KEY_PATH,
            ))

    def upload_plugin(self, plugin_name, tenant_name=DEFAULT_TENANT_NAME):
        all_plugins = util.get_plugin_wagon_urls()
        plugin = [p for p in all_plugins if p['name'] == plugin_name]
        if len(plugin) != 1:
            self._logger.error(
                '%s plugin wagon not found in:%s%s',
                plugin_name,
                os.linesep,
                json.dumps(all_plugins, indent=2))
            raise RuntimeError(
                '{} plugin not found in wagons list'.format(plugin_name))
        self._logger.info('Uploading %s plugin [%s] to %s..',
                          plugin_name,
                          plugin[0]['wgn_url'],
                          self)

        # versions newer than 4.2 support passing yaml files
        yaml_snippet = ''
        if LooseVersion(self.branch_name) > LooseVersion('4.2'):
            yaml_snippet = '--yaml-path {0}'.format(
                plugin[0]['plugin_yaml_url'])
        try:
            with self.ssh() as fabric_ssh:
                # This will only work for images as cfy is pre-installed there.

                # from some reason this method is usually less error prone.
                fabric_ssh.run(
                    'cfy plugins upload {0} -t {1} {2}'.format(
                        plugin[0], tenant_name, yaml_snippet
                    ))
        except Exception:
            try:
                self.use()
                self._cfy.plugins.upload([plugin[0], '-t', tenant_name])
            except Exception:
                # This is needed for 3.4 managers. local cfy isn't
                # compatible and cfy isn't installed in the image
                self.client.plugins.upload(plugin[0])

    @property
    def remote_private_key_path(self):
        """Returns the private key path on the manager."""
        return REMOTE_PRIVATE_KEY_PATH

    def __str__(self):
        return 'Cloudify manager [{}:{}]'.format(self.index, self.ip_address)

    @retrying.retry(stop_max_attempt_number=3, wait_fixed=3000)
    def use(self, tenant=None, profile_name=None):
        kwargs = {}
        if profile_name is not None:
            kwargs['profile_name'] = profile_name
        self._cfy.profiles.use([
            self.ip_address,
            '-u', self._attributes.cloudify_username,
            '-p', self._attributes.cloudify_password,
            '-t', tenant or self._attributes.cloudify_tenant,
            ], **kwargs)

    @property
    def server_id(self):
        """Returns this server's Id from the terraform outputs."""
        key = 'server_id_{}'.format(self.index)
        return self._attributes[key]

    @retrying.retry(stop_max_attempt_number=6*10, wait_fixed=10000)
    def verify_services_are_running(self):
        with self.ssh() as fabric_ssh:
            # the manager-ip-setter script creates the `touched` file when it
            # is done.
            try:
                # will fail on bootstrap based managers
                fabric_ssh.run('systemctl | grep manager-ip-setter')
            except Exception:
                pass
            else:
                self._logger.info('Verify manager-ip-setter is done..')
                fabric_ssh.run('cat /opt/cloudify/manager-ip-setter/touched')

        self._logger.info('Verifying all services are running on manager%d..',
                          self.index)
        status = self.client.manager.get_status()
        for service in status['services']:
            for instance in service['instances']:
                if (
                    instance['Id'] == 'cloudify-stage.service'
                    and not util.is_community()
                ):
                    assert instance['SubState'] == 'running', \
                        'service {0} is in {1} state'.format(
                                service['display_name'], instance['SubState'])

    @abstractproperty
    def branch_name(Self):
        raise NotImplementedError()

    @property
    def image_name(self):
        return ATTRIBUTES['cloudify_manager_{}_image_name'.format(
                self.branch_name.replace('.', '_'))]

    @property
    def api_version(self):
        return MANAGER_API_VERSIONS[self.branch_name]

    @property
    def rsync_path(self):
        if not self._rsync_path:
            self._rsync_path = os.path.join(self._tmpdir, 'rsync.sh')
            urlretrieve(RSYNC_SCRIPT_URL, self._rsync_path)
            os.chmod(self._rsync_path, 0o755)  # Make the script executable

        return self._rsync_path

    # passed to cfy. To be overridden in pre-4.0 versions
    restore_tenant_name = None
    tenant_name = 'default_tenant'

    def stop_for_user_input(self):
        """
        Print out a helpful ssh command to allow the user to connect to the
        current manager, and then wait for user input to continue the test
        """
        self._logger.info('#' * 80)
        self._logger.info(
            '\nssh -o StrictHostKeyChecking=no {user}@{ip} -i {key}'.format(
                user=self._attributes.centos_7_username,
                ip=self.ip_address,
                key=self._ssh_key.private_key_path)
        )
        raw_input('You can now connect to the manager')

    def sync_local_code_to_manager(self):
        self._logger.info('Syncing local code to the manager')
        cmd = ' '.join([
            self.rsync_path,
            self.ip_address,
            self._attributes.centos_7_username,
            self._ssh_key.private_key_path
        ])
        self._logger.info('Running command:\n{0}'.format(cmd))
        os.system(cmd)

    def teardown(self):
        with self.ssh() as fabric_ssh:
            fabric_ssh.run('cfy_manager remove --force')
            fabric_ssh.sudo('yum remove -y cloudify-manager-install')

    def _create_config_file(self):
        config_file = self._tmpdir / 'config_{0}.yaml'.format(self.index)
        install_config = {
            'manager':
                {
                    'public_ip': str(self.ip_address),
                    'private_ip': str(self.private_ip_address),
                    'security': {
                        'admin_username': self._attributes.cloudify_username,
                        'admin_password': self._attributes.cloudify_password,
                    }
                }
        }

        # Add any additional bootstrap inputs passed from the test
        install_config.update(self.additional_install_config)
        install_config_str = yaml.dump(install_config)

        self._logger.info(
            'Install config:\n{0}'.format(install_config_str))
        config_file.write_text(install_config_str)
        return config_file

    def bootstrap(self):
        manager_install_rpm = util.get_manager_install_rpm_url()
        install_config = self._create_config_file()
        install_rpm_file = 'cloudify-manager-install.rpm'
        with self.ssh() as fabric_ssh:
            fabric_ssh.run(
                'curl -sS {0} -o {1}'.format(
                    manager_install_rpm,
                    install_rpm_file
                )
            )
            fabric_ssh.sudo('yum install -y {0}'.format(install_rpm_file))
            fabric_ssh.put(
                install_config,
                '/etc/cloudify/config.yaml'
            )
            fabric_ssh.run('cfy_manager install')
        self.use()

    def _create_openstack_config_file(self):
        openstack_config_file = self._tmpdir / 'openstack_config.json'
        openstack_config_file.write_text(json.dumps({
            'username': os.environ['OS_USERNAME'],
            'password': os.environ['OS_PASSWORD'],
            'tenant_name': os.environ.get('OS_TENANT_NAME',
                                          os.environ['OS_PROJECT_NAME']),
            'auth_url': os.environ['OS_AUTH_URL']
        }, indent=2))
        return openstack_config_file


def get_latest_manager_image_name():
    """
    Returns the manager image name based on installed CLI version.
    For CLI version "4.0.0-m15"
    Returns: "cloudify-manager-premium-4.0m15"
    """
    specific_manager_name = ATTRIBUTES.cloudify_manager_latest_image.strip()

    if specific_manager_name:
        image_name = specific_manager_name
    else:
        version = util.get_cli_version()
        version_num, _, version_milestone = version.partition('-')

        if version_num.endswith('.0') and version_num.count('.') > 1:
            version_num = version_num[:-2]

        version = version_num + version_milestone
        image_name = '{prefix}-{suffix}'.format(
            prefix=ATTRIBUTES.cloudify_manager_image_name_prefix,
            suffix=version,
        )

    return image_name


class Cloudify3_4Manager(_CloudifyManager):
    branch_name = '3.4.2'
    tenant_name = restore_tenant_name = 'restore_tenant'

    def upload_necessary_files(self):
        self._logger.info('Uploading necessary files to %s', self)
        openstack_config_file = self._create_openstack_config_file()
        with self.ssh() as fabric_ssh:
            openstack_json_path = '/root/openstack_config.json'
            fabric_ssh.put(openstack_config_file,
                           openstack_json_path,
                           use_sudo=True)
            fabric_ssh.sudo('mkdir -p "{}"'.format(
                os.path.dirname(REMOTE_PRIVATE_KEY_PATH)))
            fabric_ssh.put(self._ssh_key.private_key_path,
                           REMOTE_PRIVATE_KEY_PATH,
                           use_sudo=True)
            fabric_ssh.sudo('chmod 440 {key_file}'.format(
                key_file=REMOTE_PRIVATE_KEY_PATH,
            ))


class Cloudify4_0Manager(_CloudifyManager):
    branch_name = '4.0'

    def upload_necessary_files(self):
        self._logger.info('Uploading necessary files to %s', self)
        openstack_config_file = self._create_openstack_config_file()
        with self.ssh() as fabric_ssh:
            openstack_json_path = '/root/openstack_config.json'
            fabric_ssh.put(openstack_config_file,
                           openstack_json_path,
                           use_sudo=True)
            fabric_ssh.sudo('mkdir -p "{}"'.format(
                os.path.dirname(REMOTE_PRIVATE_KEY_PATH)))
            fabric_ssh.put(self._ssh_key.private_key_path,
                           REMOTE_PRIVATE_KEY_PATH,
                           use_sudo=True)
            fabric_ssh.sudo('chmod 440 {key_file}'.format(
                key_file=REMOTE_PRIVATE_KEY_PATH,
            ))


class Cloudify4_0_1Manager(_CloudifyManager):
    branch_name = '4.0.1'


class Cloudify4_1Manager(_CloudifyManager):
    branch_name = '4.1'


class CloudifyMasterManager(_CloudifyManager):
    branch_name = 'master'
    image_name_attribute = 'cloudify_manager_image_name_prefix'

    image_name = get_latest_manager_image_name()

    # The MTU is set to 1450 because we're using a static BOOTPROTO here (as
    # opposed to DHCP), which sets a lower default by default
    NETWORK_CONFIG_TEMPLATE = """DEVICE="eth{0}"
BOOTPROTO="static"
ONBOOT="yes"
TYPE="Ethernet"
USERCTL="yes"
PEERDNS="yes"
IPV6INIT="no"
PERSISTENT_DHCLIENT="1"
IPADDR="{1}"
NETMASK="255.255.255.128"
DEFROUTE="no"
MTU=1450
"""

    def enable_nics(self):
        """
        Extra network interfaces need to be manually enabled on the manager
        `manager.networks` is a dict that looks like this:
        {
            "network_0": "10.0.0.6",
            "network_1": "11.0.0.6",
            "network_2": "12.0.0.6"
        }
        """

        self._logger.info('Adding extra NICs...')

        # Need to do this for each network except 0 (eth0 is already enabled)
        for i in range(1, len(self.networks)):
            network_file_path = self._tmpdir / 'network_cfg_{0}'.format(i)
            ip_addr = self.networks['network_{0}'.format(i)]
            config_content = self.NETWORK_CONFIG_TEMPLATE.format(i, ip_addr)

            # Create and copy the interface config
            network_file_path.write_text(config_content)
            with self.ssh() as fabric_ssh:
                fabric_ssh.put(
                    network_file_path,
                    '/etc/sysconfig/network-scripts/ifcfg-eth{0}'.format(i),
                    use_sudo=True
                )
                # Start the interface
                fabric_ssh.sudo('ifup eth{0}'.format(i))


IMAGES = {
    '3.4.2': Cloudify3_4Manager,
    '4.0': Cloudify4_0Manager,
    '4.0.1': Cloudify4_0_1Manager,
    '4.1': Cloudify4_1Manager,
    'master': CloudifyMasterManager,
    'centos': VM,
}

CURRENT_MANAGER = IMAGES['master']


class TestHosts(object):

    __metaclass__ = ABCMeta

    def __init__(self,
                 cfy,
                 ssh_key,
                 tmpdir,
                 attributes,
                 logger,
                 number_of_instances=1,
                 instances=None,
                 tf_template=None,
                 template_inputs=None
                 ):
        """
        instances: supply a list of VM instances.
        This allows pre-configuration to happen before starting the hosts, or
        for a list of instances of different versions to be created at once.
        if instances is provided, number_of_instances will be ignored
        """

        super(TestHosts, self).__init__()
        self._logger = logger
        self._attributes = attributes
        self._tmpdir = tmpdir
        self._ssh_key = ssh_key
        self._cfy = cfy
        self._terraform = util.sh_bake(sh.terraform)
        self._terraform_inputs_file = self._tmpdir / 'terraform-vars.json'
        self._tf_template = tf_template or 'openstack-vm.tf.template'
        self.preconfigure_callback = None
        if instances is not None:
            self.instances = instances
        else:
            self.instances = [
                CURRENT_MANAGER()
                for _ in range(number_of_instances)]
        self._template_inputs = template_inputs or {'servers': self.instances}

    def _bootstrap_managers(self):
        pass

    def _get_server_flavor(self):
        return self._attributes.manager_server_flavor_name

    def create(self):
        """Creates the OpenStack infrastructure for a Cloudify manager.

        The openstack credentials file and private key file for SSHing
        to provisioned VMs are uploaded to the server."""
        self._logger.info('Creating image based cloudify instances: '
                          '[number_of_instances=%d]', len(self.instances))

        terraform_template_file = self._tmpdir / 'openstack-vm.tf'

        input_file = util.get_resource_path(
            'terraform/{0}'.format(self._tf_template)
        )
        with open(input_file, 'r') as f:
            tf_template = f.read()

        output = jinja2.Template(tf_template).render(self._template_inputs)

        terraform_template_file.write_text(output)

        self._terraform_inputs_file.write_text(json.dumps({
            'resource_suffix': str(uuid.uuid4()),
            'public_key_path': self._ssh_key.public_key_path,
            'private_key_path': self._ssh_key.private_key_path,
            'flavor': self._get_server_flavor()
        }, indent=2))

        try:
            with self._tmpdir:
                self._terraform.apply(['-var-file',
                                       self._terraform_inputs_file])
                outputs = util.AttributesDict(
                        {k: v['value'] for k, v in yaml.safe_load(
                                self._terraform.output(
                                        ['-json']).stdout).items()})
            self._attributes.update(outputs)

            self._update_instances_list(outputs)

            if self.preconfigure_callback:
                self.preconfigure_callback(self.instances)

            self._bootstrap_managers()

            for instance in self.instances:
                instance.verify_services_are_running()

                instance.upload_necessary_files()
                if instance.upload_plugins:
                    instance.upload_plugin('openstack_centos_core')

            self._logger.info('Test hosts successfully created!')

        except Exception as e:
            self._logger.error(
                    'Error creating image based hosts: %s', e)
            try:
                self.destroy()
            except sh.ErrorReturnCode as ex:
                self._logger.error('Error on terraform destroy: %s', ex)
            raise

    def destroy(self):
        """Destroys the OpenStack infrastructure."""
        self._logger.info('Destroying test hosts..')
        with self._tmpdir:
            self._terraform.destroy(
                    ['-var-file', self._terraform_inputs_file, '-force'])

    def _update_instances_list(self, outputs):
        for i, instance in enumerate(self.instances):
            public_ip_address = outputs['public_ip_address_{}'.format(i)]
            private_ip_address = outputs['private_ip_address_{}'.format(i)]
            # Some templates don't expose networks as outputs
            networks = outputs.get('networks_{}'.format(i), [])
            if hasattr(instance, 'api_version'):
                rest_client = util.create_rest_client(
                        public_ip_address,
                        username=self._attributes.cloudify_username,
                        password=self._attributes.cloudify_password,
                        tenant=self._attributes.cloudify_tenant,
                        api_version=instance.api_version,
                        )
            else:
                rest_client = None
            instance.create(
                    i,
                    public_ip_address,
                    private_ip_address,
                    networks,
                    rest_client,
                    self._ssh_key,
                    self._cfy,
                    self._attributes,
                    self._logger,
                    self._tmpdir
                    )


class BootstrapBasedCloudifyManagers(TestHosts):
    """
    Bootstraps a Cloudify manager using manager install RPM.
    """

    def __init__(self, *args, **kwargs):
        super(BootstrapBasedCloudifyManagers, self).__init__(*args, **kwargs)
        for manager in self.instances:
            manager.image_name = self._attributes.centos_7_image_name
        self._manager_install_rpm = util.get_manager_install_rpm_url()

    def _get_server_flavor(self):
        return self._attributes.medium_flavor_name

    def _bootstrap_managers(self):
        super(BootstrapBasedCloudifyManagers, self)._bootstrap_managers()

        for manager in self.instances:
            manager.bootstrap()
