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

import os
import json
import uuid
from urllib import urlretrieve
from contextlib import contextmanager

import jinja2
import retrying
import sh
from fabric import api as fabric_api
from fabric import context_managers as fabric_context_managers
from influxdb import InfluxDBClient

from cosmo_tester.framework import util
from cosmo_tester.framework import git_helper

from cloudify_cli.constants import DEFAULT_TENANT_NAME


REMOTE_PRIVATE_KEY_PATH = '/etc/cloudify/key.pem'
REMOTE_OPENSTACK_CONFIG_PATH = '/etc/cloudify/openstack_config.json'

MANAGER_BLUEPRINTS_REPO_URL = 'https://github.com/cloudify-cosmo/cloudify-manager-blueprints.git'  # noqa
RSYNC_SCRIPT_URL = 'https://raw.githubusercontent.com/cloudify-cosmo/cloudify-dev/master/scripts/rsync.sh'  # NOQA

MANAGER_API_VERSIONS = {
    'master': 'v3',
    '4.1': 'v3',
    '4.0.1': 'v3',
    '4.0': 'v3',
    '3.4.2': 'v2',
}


ATTRIBUTES = util.get_attributes()


class _CloudifyManager(object):

    __metaclass__ = ABCMeta

    def __init__(self, upload_plugins=True):
        self.upload_plugins = upload_plugins

    def create(
            self,
            index,
            public_ip_address,
            private_ip_address,
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

    def _upload_necessary_files(self, openstack_config_file):
        self._logger.info('Uploading necessary files to %s', self)
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
                          self)

        try:
            with self.ssh() as fabric_ssh:
                # This will only work for images as cfy is pre-installed there.
                # from some reason this method is usually less error prone.
                fabric_ssh.run(
                    'cfy plugins upload {0} -t {1}'.format(
                        plugin_wagon[0], tenant_name
                    ))
        except Exception:
            try:
                self.use()
                self._cfy.plugins.upload([plugin_wagon[0], '-t', tenant_name])
            except Exception:
                # This is needed for 3.4 managers. local cfy isn't
                # compatible and cfy isn't installed in the image
                self.client.plugins.upload(plugin_wagon[0])

    @property
    def remote_private_key_path(self):
        """Returns the private key path on the manager."""
        return REMOTE_PRIVATE_KEY_PATH

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
            os.chmod(self._rsync_path, 0755)  # Make the script executable

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


def _get_latest_manager_image_name():
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

    def _upload_necessary_files(self, openstack_config_file):
        self._logger.info('Uploading necessary files to %s', self)
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

    def _upload_necessary_files(self, openstack_config_file):
        self._logger.info('Uploading necessary files to %s', self)
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

    image_name = _get_latest_manager_image_name()


