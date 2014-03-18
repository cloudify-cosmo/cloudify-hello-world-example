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
import copy
import uuid

from path import path
from cosmo_manager_rest_client.cosmo_manager_rest_client import (
    CosmoManagerRestClient)

from cosmo_tester.framework import cfy_helper
from cosmo_tester.framework.util import (get_blueprint_path,
                                         Singleton,
                                         CloudifyConfigReader)

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


class TestEnvironment(object):
    __metaclass__ = Singleton

    def __init__(self):
        self.cloudify_config_path = \
            '/home/dan/work/cfy-openstack/cloudify-config.yaml'
        self.management_ip = '192.168.15.15'
        self._config_reader = CloudifyConfigReader(self.cloudify_config_path)
        self.rest_client = CosmoManagerRestClient(self.management_ip)

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


class TestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        pass

    @classmethod
    def tearDownClass(cls):
        pass

    def setUp(self):
        self.env = TestEnvironment()
        self.logger = logging.getLogger(self._testMethodName)
        self.logger.setLevel(logging.INFO)
        self.workdir = tempfile.mkdtemp(prefix='cosmo-test-')
        self.cfy = cfy_helper.CfyHelper(cfy_workdir=self.workdir,
                                        management_ip=self.env.management_ip)
        self.rest = self.env.rest_client
        self.test_id = uuid.uuid4()
        self.blueprint_yaml = None

    def tearDown(self):
        shutil.rmtree(self.workdir)

    def bootstrap(self):
        self.cfy.bootstrap(
            self.env.cloudify_config_path,
            keep_up_on_failure=True,
            verbose=True,
            dev_mode=False,
            alternate_bootstrap_method=True
        )

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

    def upload_deploy_and_execute_install(self):
        before_state = self.get_manager_state()
        self.cfy.upload_deploy_and_execute_install(
            str(self.blueprint_yaml),
            blueprint_id=self.test_id,
            deployment_id=self.test_id,
        )
        after_state = self.get_manager_state()
        return before_state, after_state

    def execute_uninstall(self):
        self.cfy.execute_uninstall(deployment_id=self.test_id)

    def copy_blueprint(self, blueprint_dir_name):
        blueprint_path = path(self.workdir) / blueprint_dir_name
        shutil.copytree(get_blueprint_path(blueprint_dir_name),
                        str(blueprint_path))
        return blueprint_path
