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

from abc import ABCMeta, abstractmethod

from contextlib import contextmanager
import json
import os
import uuid

from fabric import api as fabric_api
from fabric import context_managers as fabric_context_managers
from influxdb import InfluxDBClient
import jinja2
import retrying
import sh

from cosmo_tester.framework import util
from cosmo_tester.framework import git_helper

REMOTE_PRIVATE_KEY_PATH = '/etc/cloudify/key.pem'
REMOTE_OPENSTACK_CONFIG_PATH = '/etc/cloudify/openstack_config.json'

MANAGER_BLUEPRINTS_REPO_URL = 'https://github.com/cloudify-cosmo/cloudify-manager-blueprints.git'  # noqa


class _CloudifyManager(object):

    def __init__(self,
                 index,
                 public_ip_address,
                 private_ip_address,
                 rest_client,
                 ssh_key,
                 cfy,
                 attributes,
                 logger,
                 config):
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
        self.influxdb_client = InfluxDBClient(public_ip_address, 8086,
                                              'root', 'root', 'cloudify')
        self.config = config

    @property
    def remote_private_key_path(self):
        """Returns the private key path on the manager."""
        return REMOTE_PRIVATE_KEY_PATH

    @contextmanager
    def ssh(self, **kwargs):
        with fabric_context_managers.settings(
                host_string=self.ip_address,
                user=self._attributes.centos7_username,
                key_filename=self._ssh_key.private_key_path,
                **kwargs):
            yield fabric_api

    def __str__(self):
        return 'Cloudify manager [{}:{}]'.format(self.index, self.ip_address)

    @retrying.retry(stop_max_attempt_number=3, wait_fixed=3000)
    def use(self):
        self._cfy.profiles.use('{0} -u {1} -p {2} -t {3}'.format(
                self.ip_address,
                self._attributes.cloudify_username,
                self._attributes.cloudify_password,
                self._attributes.cloudify_tenant).split())

    @property
    def server_id(self):
        """Returns this server's Id from the terraform outputs."""
        key = 'server_id_{}'.format(self.index)
        return self._attributes[key]

    def delete(self):
        """Deletes this manager's VM from the OpenStack envrionment."""
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

    @retrying.retry(stop_max_attempt_number=24, wait_fixed=5000)
    def verify_services_are_running(self):
        self._logger.info('Verifying all services are running on manager%d..',
                          self.index)
        status = self.client.manager.get_status()
        for service in status['services']:
            for instance in service['instances']:
                assert instance['SubState'] == 'running', \
                    'service {0} is in {1} state'.format(
                            service['display_name'], instance['SubState'])


class _ManagerConfig(object):

    def __init__(self):
        self.image_name = None
        self.upload_plugins = True

    @property
    def is_4_0(self):
        # This is a temporary measure. We will probably have subclasses for it
        return self.image_name.endswith('4.0')


