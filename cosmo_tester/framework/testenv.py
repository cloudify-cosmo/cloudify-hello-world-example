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


import unittest
import logging
import sys
import shutil
import tempfile
import time
import copy
import os
import importlib
import json
from contextlib import contextmanager

import yaml
from path import path
import fabric.api
import fabric.context_managers

from cosmo_tester.framework.cfy_helper import (CfyHelper,
                                               DEFAULT_EXECUTE_TIMEOUT)
from cosmo_tester.framework.util import (get_blueprint_path,
                                         process_variables,
                                         YamlPatcher,
                                         generate_unique_configurations,
                                         create_rest_client)

from cloudify_rest_client.executions import Execution

root = logging.getLogger()
root.setLevel(logging.INFO)
ch = logging.StreamHandler(sys.stdout)
ch.setLevel(logging.INFO)
formatter = logging.Formatter(fmt='%(asctime)s [%(levelname)s] '
                                  '[%(name)s] %(message)s',
                              datefmt='%H:%M:%S')
ch.setFormatter(formatter)

# clear all other handlers
for logging_handler in root.handlers:
    root.removeHandler(logging_handler)

root.addHandler(ch)
logger = logging.getLogger('TESTENV')
logger.setLevel(logging.INFO)

HANDLER_CONFIGURATION = 'HANDLER_CONFIGURATION'
SUITES_YAML_PATH = 'SUITES_YAML_PATH'

test_environment = None


def initialize_without_bootstrap():
    logger.info('TestEnvironment initialize without bootstrap')
    global test_environment
    if not test_environment:
        test_environment = TestEnvironment()


def clear_environment():
    logger.info('TestEnvironment clear')
    global test_environment
    test_environment = None


def bootstrap(task_retries=5):
    logger.info('TestEnvironment initialize with bootstrap')
    global test_environment
    if not test_environment:
        test_environment = TestEnvironment()
        test_environment.bootstrap(task_retries)


def teardown():
    logger.info('TestEnvironment teardown')
    global test_environment
    if test_environment:
        try:
            logger.info('TestEnvironment teardown - starting')
            test_environment.teardown()
        finally:
            clear_environment()