class NotAManager(_CloudifyManager):
    def create(
            self,
            index,
            public_ip_address,
            private_ip_address,
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

    def verify_services_are_running(self):
        return True

    def use(self, tenant=None):
        return True

    def _upload_plugin(self, plugin_name):
        return True

    def _upload_necessary_files(self, openstack_config_file):
        return True

    image_name = ATTRIBUTES['notmanager_image_name']
    branch_name = 'master'


MANAGERS = {
    '3.4.2': Cloudify3_4Manager,
    '4.0': Cloudify4_0Manager,
    '4.0.1': Cloudify4_0_1Manager,
    '4.1': Cloudify4_1Manager,
    'master': CloudifyMasterManager,
    'notamanager': NotAManager,
}

CURRENT_MANAGER = MANAGERS['master']


class CloudifyCluster(object):

    __metaclass__ = ABCMeta

    def __init__(self,
                 cfy,
                 ssh_key,
                 tmpdir,
                 attributes,
                 logger,
                 number_of_managers=1,
                 managers=None,
                 ):
        """
        managers: supply a list of _CloudifyManager instances.
        This allows pre-configuration to happen before starting the cluster, or
        for a list of managers of different versions to be created at once.
        if managers is provided, number_of_managers will be ignored
        """
        super(CloudifyCluster, self).__init__()
        self._logger = logger
        self._attributes = attributes
        self._tmpdir = tmpdir
        self._ssh_key = ssh_key
        self._cfy = cfy
        self._terraform = util.sh_bake(sh.terraform)
        self._terraform_inputs_file = self._tmpdir / 'terraform-vars.json'
        self.preconfigure_callback = None
        if managers is not None:
            self.managers = managers
        else:
            self.managers = [
                CURRENT_MANAGER()
                for _ in range(number_of_managers)]

    def _bootstrap_managers(self):
        pass

    @staticmethod
    def create_image_based(
            cfy, ssh_key, tmpdir, attributes, logger,
            number_of_managers=1,
            managers=None,
            create=True,
            ):
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
                number_of_managers=number_of_managers,
                managers=managers,
                )
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
        cluster.managers[0].image_name = ATTRIBUTES['centos_7_image_name']
        cluster.create()
        return cluster

    def create_openstack_config_file(self):
        openstack_config_file = self._tmpdir / 'openstack_config.json'
        openstack_config_file.write_text(json.dumps({
            'username': os.environ['OS_USERNAME'],
            'password': os.environ['OS_PASSWORD'],
            'tenant_name': os.environ.get('OS_TENANT_NAME',
                                          os.environ['OS_PROJECT_NAME']),
            'auth_url': os.environ['OS_AUTH_URL']
        }, indent=2))
        return openstack_config_file

    def _get_server_flavor(self):
        return self._attributes.manager_server_flavor_name

    def create(self):
        """Creates the OpenStack infrastructure for a Cloudify manager.

        The openstack credentials file and private key file for SSHing
        to provisioned VMs are uploaded to the server."""
        self._logger.info('Creating an image based cloudify cluster '
                          '[number_of_managers=%d]', len(self.managers))

        openstack_config_file = self.create_openstack_config_file()

        terraform_template_file = self._tmpdir / 'openstack-vm.tf'

        input_file = util.get_resource_path(
                'terraform/openstack-vm.tf.template')
        with open(input_file, 'r') as f:
            terraform_template = f.read()

        output = jinja2.Template(terraform_template).render({
            'servers': self.managers
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

            self._update_managers_list(outputs)

            if self.preconfigure_callback:
                self.preconfigure_callback(self.managers)

            self._bootstrap_managers()

            for manager in self.managers:
                manager.verify_services_are_running()

                manager._upload_necessary_files(openstack_config_file)
                if manager.upload_plugins:
                    manager.upload_plugin('openstack_centos_core')

            self._logger.info('Cloudify cluster successfully created!')

        except Exception as e:
            self._logger.error(
                    'Error creating image based cloudify cluster: %s', e)
            try:
                self.destroy()
            except sh.ErrorReturnCode as ex:
                self._logger.error('Error on terraform destroy: %s', ex)
            raise

    def destroy(self):
        """Destroys the OpenStack infrastructure."""
        self._logger.info('Destroying cloudify cluster..')
        with self._tmpdir:
            self._terraform.destroy(
                    ['-var-file', self._terraform_inputs_file, '-force'])

    def _update_managers_list(self, outputs):
        for i, manager in enumerate(self.managers):
            public_ip_address = outputs['public_ip_address_{}'.format(i)]
            private_ip_address = outputs['private_ip_address_{}'.format(i)]
            rest_client = util.create_rest_client(
                    public_ip_address,
                    username=self._attributes.cloudify_username,
                    password=self._attributes.cloudify_password,
                    tenant=self._attributes.cloudify_tenant,
                    api_version=manager.api_version,
                    )
            manager.create(
                    i,
                    public_ip_address,
                    private_ip_address,
                    rest_client,
                    self._ssh_key,
                    self._cfy,
                    self._attributes,
                    self._logger,
                    self._tmpdir
                    )


class ImageBasedCloudifyCluster(CloudifyCluster):
    """
    Starts a manager from an image on OpenStack.
    """


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
        return self._attributes.centos_7_image_name

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
                'ssh_user': self._attributes.centos_7_username,
                'ssh_key_filename': self._ssh_key.private_key_path,
                'admin_username': self._attributes.cloudify_username,
                'admin_password': self._attributes.cloudify_password,
                'manager_resources_package': self._manager_resources_package,
            },
            indent=2,
        )
        self._logger.info(
                'Bootstrap inputs:%s%s', os.linesep, bootstrap_inputs)
        self._inputs_file.write_text(bootstrap_inputs)

    def _bootstrap_manager(self):
        manager_blueprint_path = \
            self._manager_blueprints_path / 'simple-manager-blueprint.yaml'
        self._cfy.bootstrap([manager_blueprint_path, '-i', self._inputs_file])