class CloudifyCluster(object):

    __metaclass__ = ABCMeta

    def __init__(self,
                 cfy,
                 ssh_key,
                 tmpdir,
                 attributes,
                 logger,
                 number_of_managers=1):
        super(CloudifyCluster, self).__init__()
        self._logger = logger
        self._attributes = attributes
        self._tmpdir = tmpdir
        self._ssh_key = ssh_key
        self._cfy = cfy
        self._number_of_managers = number_of_managers
        self._terraform = util.sh_bake(sh.terraform)
        self._terraform_inputs_file = self._tmpdir / 'terraform-vars.json'
        self._managers = None
        self.preconfigure_callback = None
        self._managers_config = [self._get_default_manager_config()
                                 for _ in range(number_of_managers)]

    def _get_default_manager_config(self):
        config = _ManagerConfig()
        config.image_name = self._get_latest_manager_image_name()
        return config

    def _bootstrap_managers(self):
        pass

    @abstractmethod
    def _get_latest_manager_image_name(self):
        """Returns the image name for the manager's VM."""
        pass

    @staticmethod
    def create_image_based(
            cfy, ssh_key, tmpdir, attributes, logger, number_of_managers=1,
            create=True):
        """Creates an image based Cloudify manager.
        :param create: Determines whether to actually create the environment
         in this invocation. If set to False, create() should be invoked in
         order to create the environment. Setting it to False allows to
         change the servers configuration using the servers_config property
         before calling create().
        """
        cluster = ImageBasedCloudifyCluster(
                cfy,
                ssh_key,
                tmpdir,
                attributes,
                logger,
                number_of_managers=number_of_managers)
        if create:
            cluster.create()
        return cluster

    @staticmethod
    def create_bootstrap_based(cfy, ssh_key, tmpdir, attributes, logger,
                               preconfigure_callback=None):
        """Bootstraps a Cloudify manager using simple manager blueprint."""
        cluster = BootstrapBasedCloudifyCluster(cfy,
                                                ssh_key,
                                                tmpdir,
                                                attributes,
                                                logger)
        logger.info('Bootstrapping cloudify manager using simple '
                    'manager blueprint..')
        if preconfigure_callback:
            cluster.preconfigure_callback = preconfigure_callback
        cluster.create()
        return cluster

    def _get_server_flavor(self):
        return self._attributes.medium_flavor_name

    @property
    def managers(self):
        """Returns a list containing the managers in the cluster."""
        if not self._managers:
            raise RuntimeError('_managers is not set')
        return self._managers

    @property
    def managers_config(self):
        """Returns a list containing a manager configuration obj per manager
         to be created."""
        return self._managers_config

    def create(self):
        """Creates the OpenStack infrastructure for a Cloudify manager.

        The openstack credentials file and private key file for SSHing
        to provisioned VMs are uploaded to the server."""
        self._logger.info('Creating an image based cloudify cluster '
                          '[number_of_managers=%d]', self._number_of_managers)

        openstack_config_file = self._tmpdir / 'openstack_config.json'
        openstack_config_file.write_text(json.dumps({
            'username': os.environ['OS_USERNAME'],
            'password': os.environ['OS_PASSWORD'],
            'tenant_name': os.environ.get('OS_TENANT_NAME',
                                          os.environ['OS_PROJECT_NAME']),
            'auth_url': os.environ['OS_AUTH_URL']
        }, indent=2))

        terraform_template_file = self._tmpdir / 'openstack-vm.tf'

        input_file = util.get_resource_path(
                'terraform/openstack-vm.tf.template')
        with open(input_file, 'r') as f:
            terraform_template = f.read()

        output = jinja2.Template(terraform_template).render({
            'servers': self.managers_config
        })

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
                        {k: v['value'] for k, v in json.loads(
                                self._terraform.output(
                                        ['-json']).stdout).items()})
            self._attributes.update(outputs)
            self._create_managers_list(outputs)

            if self.preconfigure_callback:
                self.preconfigure_callback(self.managers)

            self._bootstrap_managers()

            for manager in self.managers:
                manager.verify_services_are_running()

            for i, manager in enumerate(self._managers):
                manager.use()
                self._upload_necessary_files_to_manager(manager,
                                                        openstack_config_file)
                if self.managers_config[i].upload_plugins:
                    self._upload_plugin_to_manager(
                            manager, 'openstack_centos_core')

            self._logger.info('Cloudify cluster successfully created!')

        except Exception as e:
            self._logger.error(
                    'Error creating image based cloudify cluster: %s', e)
            try:
                self.destroy()
            except sh.ErrorReturnCode as ex:
                self._logger.error('Error on terraform destroy: %s', ex)
            raise

    @retrying.retry(stop_max_attempt_number=3, wait_fixed=3000)
    def _upload_plugin_to_manager(self, manager, plugin_name):
        plugins_list = util.get_plugin_wagon_urls()
        plugin_wagon = [
            x['wgn_url'] for x in plugins_list
            if x['name'] == plugin_name]
        if len(plugin_wagon) != 1:
            self._logger.error(
                    '%s plugin wagon not found in:%s%s',
                    plugin_name,
                    os.linesep,
                    json.dumps(plugins_list, indent=2))
            raise RuntimeError(
                    '{} plugin not found in wagons list'.format(plugin_name))
        self._logger.info('Uploading %s plugin [%s] to %s..',
                          plugin_name,
                          plugin_wagon[0],
                          manager)
        # we keep this because plugin upload may fail but the manager
        # will contain the uploaded plugin which is in some corrupted state.
        plugins_ids_before_upload = [
            x.id for x in manager.client.plugins.list()]
        try:
            manager.client.plugins.upload(plugin_wagon[0])
            self._cfy.plugins.list()
        except Exception as cce:
            self._logger.error('Error on plugin upload: %s', cce)
            current_plugins_ids = [x.id for x in manager.client.plugins.list()]
            new_plugin_id = list(set(current_plugins_ids).intersection(
                    set(plugins_ids_before_upload)))
            if new_plugin_id:
                self._logger.info(
                        'Removing plugin after upload plugin failure: %s',
                        new_plugin_id[0])
                manager.client.plugins.delete(new_plugin_id[0])
            raise

    def _upload_necessary_files_to_manager(self,
                                           manager,
                                           openstack_config_file):
        self._logger.info('Uploading necessary files to %s', manager)
        with manager.ssh() as fabric_ssh:
            if manager.config.is_4_0:
                openstack_json_path = '/root/openstack_config.json'
            else:
                openstack_json_path = REMOTE_OPENSTACK_CONFIG_PATH
            fabric_ssh.put(openstack_config_file,
                           openstack_json_path,
                           use_sudo=True)
            fabric_ssh.put(self._ssh_key.private_key_path,
                           REMOTE_PRIVATE_KEY_PATH,
                           use_sudo=True)
            if not manager.config.is_4_0:
                fabric_ssh.sudo('chown root:cfyuser {key_file}'.format(
                    key_file=REMOTE_PRIVATE_KEY_PATH,
                ))
            fabric_ssh.sudo('chmod 440 {key_file}'.format(
                key_file=REMOTE_PRIVATE_KEY_PATH,
            ))

    def destroy(self):
        """Destroys the OpenStack infrastructure."""
        self._logger.info('Destroying cloudify cluster..')
        with self._tmpdir:
            self._terraform.destroy(
                    ['-var-file', self._terraform_inputs_file, '-force'])

    def _create_managers_list(self, outputs):
        self._managers = []
        for i in range(self._number_of_managers):
            public_ip_address = outputs['public_ip_address_{}'.format(i)]
            private_ip_address = outputs['private_ip_address_{}'.format(i)]
            rest_clinet = util.create_rest_client(
                    public_ip_address,
                    username=self._attributes.cloudify_username,
                    password=self._attributes.cloudify_password,
                    tenant=self._attributes.cloudify_tenant)
            self._managers.append(_CloudifyManager(i,
                                                   public_ip_address,
                                                   private_ip_address,
                                                   rest_clinet,
                                                   self._ssh_key,
                                                   self._cfy,
                                                   self._attributes,
                                                   self._logger,
                                                   self.managers_config[i]))