# Singleton class
class TestEnvironment(object):
    # Singleton class
    def __init__(self):
        self._initial_cwd = os.getcwd()
        self._global_cleanup_context = None
        self._management_running = False
        self.rest_client = None
        self.management_ip = None
        self.handler = None
        self._manager_blueprint_path = None
        self._workdir = tempfile.mkdtemp(prefix='cloudify-testenv-')

        if HANDLER_CONFIGURATION not in os.environ:
            raise RuntimeError('handler configuration name must be configured '
                               'in "HANDLER_CONFIGURATION" env variable')
        handler_configuration = os.environ[HANDLER_CONFIGURATION]
        suites_yaml_path = os.environ.get(
            SUITES_YAML_PATH,
            path(__file__).dirname().dirname().dirname() / 'suites' /
            'suites' / 'suites.yaml')
        with open(suites_yaml_path) as f:
            self.suites_yaml = yaml.load(f.read())
        if os.path.exists(os.path.expanduser(handler_configuration)):
            configuration_path = os.path.expanduser(handler_configuration)
            with open(configuration_path) as f:
                self.handler_configuration = yaml.load(f.read())
        else:
            self.handler_configuration = self.suites_yaml[
                'handler_configurations'][handler_configuration]

        self.cloudify_config_path = path(os.path.expanduser(
            self.handler_configuration['inputs']))

        if not self.cloudify_config_path.isfile():
            raise RuntimeError('config file configured in handler '
                               'configuration does not seem to exist: {0}'
                               .format(self.cloudify_config_path))

        if 'manager_blueprint' not in self.handler_configuration:
            raise RuntimeError(
                'manager blueprint must be configured in handler '
                'configuration')

        manager_blueprint = self.handler_configuration['manager_blueprint']
        self._manager_blueprint_path = os.path.expanduser(
            manager_blueprint)

        # make a temp config files than can be modified freely
        self._generate_unique_configurations()

        with YamlPatcher(self._manager_blueprint_path) as patch:
            manager_blueprint_override = process_variables(
                self.suites_yaml,
                self.handler_configuration.get(
                    'manager_blueprint_override', {}))
            for key, value in manager_blueprint_override.items():
                patch.set_value(key, value)

        handler = self.handler_configuration['handler']
        try:
            handler_module = importlib.import_module(
                'system_tests.{0}'.format(handler))
        except ImportError:
            handler_module = importlib.import_module(
                'suites.helpers.handlers.{0}.handler'.format(handler))
        handler_class = handler_module.handler
        self.handler = handler_class(self)

        self.cloudify_config = yaml.load(self.cloudify_config_path.text())
        self._config_reader = self.handler.CloudifyConfigReader(
            self.cloudify_config,
            manager_blueprint_path=self._manager_blueprint_path)
        with self.handler.update_cloudify_config() as patch:
            processed_inputs = process_variables(
                self.suites_yaml,
                self.handler_configuration.get('inputs_override', {}))
            for key, value in processed_inputs.items():
                patch.set_value(key, value)

        if 'manager_ip' in self.handler_configuration:
            self._running_env_setup(self.handler_configuration['manager_ip'])

        self.install_plugins = self.handler_configuration.get(
            'install_manager_blueprint_dependencies', True)

        if self.handler_configuration.get('clean_env_on_init', False) is True:
            logger.info('Cleaning environment on init..')
            self.handler.CleanupContext.clean_all(self)

        global test_environment
        test_environment = self

    def _generate_unique_configurations(self):
        inputs_path, manager_blueprint_path = generate_unique_configurations(
            workdir=self._workdir,
            original_inputs_path=self.cloudify_config_path,
            original_manager_blueprint_path=self._manager_blueprint_path)
        self.cloudify_config_path = inputs_path
        self._manager_blueprint_path = manager_blueprint_path

    def setup(self):
        os.chdir(self._initial_cwd)
        return self

    def bootstrap(self, task_retries=5):
        if self._management_running:
            return

        self._global_cleanup_context = self.handler.CleanupContext(
            'testenv', self)

        cfy = CfyHelper(cfy_workdir=self._workdir)

        self.handler.before_bootstrap()
        cfy.bootstrap(
            self._manager_blueprint_path,
            inputs_file=self.cloudify_config_path,
            install_plugins=self.install_plugins,
            keep_up_on_failure=False,
            task_retries=task_retries,
            verbose=True)
        self._running_env_setup(cfy.get_management_ip())
        self.handler.after_bootstrap(cfy.get_provider_context())

    def teardown(self):
        if self._global_cleanup_context is None:
            return
        self.setup()
        cfy = CfyHelper(cfy_workdir=self._workdir)
        try:
            cfy.use(self.management_ip)
            cfy.teardown(verbose=True)
        finally:
            self._global_cleanup_context.cleanup()
            self.handler.after_teardown()
            if os.path.exists(self._workdir):
                shutil.rmtree(self._workdir)

    def _running_env_setup(self, management_ip):
        self.management_ip = management_ip
        self.rest_client = create_rest_client(management_ip)
        response = self.rest_client.manager.get_status()
        if not response['status'] == 'running':
            raise RuntimeError('Manager at {0} is not running.'
                               .format(self.management_ip))
        self._management_running = True

    def __getattr__(self, item):
        """Every attribute access on this env (usually from tests doing
        self.env, has the following semantics:
        First if env contains this attribute, use it, then
        if the handler has this attribute configured on it (this also includes
        handler_properties configured in the handler configuration), then
        use that, finally, check this attribute in the config reader.
        only then fail
        """

        if hasattr(self.handler, item):
            return getattr(self.handler, item)
        elif hasattr(self._config_reader, item):
            return getattr(self._config_reader, item)
        else:
            raise AttributeError(
                'Property \'{0}\' was not found in env'.format(item))


class TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pass

    @classmethod
    def tearDownClass(cls):
        pass

    def wait_until_deployment_ready_and_execute_install(self,
                                                        deployment_id,
                                                        inputs):
        self.wait_until_all_deployment_executions_end(deployment_id)
        return self.execute_install(deployment_id=deployment_id)

    def wait_until_all_deployment_executions_end(
            self,
            deployment_id=None,
            include_system_workflows=False):
        if deployment_id:
            msg = "Waiting for executions on " \
                  "deployment {0} to finish".format(deployment_id)
        else:
            msg = "Waiting for system wide executions to finish"
        if include_system_workflows:
            msg = "{0}, including system workflows.".format(msg)
        self.logger.info(msg)

        start_time = time.time()
        while len([execution for execution in self.client.executions.list(
                deployment_id=deployment_id,
                include_system_workflows=include_system_workflows)
                if execution["status"] not in Execution.END_STATES]) > 0:
            time.sleep(1)
            if start_time - time.time() > DEFAULT_EXECUTE_TIMEOUT:
                if deployment_id:
                    timeout_msg = "Timeout while waiting for " \
                                  "executions to end " \
                                  "on deployment {0}.".format(deployment_id)
                else:
                    timeout_msg = "Timeout while waiting for " \
                                  "system wide executions to end."
                raise Exception(timeout_msg)
        return

    def assert_outputs(self, expected_outputs, deployment_id=None):
        if deployment_id is None:
            deployment_id = self.test_id
        outputs = self.client.deployments.outputs.get(deployment_id)
        outputs = outputs['outputs']
        self.assertEqual(expected_outputs, outputs)

    def setUp(self):
        global test_environment
        self.env = test_environment.setup()
        self.logger = logging.getLogger(self._testMethodName)
        self.logger.setLevel(logging.INFO)
        self.logger.info('Starting test setUp')
        self.workdir = tempfile.mkdtemp(prefix='cosmo-test-')
        self.cfy = CfyHelper(cfy_workdir=self.workdir,
                             management_ip=self.env.management_ip)
        self.client = self.env.rest_client
        self.test_id = 'system-test-{0}-{1}'.format(
            self._testMethodName,
            time.strftime("%Y%m%d-%H%M"))
        self.blueprint_yaml = None
        self._test_cleanup_context = self.env.handler.CleanupContext(
            self._testMethodName, self.env)
        # register cleanup
        self.addCleanup(self._cleanup)
        self.maxDiff = 1024 * 1024 * 10

    def _cleanup(self):
        self.env.setup()
        self._test_cleanup_context.cleanup()
        shutil.rmtree(self.workdir)

    def tearDown(self):
        self.logger.info('Starting test tearDown')
        # note that the cleanup function is registered in setUp
        # because it is called regardless of whether setUp succeeded or failed
        # unlike tearDown which is not called when setUp fails (which might
        # happen when tests override setUp)

    def get_manager_state(self):
        self.logger.info('Fetching manager current state')
        blueprints = {}
        for blueprint in self.client.blueprints.list():
            blueprints[blueprint.id] = blueprint
        deployments = {}
        for deployment in self.client.deployments.list():
            deployments[deployment.id] = deployment
        nodes = {}
        for deployment_id in deployments.keys():
            for node in self.client.node_instances.list(deployment_id):
                nodes[node.id] = node
        deployment_nodes = {}
        node_state = {}
        for deployment_id in deployments.keys():
            deployment_nodes[deployment_id] = self.client.node_instances.list(
                deployment_id).items
            node_state[deployment_id] = {}
            for node in deployment_nodes[deployment_id]:
                node_state[deployment_id][node.id] = node

        return {
            'blueprints': blueprints,
            'deployments': deployments,
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
            del after['deployment_nodes'][deployment_id]
            del after['node_state'][deployment_id]
        for node_id in before['nodes'].keys():
            del after['nodes'][node_id]
        return after

    def execute_install(self,
                        deployment_id=None,
                        fetch_state=True):
        self.logger.info("attempting to execute install on deployment {0}"
                         .format(deployment_id))
        return self._make_operation_with_before_after_states(
            self.cfy.execute_install,
            fetch_state,
            deployment_id=deployment_id)

    def upload_deploy_and_execute_install(
            self,
            blueprint_id=None,
            deployment_id=None,
            fetch_state=True,
            execute_timeout=DEFAULT_EXECUTE_TIMEOUT,
            inputs=None):

        return self._make_operation_with_before_after_states(
            self.cfy.upload_deploy_and_execute_install,
            fetch_state,
            str(self.blueprint_yaml),
            blueprint_id=blueprint_id or self.test_id,
            deployment_id=deployment_id or self.test_id,
            execute_timeout=execute_timeout,
            inputs=inputs)

    def upload_blueprint(
            self,
            blueprint_id):
        self.logger.info("attempting to upload blueprint {0}"
                         .format(blueprint_id))
        return self.cfy.upload_blueprint(
            blueprint_id=blueprint_id,
            blueprint_path=str(self.blueprint_yaml))

    def create_deployment(
            self,
            blueprint_id,
            deployment_id,
            inputs):
        self.logger.info("attempting to create_deployment deployment {0}"
                         .format(deployment_id))
        return self.cfy.create_deployment(
            blueprint_id=blueprint_id,
            deployment_id=deployment_id,
            inputs=inputs)

    def _make_operation_with_before_after_states(self, operation, fetch_state,
                                                 *args, **kwargs):
        before_state = None
        after_state = None
        if fetch_state:
            before_state = self.get_manager_state()
        operation(*args, **kwargs)
        if fetch_state:
            after_state = self.get_manager_state()
        return before_state, after_state

    def execute_uninstall(self, deployment_id=None, cfy=None):
        cfy = cfy or self.cfy
        cfy.execute_uninstall(deployment_id=deployment_id or self.test_id)

    def copy_blueprint(self, blueprint_dir_name, blueprints_dir=None):
        blueprint_path = path(self.workdir) / blueprint_dir_name
        shutil.copytree(get_blueprint_path(blueprint_dir_name, blueprints_dir),
                        str(blueprint_path))
        return blueprint_path

    def wait_for_execution(self, execution, timeout, client=None,
                           assert_success=True):
        def dump_events(_client, _execution):
            events, _ = _client.events.get(_execution.id,
                                           batch_size=1000,
                                           include_logs=True)
            self.logger.info('Deployment creation events & logs:')
            for event in events:
                self.logger.info(json.dumps(event))
        client = client or self.client
        end = time.time() + timeout
        while time.time() < end:
            status = client.executions.get(execution.id).status
            if status == 'failed':
                if assert_success:
                    dump_events(client, execution)
                    raise AssertionError('Execution "{}" failed'.format(
                        execution.id))
                else:
                    return
            if status == 'terminated':
                return
            time.sleep(1)
        dump_events(client, execution)
        raise AssertionError('Execution "{}" timed out'.format(execution.id))

    def repetitive(self, func, timeout=10, exception_class=Exception,
                   args=None, kwargs=None):
        args = args or []
        kwargs = kwargs or {}
        deadline = time.time() + timeout
        while True:
            try:
                return func(*args, **kwargs)
            except exception_class:
                if time.time() > deadline:
                    raise
                time.sleep(1)

    @contextmanager
    def manager_env_fabric(self, **kwargs):
        with fabric.context_managers.settings(
                host_string=self.cfy.get_management_ip(),
                user=self.env.management_user_name,
                key_filename=self.env.management_key_path,
                **kwargs):
            yield fabric.api

    def run_commands_on_agent_host(self,
                                   user,
                                   commands,
                                   deployment_id=None,
                                   compute_node_id=None,
                                   compute_node_instance_id=None):
        if not (compute_node_id or compute_node_instance_id):
            self.fail('no node_id or node_instance_id')
        deployment_id = deployment_id or self.test_id
        filters = {'deployment_id': deployment_id}
        if compute_node_id:
            filters['node_id'] = compute_node_id
        if compute_node_instance_id:
            filters['id'] = compute_node_instance_id
        computes = self.client.node_instances.list(**filters).items
        if not computes:
            self.fail('No compute nodes were found')
        if len(computes) > 1:
            self.fail('More than one instance found, please refine your query:'
                      ' {0}'.format(computes))
        compute = computes[0]
        private_ip = compute.runtime_properties['ip']
        with self.manager_env_fabric() as api:
            api.sudo('ssh '
                     '-o UserKnownHostsFile=/dev/null '
                     '-o StrictHostKeyChecking=no '
                     '-t -i /root/.ssh/agent_key.pem {0}@{1} "{2}"'
                     .format(user, private_ip, ' && '.join(commands)))

    def wait_for_resource(self, predicate_func, timeout_sec=60):
        timeout = time.time() + timeout_sec
        while True:
            if time.time() > timeout:
                raise RuntimeError('Failed waiting for resource')
            try:
                result = predicate_func()
                if result:
                    break
            except Exception as e:
                logger.info('predicate function raised an error; {error}'
                            .format(error=e))
            time.sleep(1)
