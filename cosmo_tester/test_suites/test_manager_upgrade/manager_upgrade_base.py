########
# Copyright (c) 2016 GigaSpaces Technologies Ltd. All rights reserved
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

from contextlib import contextmanager
import subprocess
import json
import os
import shutil
import tempfile
import time
import urllib2

import fabric
from influxdb import InfluxDBClient
from pkg_resources import parse_version

from cloudify_cli import constants as cli_constants
from cloudify.workflows import local

from cosmo_tester.framework.testenv import TestCase
from cosmo_tester.framework.git_helper import clone
from cosmo_tester.framework.util import create_rest_client, \
    YamlPatcher, get_cfy


BOOTSTRAP_REPO_URL = 'https://github.com/cloudify-cosmo/' \
                     'cloudify-manager-blueprints.git'

BOOTSTRAP_BRANCH = '3.4rc1'

UPGRADE_REPO_URL = 'https://github.com/cloudify-cosmo/' \
                   'cloudify-manager-blueprints.git'
UPGRADE_BRANCH = 'master'


class BaseManagerUpgradeTest(TestCase):
    """Base for manager upgrade tests, with methods for bootstrap/upgrade.

    When writing a manager upgrade test, inherit from this, and use the
    .prepare_manager, .upgrade_manager, .rollback_manager, etc. methods -
    but note that upgrade, rollback and other methods rely on state stored
    during the .prepare_manager method.

    For debugging purposes, we can skip bootstrapping the manager that will
    be used in the test, and use a pre-existing one: see the
    ._use_external_manager method
    """

    @property
    def _use_external_manager(self):
        """Check if the handler config has a valid upgrade_manager setting.

        To use a pre-bootstrapped manager for this test, handler configuration
        needs to contain a "upgrade_manager" key, referencing an object
        with the following keys: manager_key, agents_key (filepaths to the ssh
        keys), public_ip, private_ip.

        Only use this when working on the test itself.
        """
        return 'upgrade_manager' in self.env.handler_configuration

    @contextmanager
    def _manager_fabric_env(self, **kwargs):
        """Push a fabric context connecting to the manager.

        Inside this contextmanager, use fabric's methods to interact with
        the manager that was bootstrapped during the test.
        """
        # Note that bootstrapping the manager is part of the test, so we can't
        # use the testenv manager - we can't use the self.manager_env_fabric
        # method.
        if self.upgrade_manager_ip is None:
            raise RuntimeError("Can't SSH to the manager before bootstrapping")

        inputs = self.manager_inputs
        settings = {
            'host_string': self.upgrade_manager_ip,
            'user': inputs['ssh_user'],
            'key_filename': inputs['ssh_key_filename'],
            # use keepalive to make sure fabric doesn't hang, when a connection
            # dies after a long period of inactivity (eg. running an upgrade)
            'keepalive': 30,
        }
        settings.update(kwargs)
        with fabric.context_managers.settings(**settings):
            yield fabric.api

    def _bootstrap_local_env(self, workdir):
        storage = local.FileStorage(
            os.path.join(workdir, '.cloudify', 'bootstrap'))
        return local.load_env('manager', storage=storage)

    def _blueprint_rpm_versions(self, blueprint_path, inputs):
        """RPM filenames that should be installed on the manager.

        Currently, only amqpinflux, restservice and mgmtworker are installed
        from RPMs during the bootstrap.
        """
        env = local.init_env(
            blueprint_path,
            inputs=inputs,
            ignored_modules=cli_constants.IGNORED_LOCAL_WORKFLOW_MODULES)

        storage = env.storage

        amqp_influx_rpm = storage.get_node('amqp_influx')['properties'][
            'amqpinflux_rpm_source_url']
        restservice_rpm = storage.get_node('rest_service')['properties'][
            'rest_service_rpm_source_url']
        mgmtworker_rpm = storage.get_node('mgmt_worker')['properties'][
            'management_worker_rpm_source_url']
        return {
            'cloudify-amqp-influx': amqp_influx_rpm,
            'cloudify-rest-service': restservice_rpm,
            'cloudify-management-worker': mgmtworker_rpm
        }

    def _cloudify_rpm_versions(self):
        with self._manager_fabric_env() as fabric:
            return fabric.sudo('rpm -qa | grep cloudify')

    def check_rpm_versions(self, blueprint_path, inputs):
        """Check if installed RPMs are the versions declared in the blueprint.

        Parse the blueprint to retrieve package RPM filenames, and verify
        that `rpm -qa` on the manager reports these exact versions.
        """
        blueprint_rpms = self._blueprint_rpm_versions(blueprint_path, inputs)
        installed_rpms = self._cloudify_rpm_versions()
        for service_name, rpm_filename in blueprint_rpms.items():
            for line in installed_rpms.split('\n'):
                line = line.strip()
                if line.startswith(service_name):
                    self.assertIn(line.strip(), rpm_filename)

    def get_curr_version(self):
        version = self.rest_client.manager.get_version()['version']
        # Parse version does not handle 'm' version well.
        version = version.replace('m', 'a')
        return parse_version(version)

    def prepare_manager(self):
        # note that we're using a separate manager checkout, so we need to
        # create our own utils like cfy and the rest client, rather than use
        # the testenv ones
        self.cfy_workdir = tempfile.mkdtemp(prefix='manager-upgrade-')
        self.addCleanup(shutil.rmtree, self.cfy_workdir)
        self.manager_cfy = get_cfy()
        self.manager_inputs = self._get_bootstrap_inputs()

        if self._use_external_manager:
            upgrade_config = self.env.handler_configuration['upgrade_manager']
            self.upgrade_manager_ip = upgrade_config['public_ip']
            self.manager_private_ip = upgrade_config['private_ip']
            self.manager_cfy.profiles.use(self.upgrade_manager_ip)
        else:
            self.bootstrap_manager()

        self.rest_client = create_rest_client(self.upgrade_manager_ip)

        self.bootstrap_manager_version = self.get_curr_version()

    def _get_keys(self, prefix):
        if self._use_external_manager:
            upgrade_config = self.env.handler_configuration['upgrade_manager']
            return upgrade_config['manager_key'], upgrade_config['agents_key']
        else:
            ssh_key_filename = os.path.join(self.workdir, 'manager.key')
            self.addCleanup(self.env.handler.remove_keypair,
                            prefix + '-manager-key')

            agent_key_path = os.path.join(self.workdir, 'agents.key')
            self.addCleanup(self.env.handler.remove_keypair,
                            prefix + '-agents-key')
            return ssh_key_filename, agent_key_path

    def _get_bootstrap_inputs(self):
        prefix = self.test_id

        ssh_key_filename, agent_key_path = self._get_keys(prefix)

        return {
            'keystone_username': self.env.keystone_username,
            'keystone_password': self.env.keystone_password,
            'keystone_tenant_name': self.env.keystone_tenant_name,
            'keystone_url': self.env.keystone_url,
            'region': self.env.region,
            'flavor_id': self.env.medium_flavor_id,
            'image_id': self.env.centos_7_image_id,

            'ssh_user': self.env.centos_7_image_user,
            'external_network_name': self.env.external_network_name,
            'resources_prefix': 'test-upgrade-',

            'manager_server_name': prefix + '-manager',

            # shared settings
            'manager_public_key_name': prefix + '-manager-key',
            'agent_public_key_name': prefix + '-agents-key',
            'ssh_key_filename': ssh_key_filename,
            'agent_private_key_path': agent_key_path,

            'management_network_name': prefix + '-network',
            'management_subnet_name': prefix + '-subnet',
            'management_router': prefix + '-router',

            'agents_user': '',

            # private settings
            'manager_security_group_name': prefix + '-m-sg',
            'agents_security_group_name': prefix + '-a-sg',
            'manager_port_name': prefix + '-port',
            'management_subnet_dns_nameservers': ['8.8.8.8', '8.8.4.4'],

            # we'll be using the openstack plugin to install a deployment.
            # We need to either upload the plugin (using the CLI or the REST
            # client), or install a compiler so that the plugin can be
            # installed from source on the manager.
            'install_python_compilers': True
        }

    def get_bootstrap_blueprint(self):
        manager_repo_dir = tempfile.mkdtemp(prefix='manager-upgrade-')
        self.addCleanup(shutil.rmtree, manager_repo_dir)
        manager_repo = clone(BOOTSTRAP_REPO_URL,
                             manager_repo_dir,
                             branch=BOOTSTRAP_BRANCH)
        yaml_path = manager_repo / 'openstack-manager-blueprint.yaml'

        # allow the ports that we're going to connect to from the tests,
        # when doing checks
        for port in [8086, 9200, 9900]:
            secgroup_cfg = [{
                'port_range_min': port,
                'port_range_max': port,
                'remote_ip_prefix': '0.0.0.0/0'
            }]
            secgroup_cfg_path = 'node_templates.management_security_group' \
                                '.properties.rules'
            with YamlPatcher(yaml_path) as patch:
                patch.append_value(secgroup_cfg_path, secgroup_cfg)

        return yaml_path

    def _load_private_ip_from_env(self, workdir):
        env = self._bootstrap_local_env(workdir)
        return env.outputs()['private_ip']

    def _load_public_ip_from_env(self, workdir):
        env = self._bootstrap_local_env(workdir)
        return env.outputs()['manager_ip']

    def bootstrap_manager(self):
        self.bootstrap_blueprint = self.get_bootstrap_blueprint()
        inputs_path = self.get_inputs_in_temp_file(
            self.manager_inputs, self._testMethodName)

        try:
            bootstrap_cli_env = tempfile.mkdtemp()
            # create bootstrap venv
            create_venv_cmd = 'virtualenv {0}'.format(bootstrap_cli_env)
            self._execute_command(create_venv_cmd.split())
            # install cli matching the bootstrap manager version
            py_bin_path = os.path.join(bootstrap_cli_env, 'bin')
            install_cli_cmd = '{0}/pip install cloudify=={1}' \
                .format(py_bin_path, BOOTSTRAP_BRANCH)
            self._execute_command(install_cli_cmd.split())
            # init temp workdir
            cfy_init_cmd = '{0}/cfy init -r'.format(py_bin_path)

            self._execute_command(cfy_init_cmd.split(), cwd=self.cfy_workdir)
            # execute bootstrap
            bootstrap_cmd = '{0}/cfy bootstrap {1} -i {2} --install-plugins'\
                .format(py_bin_path, self.bootstrap_blueprint, inputs_path)
            self._execute_command(bootstrap_cmd.split(), cwd=self.cfy_workdir)

            self.upgrade_manager_ip = self._load_public_ip_from_env(
                    self.cfy_workdir)
            self.manager_private_ip = self._load_private_ip_from_env(
                    self.cfy_workdir)
            self.manager_cfy.profiles.use(self.upgrade_manager_ip)
        finally:
            if os.path.isdir(bootstrap_cli_env):
                shutil.rmtree(bootstrap_cli_env, ignore_errors=True)

    def _execute_command(self, command, cwd=None):
        process = subprocess.Popen(command, cwd=cwd, stdout=subprocess.PIPE)

        while process.poll() is None:
            line = process.stdout.readline()
            self.logger.info(line)
        self.logger.info(process.stdout.read())

    def deploy_hello_world(self, prefix=''):
        """Install the hello world app."""
        blueprint_id = prefix + self.test_id
        deployment_id = prefix + self.test_id
        hello_repo_dir = tempfile.mkdtemp(prefix='manager-upgrade-')
        hello_repo_path = clone(
            'https://github.com/cloudify-cosmo/'
            'cloudify-hello-world-example.git',
            hello_repo_dir
        )
        self.addCleanup(shutil.rmtree, hello_repo_dir)
        hello_blueprint_path = hello_repo_path / 'blueprint.yaml'
        self.cfy.blueprints.upload(
            hello_blueprint_path,
            blueprint_id=blueprint_id
        )

        inputs = {
            'agent_user': self.env.ubuntu_image_user,
            'image': self.env.ubuntu_trusty_image_name,
            'flavor': self.env.flavor_name
        }
        inputs = self.get_inputs_in_temp_file(inputs, deployment_id)
        self.manager_cfy.deployments.create(
            deployment_id,
            blueprint_id=blueprint_id,
            inputs=inputs
        )

        self.manager_cfy.executions.start(
            'install',
            deployment_id=deployment_id
        )
        return deployment_id

    def get_upgrade_blueprint(self):
        """Path to the blueprint using for upgrading the manager.

        Note that upgrade uses a simple blueprint, even though the manager
        was installed using the openstack blueprint. Upgrade does not need to
        use the same blueprint.
        """
        repo_dir = tempfile.mkdtemp(prefix='manager-upgrade-')
        self.addCleanup(shutil.rmtree, repo_dir)
        upgrade_blueprint_path = clone(UPGRADE_REPO_URL,
                                       repo_dir,
                                       branch=UPGRADE_BRANCH)

        return upgrade_blueprint_path / 'simple-manager-blueprint.yaml'

    def upgrade_manager(self, blueprint=None, inputs=None):
        self.upgrade_blueprint = blueprint or self.get_upgrade_blueprint()
        if not blueprint:
            # we're changing one of the ES inputs -
            # make sure we also re-install ES
            with YamlPatcher(self.upgrade_blueprint) as patch:
                patch.set_value(
                    ('node_templates.elasticsearch.properties'
                     '.use_existing_on_upgrade'),
                    False)

        self.upgrade_inputs = inputs or {
            'private_ip': self.manager_private_ip,
            'public_ip': self.upgrade_manager_ip,
            'ssh_key_filename': self.manager_inputs['ssh_key_filename'],
            'ssh_user': self.manager_inputs['ssh_user'],
            'ssh_port': 22,
            'elasticsearch_endpoint_port': 9900
        }
        upgrade_inputs_file = self.get_inputs_in_temp_file(
            self.upgrade_inputs,
            self._testMethodName
        )

        with self.maintenance_mode():
            self.manager_cfy.upgrade(
                self.upgrade_blueprint,
                inputs=upgrade_inputs_file,
                install_plugins=self.env.install_plugins
            )

    def post_upgrade_checks(self, preupgrade_deployment_id):
        """To check if the upgrade succeeded:
            - fire a request to the REST service
            - check that elasticsearch is listening on the changed port
            - check that the pre-existing deployment still reports to influxdb
            - install a new deployment, check that it reports to influxdb,
              and uninstall it: to check that the manager still allows
              creating, installing and uninstalling deployments correctly
        """
        upgrade_manager_version = self.get_curr_version()
        self.assertGreaterEqual(upgrade_manager_version,
                                self.bootstrap_manager_version)
        self.check_rpm_versions(self.upgrade_blueprint, self.upgrade_inputs)

        self.rest_client.blueprints.list()
        self.check_elasticsearch(self.upgrade_manager_ip, 9900)
        self.check_influx(preupgrade_deployment_id)

        postupgrade_deployment_id = self.deploy_hello_world('post-')
        self.check_influx(postupgrade_deployment_id)
        self.uninstall_deployment(postupgrade_deployment_id)

    def check_influx(self, deployment_id):
        """Check that the deployment_id continues to report metrics.

        Look at the last 5 seconds worth of metrics. To avoid race conditions
        (running this check before the deployment even had a chance to report
        any metrics), first wait 5 seconds to allow some metrics to be
        gathered.
        """
        # TODO influx config should be pulled from props?
        time.sleep(5)
        influx_client = InfluxDBClient(self.upgrade_manager_ip, 8086,
                                       'root', 'root', 'cloudify')
        try:
            result = influx_client.query('select * from /^{0}\./i '
                                         'where time > now() - 5s'
                                         .format(deployment_id))
        except NameError as e:
            self.fail('monitoring events list for deployment with ID {0} were'
                      ' not found on influxDB. error is: {1}'
                      .format(deployment_id, e))

        self.assertTrue(len(result) > 0)

    def check_elasticsearch(self, host, port):
        """Check that elasticsearch is listening on the given host:port.

        This is used for checking if the ES port changed correctly during
        the upgrade.
        """
        try:
            response = urllib2.urlopen('http://{0}:{1}'.format(
                self.upgrade_manager_ip, port))
            response = json.load(response)
            if response['status'] != 200:
                raise ValueError('Incorrect status {0}'.format(
                    response['status']))
        except (ValueError, urllib2.URLError):
            self.fail('elasticsearch isnt listening on the changed port')

    def uninstall_deployment(self, deployment_id):
        self.manager_cfy.executions.start(
            'uninstall',
            deployment_id=deployment_id
        )

    def rollback_manager(self, blueprint=None, inputs=None):
        blueprint = blueprint or self.upgrade_blueprint
        rollback_inputs = inputs or {
            'private_ip': self.manager_private_ip,
            'public_ip': self.upgrade_manager_ip,
            'ssh_key_filename': self.manager_inputs['ssh_key_filename'],
            'ssh_port': 22,
            'ssh_user': self.manager_inputs['ssh_user']
        }
        rollback_inputs_file = self.get_inputs_in_temp_file(
            rollback_inputs,
            self._testMethodName
        )

        with self.maintenance_mode():
            self.manager_cfy.rollback(blueprint, inputs=rollback_inputs_file)

    def post_rollback_checks(self, preupgrade_deployment_id):
        rollback_manager_version = self.get_curr_version()
        self.assertEqual(rollback_manager_version,
                         self.bootstrap_manager_version)
        self.check_rpm_versions(self.bootstrap_blueprint, self.manager_inputs)

        self.rest_client.blueprints.list()
        self.check_elasticsearch(self.upgrade_manager_ip, 9200)
        self.check_influx(preupgrade_deployment_id)

    def teardown_manager(self):
        if not self._use_external_manager:
            self.manager_cfy.teardown(ignore_deployments=True)

    # a failed copy command on centos outputs an error with illegal chars.
    # replacing them in order to be able to print the output, and find
    # a required string in the error message.
    def replace_illegal_chars(self, s):
        return s.replace(u'\u2019', "'").replace(u'\u2018', "'")
