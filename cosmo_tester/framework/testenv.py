########
# Copyright (c) 2014 GigaSpaces Technologies Ltd. All rights reserved
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

__author__ = 'dan'

import unittest
import logging
import sys
import shutil
import tempfile
import time
import copy
import os

import yaml
from path import path
from cosmo_manager_rest_client.cosmo_manager_rest_client import (
    CosmoManagerRestClient)

from cosmo_tester.framework.cfy_helper import CfyHelper
from cosmo_tester.framework.util import (get_blueprint_path,
                                         Singleton,
                                         CloudifyConfigReader)
from cosmo_tester.framework.openstack_api import (openstack_infra_state,
                                                  openstack_infra_state_delta,
                                                  remove_openstack_resources)

root = logging.getLogger()
ch = logging.StreamHandler(sys.stdout)
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter(fmt='%(asctime)s [%(levelname)s] '
                                  '[%(name)s] %(message)s',
                              datefmt='%H:%M:%S')
ch.setFormatter(formatter)

# clear all other handlers
for handler in root.handlers:
    root.removeHandler(handler)

root.addHandler(ch)
logger = logging.getLogger("TESTENV")
logger.setLevel(logging.DEBUG)

logging.getLogger('neutronclient.client').setLevel(logging.INFO)
logging.getLogger('novaclient.client').setLevel(logging.INFO)

CLOUDIFY_TEST_MANAGEMENT_IP = 'CLOUDIFY_TEST_MANAGEMENT_IP'
CLOUDIFY_TEST_CONFIG_PATH = 'CLOUDIFY_TEST_CONFIG_PATH'
CLOUDIFY_TEST_NO_CLEANUP = 'CLOUDIFY_TEST_NO_CLEANUP'


class CleanupContext(object):

    logger = logging.getLogger('CleanupContext')
    logger.setLevel(logging.DEBUG)

    def __init__(self, context_name, cloudify_config):
        self.context_name = context_name
        self.cloudify_config = cloudify_config
        self.before_run = openstack_infra_state(cloudify_config)

    def cleanup(self):
        before_cleanup = openstack_infra_state(self.cloudify_config)
        resources_to_teardown = openstack_infra_state_delta(
            before=self.before_run, after=before_cleanup)
        if os.environ.get(CLOUDIFY_TEST_NO_CLEANUP):
            self.logger.warn('[{0}] SKIPPING cleanup: of the resources: {1}'
                             .format(self.context_name, resources_to_teardown))
            return

        self.logger.info('[{0}] Performing cleanup: will try removing '
                         'these resources: {1}'
                         .format(self.context_name, resources_to_teardown))

        leftovers = remove_openstack_resources(self.cloudify_config,
                                               resources_to_teardown)
        self.logger.info('[{0}] Leftover resources after cleanup: {1}'
                         .format(self.context_name, leftovers))


# Singleton class
class TestEnvironment(object):
    __metaclass__ = Singleton

    # Singleton class
    def __init__(self):
        self._initial_cwd = os.getcwd()
        self._global_cleanup_context = None
        self._management_running = False
        self.rest_client = None
        self.management_ip = None

        if not CLOUDIFY_TEST_CONFIG_PATH in os.environ:
            raise RuntimeError('a path to cloudify-config must be configured '
                               'in "CLOUDIFY_TEST_CONFIG_PATH" env variable')
        self.cloudify_config_path = path(os.environ[CLOUDIFY_TEST_CONFIG_PATH])

        if not self.cloudify_config_path.isfile():
            raise RuntimeError('cloud-config file configured in env variable'
                               ' {0} does not seem to exist'
                               .format(self.cloudify_config_path))
        self.cloudify_config = yaml.load(self.cloudify_config_path.text())

        if CLOUDIFY_TEST_MANAGEMENT_IP in os.environ:
            self._running_env_setup(os.environ[CLOUDIFY_TEST_MANAGEMENT_IP])

        self._config_reader = CloudifyConfigReader(self.cloudify_config)

    def setup(self):
        os.chdir(self._initial_cwd)
        return self

    def bootstrap_if_necessary(self):
        if self._management_running:
            return
        self._global_cleanup_context = CleanupContext('testenv',
                                                      self.cloudify_config)
        cfy = CfyHelper()
        try:
            cfy.bootstrap(
                self.cloudify_config_path,
                keep_up_on_failure=True,
                verbose=True,
                dev_mode=False,
                alternate_bootstrap_method=False)
            self._running_env_setup(cfy.get_management_ip())
        finally:
            cfy.close()

    def teardown_if_necessary(self):
        if self._global_cleanup_context is None:
            return
        self._global_cleanup_context.cleanup()

    def _running_env_setup(self, management_ip):
        self.management_ip = management_ip
        self.rest_client = CosmoManagerRestClient(self.management_ip)
        response = self.rest_client.status()
        if not response.status == 'running':
            raise RuntimeError('Manager at {0} is not running.'
                               .format(self.management_ip))
        self._management_running = True

    @property
    def management_network_name(self):
        return self._config_reader.management_network_name

    @property
    def agent_key_path(self):
        return self._config_reader.agent_key_path

    @property
    def agent_keypair_name(self):
        return self._config_reader.agent_keypair_name

    @property
    def external_network_name(self):
        return self._config_reader.external_network_name

    @property
    def agents_security_group(self):
        return self._config_reader.agents_security_group

    @property
    def management_server_name(self):
        return self._config_reader.management_server_name

    @property
    def management_server_floating_ip(self):
        return self._config_reader.management_server_floating_ip

    @property
    def management_sub_network_name(self):
        return self._config_reader.management_sub_network_name

    @property
    def management_router_name(self):
        return self._config_reader.management_router_name

    @property
    def management_key_path(self):
        return self._config_reader.management_key_path

    @property
    def management_keypair_name(self):
        return self._config_reader.management_keypair_name

    @property
    def management_security_group(self):
        return self._config_reader.management_security_group


class TestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        pass

    @classmethod
    def tearDownClass(cls):
        pass

    def setUp(self):
        self.env = TestEnvironment().setup()
        self.logger = logging.getLogger(self._testMethodName)
        self.logger.setLevel(logging.INFO)
        self.workdir = tempfile.mkdtemp(prefix='cosmo-test-')
        self.cfy = CfyHelper(cfy_workdir=self.workdir,
                             management_ip=self.env.management_ip)
        self.rest = self.env.rest_client
        self.test_id = 'system-test-{0}'.format(time.strftime("%Y%m%d-%H%M"))
        self.blueprint_yaml = None
        self._test_cleanup_context = CleanupContext(self._testMethodName,
                                                    self.env.cloudify_config)

    def tearDown(self):
        self._test_cleanup_context.cleanup()
        shutil.rmtree(self.workdir)

    def get_manager_state(self):
        self.logger.info('Fetching manager current state')
        blueprints = {}
        for blueprint in self.rest.list_blueprints():
            blueprints[blueprint.id] = blueprint
        deployments = {}
        for deployment in self.rest.list_deployments():
            deployments[deployment.id] = deployment
        nodes = {}
        for deployment_id in deployments.keys():
            for node in self.rest.list_deployment_nodes(deployment_id).nodes:
                nodes[node.id] = node
        workflows = {}
        deployment_nodes = {}
        node_state = {}
        for deployment_id in deployments.keys():
            workflows[deployment_id] = self.rest.list_workflows(deployment_id)
            deployment_nodes[deployment_id] = self.rest.list_deployment_nodes(
                deployment_id,
                get_state=True)
            node_state[deployment_id] = {}
            for node in deployment_nodes[deployment_id].nodes:
                node_state[deployment_id][node.id] = self.rest.get_node_state(
                    node.id,
                    get_state=True,
                    get_runtime_properties=True)

        return {
            'blueprints': blueprints,
            'deployments': deployments,
            'workflows': workflows,
            'nodes': nodes,
            'node_state': node_state,
            'deployment_nodes': deployment_nodes
        }

    def get_manager_state_delta(self, before, after):
        after = copy.deepcopy(after)
        for blueprint_id in before['blueprints'].keys():
            del after['blueprints'][blueprint_id]
        for deployment_id in before['deployments'].keys():
            del after['deployments'][deployment_id]
            del after['workflows'][deployment_id]
            del after['deployment_nodes'][deployment_id]
            del after['node_state'][deployment_id]
        for node_id in before['nodes'].keys():
            del after['nodes'][node_id]
        return after

    def upload_deploy_and_execute_install(self, blueprint_id=None,
                                          deployment_id=None):
        before_state = self.get_manager_state()
        self.cfy.upload_deploy_and_execute_install(
            str(self.blueprint_yaml),
            blueprint_id=blueprint_id or self.test_id,
            deployment_id=deployment_id or self.test_id,
        )
        after_state = self.get_manager_state()
        return before_state, after_state

    def execute_uninstall(self, deployment_id=None):
        self.cfy.execute_uninstall(deployment_id=deployment_id or self.test_id)

    def copy_blueprint(self, blueprint_dir_name):
        blueprint_path = path(self.workdir) / blueprint_dir_name
        shutil.copytree(get_blueprint_path(blueprint_dir_name),
                        str(blueprint_path))
        return blueprint_path