class ImageBasedCloudifyCluster(CloudifyCluster):
    """
    Starts a manager from an image on OpenStack.
    """

    def _get_latest_manager_image_name(self):
        """
        Returns the manager image name based on installed CLI version.
        For CLI version "4.0.0-m15"
        Returns: "cloudify-manager-premium-4.0m15"
        """
        version = util.get_cli_version()
        version_num, version_milestone = version.split('-')

        if version_num.endswith('.0') and version_num.count('.') > 1:
            version_num = version_num[:-2]

        version = version_num + version_milestone
        return '{}-{}'.format(
                self._attributes.cloudify_manager_image_name_prefix, version)


class BootstrapBasedCloudifyCluster(CloudifyCluster):
    """
    Bootstraps a Cloudify manager using simple manager blueprint.
    """

    def __init__(self, *args, **kwargs):
        super(BootstrapBasedCloudifyCluster, self).__init__(*args, **kwargs)
        self._manager_resources_package = \
            util.get_manager_resources_package_url()
        self._manager_blueprints_path = None
        self._inputs_file = None

    def _get_server_flavor(self):
        return self._attributes.large_flavor_name

    def _get_latest_manager_image_name(self):
        return self._attributes.centos7_image_name

    def _bootstrap_managers(self):
        super(BootstrapBasedCloudifyCluster, self)._bootstrap_managers()

        self._clone_manager_blueprints()
        self._create_inputs_file()
        self._bootstrap_manager()

    def _clone_manager_blueprints(self):
        self._manager_blueprints_path = git_helper.clone(
                MANAGER_BLUEPRINTS_REPO_URL,
                str(self._tmpdir))

    def _create_inputs_file(self):
        self._inputs_file = self._tmpdir / 'inputs.json'
        bootstrap_inputs = json.dumps({
            'public_ip': self.managers[0].ip_address,
            'private_ip': self.managers[0].private_ip_address,
            'ssh_user': self._attributes.centos7_username,
            'ssh_key_filename': self._ssh_key.private_key_path,
            'admin_username': self._attributes.cloudify_username,
            'admin_password': self._attributes.cloudify_password,
            'manager_resources_package': self._manager_resources_package},
            indent=2)
        self._logger.info(
                'Bootstrap inputs:%s%s', os.linesep, bootstrap_inputs)
        self._inputs_file.write_text(bootstrap_inputs)

    def _bootstrap_manager(self):
        manager_blueprint_path = \
            self._manager_blueprints_path / 'simple-manager-blueprint.yaml'
        self._cfy.bootstrap([manager_blueprint_path, '-i', self._inputs_file])
