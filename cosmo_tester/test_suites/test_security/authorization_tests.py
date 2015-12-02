########
# Copyright (c) 2015 GigaSpaces Technologies Ltd. All rights reserved
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
#

import contextlib
from cStringIO import StringIO
import os
import sys

from sh import ErrorReturnCode

from cloudify_rest_client.client import CloudifyClient
from cosmo_tester.framework import util
from cosmo_tester.test_suites.test_security import security_test_base


ADMIN_USERNAME = 'alice'
ADMIN_PASSWORD = 'alice_password'
DEPLOYER_USERNAME = 'bob'
DEPLOYER_PASSWORD = 'bob_password'
VIEWER_USERNAME = 'clair'
VIEWER_PASSWORD = 'clair_password'
NO_ROLE_USERNAME = 'dave'
NO_ROLE_PASSWORD = 'dave_password'

security_test_base.TEST_CFY_USERNAME = ADMIN_USERNAME
security_test_base.TEST_CFY_PASSWORD = ADMIN_PASSWORD

RUNNING_EXECUTIONS_MESSAGE = 'There are running executions for this deployment'
UNAUTHORIZED_ERROR_MESSAGE = '401: user unauthorized'


class AuthorizationTests(security_test_base.SecurityTestBase):

    def setUp(self):
        super(AuthorizationTests, self).setUp()
        self.setup_secured_manager()
        self.blueprints_dir = self.copy_blueprint('mocks')
        self.blueprint_path = self.blueprints_dir / 'empty-blueprint.yaml'
        self.blueprint_yaml = self.blueprint_path

    def test_authorization(self):
        self._test_blueprint_operations()
        self._test_deployment_operations()
        self._test_execution_operations()

    def _test_blueprint_operations(self):
        blueprint_ids = self._test_upload_blueprint()
        self._test_list_blueprint(blueprint_ids)
        self._test_get_blueprint(blueprint_ids[0])
        self._test_delete_blueprint(blueprint_ids[0])

        # cleanup
        self._login(ADMIN_USERNAME, ADMIN_PASSWORD)
        # item 0 has already been deleted in _test_delete_blueprint
        for blueprint_id in blueprint_ids[1:]:
            self.cfy.delete_blueprint(blueprint_id)

    def _test_deployment_operations(self):
        blueprint_id = 'test_deployment_blueprint1'
        # setup
        self._login(ADMIN_USERNAME, ADMIN_PASSWORD)
        self.cfy.upload_blueprint(blueprint_id, self.blueprint_path)

        # test
        deployment_ids = self._test_create_deployment(blueprint_id)
        self._test_list_deployment(deployment_ids)
        self._test_delete_deployment(deployment_ids)

        # cleanup
        self._login(ADMIN_USERNAME, ADMIN_PASSWORD)
        # item 0 has already been deleted in _test_delete_deployment
        for deployment_id in deployment_ids[1:]:
            self.cfy.delete_deployment(deployment_id)
        self.cfy.delete_blueprint(blueprint_id)

    def _test_execution_operations(self):
        blueprint_id = 'test_execution_blueprint1'
        deployment_ids = ['test_execution_deployment1',
                          'test_execution_deployment2',
                          'test_execution_deployment3']
        # setup
        self._login(ADMIN_USERNAME, ADMIN_PASSWORD)
        self.cfy.upload_blueprint(blueprint_id, self.blueprint_path)
        for deployment_id in deployment_ids:
            self.cfy.create_deployment(blueprint_id, deployment_id)
            self.wait_until_all_deployment_executions_end(deployment_id)

        # test
        self._test_start_execution(deployment_ids)
        execution_ids = self._get_execution_ids()
        self._test_list_executions(execution_ids)
        self._test_get_execution(execution_ids[0])
        self._test_cancel_executions(execution_id1=execution_ids[0],
                                     execution_id2=execution_ids[1])

        # cleanup
        self._login(ADMIN_USERNAME, ADMIN_PASSWORD)
        for deployment_id in deployment_ids:
            self.wait_until_all_deployment_executions_end(deployment_id)
            self.cfy.delete_deployment(deployment_id, ignore_live_nodes=True)
        self.cfy.delete_blueprint(blueprint_id)

    ##############################
    # blueprint tests
    ##############################
    def _test_upload_blueprint(self):

        def _upload_and_assert(blueprint_id):
            out, err = self._execute_and_get_streams(self.cfy.upload_blueprint,
                                                     blueprint_id,
                                                     self.blueprint_path)
            self._assert_in_output(out, 'Uploaded blueprint')
            self.assertEqual('', err)

        # admins and deployers should be able to upload blueprints...
        blueprint1_id = 'blueprint1_id'
        blueprint2_id = 'blueprint2_id'

        self._login(ADMIN_USERNAME, ADMIN_PASSWORD)
        _upload_and_assert(blueprint1_id)

        self._login(DEPLOYER_USERNAME, DEPLOYER_PASSWORD)
        _upload_and_assert(blueprint2_id)

        # ...but viewers and simple users should not
        self._login(VIEWER_USERNAME, VIEWER_PASSWORD)
        self._assert_unauthorized(self.cfy.upload_blueprint,
                                  'dummy_bp',
                                  self.blueprint_path)

        self._login(NO_ROLE_USERNAME, NO_ROLE_PASSWORD)
        self._assert_unauthorized(self.cfy.upload_blueprint,
                                  'dummy_bp',
                                  self.blueprint_path)

        return blueprint1_id, blueprint2_id

    def _test_list_blueprint(self, blueprint_ids):

        def _list_and_assert():
            out, err = self._execute_and_get_streams(self.cfy.list_blueprints)
            self._assert_in_output(out, *blueprint_ids)
            self.assertEqual('', err)

        # admins, deployers and viewers should be able to list blueprints...
        self._login(ADMIN_USERNAME, ADMIN_PASSWORD)
        _list_and_assert()

        self._login(DEPLOYER_USERNAME, DEPLOYER_PASSWORD)
        _list_and_assert()

        self._login(VIEWER_USERNAME, VIEWER_PASSWORD)
        _list_and_assert()

        # ...but simple users should not
        self._login(NO_ROLE_USERNAME, NO_ROLE_PASSWORD)
        self._assert_unauthorized(self.cfy.list_blueprints)

    def _test_get_blueprint(self, blueprint_id):

        def _get_and_assert():
            out, err = self._execute_and_get_streams(
                self.cfy.get_blueprint, blueprint_id)
            self._assert_in_output(out, blueprint_id)
            self.assertEqual('', err)

        # admins, deployers and viewers should be able to get blueprints...
        self._login(ADMIN_USERNAME, ADMIN_PASSWORD)
        _get_and_assert()

        self._login(DEPLOYER_USERNAME, DEPLOYER_PASSWORD)
        _get_and_assert()

        self._login(VIEWER_USERNAME, VIEWER_PASSWORD)
        _get_and_assert()

        # ...but simple users should not
        self._login(NO_ROLE_USERNAME, NO_ROLE_PASSWORD)
        self._assert_unauthorized(self.cfy.get_blueprint, blueprint_id)

    def _test_delete_blueprint(self, blueprint_id):

        def _delete_and_assert():
            out, err = self._execute_and_get_streams(
                self.cfy.delete_blueprint, blueprint_id)
            self._assert_in_output(out, 'Deleted blueprint successfully')
            self.assertEqual('', err)

        # admins should be able to delete blueprints...
        self._login(ADMIN_USERNAME, ADMIN_PASSWORD)
        _delete_and_assert()

        # ...but deployers, viewers and simple users should not
        self._login(DEPLOYER_USERNAME, DEPLOYER_PASSWORD)
        self._assert_unauthorized(self.cfy.delete_blueprint, blueprint_id)

        self._login(VIEWER_USERNAME, VIEWER_PASSWORD)
        self._assert_unauthorized(self.cfy.delete_blueprint, blueprint_id)

        self._login(NO_ROLE_USERNAME, NO_ROLE_PASSWORD)
        self._assert_unauthorized(self.cfy.delete_blueprint, blueprint_id)

    ##############################
    # deployment tests
    ##############################
    def _test_create_deployment(self, blueprint_id):

        def _create_and_assert(deployment_id):
            out, err = self._execute_and_get_streams(
                self.cfy.create_deployment, blueprint_id, deployment_id)
            self._assert_in_output(out, 'Deployment created')
            self.wait_until_all_deployment_executions_end(deployment_id)
            self.assertEqual('', err)

        # admins and deployers should be able to create deployments...
        deployment1_id = 'deployment1'
        deployment2_id = 'deployment2'
        self._login(ADMIN_USERNAME, ADMIN_PASSWORD)
        _create_and_assert(deployment1_id)
        self._login(DEPLOYER_USERNAME, DEPLOYER_PASSWORD)
        _create_and_assert(deployment2_id)

        # ...but viewers and simple users should not
        self._login(VIEWER_USERNAME, VIEWER_PASSWORD)
        self._assert_unauthorized(self.cfy.create_deployment,
                                  blueprint_id,
                                  'dummy_dp')

        self._login(NO_ROLE_USERNAME, NO_ROLE_PASSWORD)
        self._assert_unauthorized(self.cfy.create_deployment,
                                  blueprint_id,
                                  'dummy_dp')

        return deployment1_id, deployment2_id

    def _test_list_deployment(self, deployment_ids):

        def _list_and_assert():
            out, err = self._execute_and_get_streams(self.cfy.list_deployments)
            self._assert_in_output(out, *deployment_ids)
            self.assertEqual('', err)

        # admins, deployers and viewers should be able to list deployments...
        self._login(ADMIN_USERNAME, ADMIN_PASSWORD)
        _list_and_assert()

        self._login(DEPLOYER_USERNAME, DEPLOYER_PASSWORD)
        _list_and_assert()

        self._login(VIEWER_USERNAME, VIEWER_PASSWORD)
        _list_and_assert()

        # ...but simple users should not
        self._login(NO_ROLE_USERNAME, NO_ROLE_PASSWORD)
        self._assert_unauthorized(self.cfy.list_deployments)

    def _test_delete_deployment(self, deployment_ids):

        def _delete_and_assert():
            out, err = self._execute_and_get_streams(
                self.cfy.delete_deployment, deployment_ids[0])
            self._assert_in_output(out, 'Deleted deployment successfully')
            self.assertEqual('', err)

        # admins should be able to delete deployments...
        self._login(ADMIN_USERNAME, ADMIN_PASSWORD)
        _delete_and_assert()

        # ...but deployers, viewers and simple users should not
        self._login(DEPLOYER_USERNAME, DEPLOYER_PASSWORD)
        self._assert_unauthorized(self.cfy.delete_deployment,
                                  deployment_ids[1])

        self._login(VIEWER_USERNAME, VIEWER_PASSWORD)
        self._assert_unauthorized(self.cfy.delete_deployment,
                                  deployment_ids[1])

        self._login(NO_ROLE_USERNAME, NO_ROLE_PASSWORD)
        self._assert_unauthorized(self.cfy.delete_deployment,
                                  deployment_ids[1])

    ##############################
    # execution tests
    ##############################
    def _test_start_execution(self, deployment_ids):
        workflow = 'install'

        def _start_and_assert(deployment_id):
            out, err = self._execute_and_get_streams(
                self.cfy.execute_workflow, workflow, deployment_id)
            self._assert_in_output(out, 'Finished executing workflow')
            self.assertEqual('', err)

        # admins and deployers should be able to start executions...
        self._login(ADMIN_USERNAME, ADMIN_PASSWORD)
        _start_and_assert(deployment_ids[0])

        self._login(DEPLOYER_USERNAME, DEPLOYER_PASSWORD)
        _start_and_assert(deployment_ids[1])

        # ...but viewers and simple users should not
        self._login(VIEWER_USERNAME, VIEWER_PASSWORD)
        self._assert_unauthorized(
            self.cfy.execute_workflow, workflow, deployment_ids[2])

        self._login(NO_ROLE_USERNAME, NO_ROLE_PASSWORD)
        self._assert_unauthorized(
            self.cfy.execute_workflow, workflow, deployment_ids[2])

    def _test_list_executions(self, execution_ids):

        def _list_and_assert():
            out, err = self._execute_and_get_streams(self.cfy.list_executions)
            self._assert_in_output(out, *execution_ids)
            self.assertEqual('', err)

        # admins, deployers and viewers should be able so list executions...
        self._login(ADMIN_USERNAME, ADMIN_PASSWORD)
        _list_and_assert()

        self._login(DEPLOYER_USERNAME, DEPLOYER_PASSWORD)
        _list_and_assert()

        self._login(VIEWER_USERNAME, VIEWER_PASSWORD)
        _list_and_assert()

        # ...but simple users should not
        self._login(NO_ROLE_USERNAME, NO_ROLE_PASSWORD)
        # self._assert_unauthorized(self.cfy.list_executions)
        # this is a temporary work around a bug in the cli: CFY-4339
        out, err = self._execute_and_get_streams(self.cfy.list_executions)
        self.assertIn('Deployment None does not exist', out)
        self.assertEqual('', err)

    def _test_get_execution(self, execution_id):

        def _get_and_assert():
            out, err = self._execute_and_get_streams(
                self.cfy.get_execution, execution_id)
            self._assert_in_output(out, execution_id)
            self.assertEqual('', err)

        # admins, deployers and viewers should be able to get executions...
        self._login(ADMIN_USERNAME, ADMIN_PASSWORD)
        _get_and_assert()

        self._login(DEPLOYER_USERNAME, DEPLOYER_PASSWORD)
        _get_and_assert()

        self._login(VIEWER_USERNAME, VIEWER_PASSWORD)
        _get_and_assert()

        # ...but simple users should not
        self._login(NO_ROLE_USERNAME, NO_ROLE_PASSWORD)
        self._assert_unauthorized(self.cfy.get_execution, execution_id)

    def _test_cancel_executions(self, execution_id1, execution_id2):

        def _cancel_and_assert(execution_id):
            out, err = self._execute_and_get_streams(
                self.cfy.cancel_execution, execution_id)
            cancelling_msg = 'A cancel request for execution {0} has been' \
                             ' sent'.format(execution_id)
            already_terminated_msg = 'in status terminated'
            if cancelling_msg not in out and already_terminated_msg not in out:
                self.fail('failed to cancel execution {0}, output: {1}'.
                          format(execution_id, out))
            self.assertEqual('', err)

        # admins and deployers should be able to cancel executions...
        self._login(ADMIN_USERNAME, ADMIN_PASSWORD)
        _cancel_and_assert(execution_id1)

        self._login(DEPLOYER_USERNAME, DEPLOYER_PASSWORD)
        _cancel_and_assert(execution_id2)

        # ...but viewers and simple users should not
        self._login(VIEWER_USERNAME, VIEWER_PASSWORD)
        self._assert_unauthorized(self.cfy.cancel_execution, execution_id1)

        self._login(NO_ROLE_USERNAME, NO_ROLE_PASSWORD)
        self._assert_unauthorized(self.cfy.cancel_execution, execution_id1)

    ###############################
    # utility methods and wrappers
    ###############################
    @contextlib.contextmanager
    def _capture_streams(self):
        old_out = sys.stdout
        old_err = sys.stderr
        try:
            out, err = StringIO(), StringIO()
            sys.stdout = out
            sys.stderr = err
            yield out, err
        finally:
            sys.stdout = old_out
            sys.stderr = old_err

    def _execute_and_get_streams(self, method, *args):
        with self._capture_streams() as (out, err):
            try:
                method(*args)
            except ErrorReturnCode:
                pass

        return out.getvalue(), err.getvalue()

    def _assert_unauthorized(self, method, *args):
        out, err = self._execute_and_get_streams(method, *args)
        self.assertIn(UNAUTHORIZED_ERROR_MESSAGE, out)
        self.assertEqual('', err)

    def _assert_in_output(self, out, *output_values):
        for value in output_values:
            self.assertIn(value, out)

    @staticmethod
    def _login(username, password):
        os.environ['CLOUDIFY_USERNAME'] = username
        os.environ['CLOUDIFY_PASSWORD'] = password

    def _get_execution_ids(self):
        auth_header = util.get_auth_header(ADMIN_USERNAME, ADMIN_PASSWORD)
        alice_client = CloudifyClient(host=self.env.management_ip,
                                      headers=auth_header)
        return [execution.id for execution in alice_client.executions.list()]

    ############################################
    # overriding super class implementations
    ############################################
    def get_authorization_providers(self):
        return {
            'implementation': 'flask_securest.authorization_providers.'
                              'role_based_authorization_provider:'
                              'RoleBasedAuthorizationProvider',
            'properties': {
                'roles_config_file_path': '/opt/manager/roles_config.yaml',
                'role_loader': {
                    'implementation':
                        'flask_securest.authorization_providers.role_loaders.'
                        'simple_role_loader:SimpleRoleLoader'
                }
            }
        }

    def get_userstore_driver(self):
        return {
            'implementation':
                'flask_securest.userstores.simple:SimpleUserstore',
            'properties': {
                'userstore': {
                    'users': [
                        {
                            'username': ADMIN_USERNAME,
                            'password': ADMIN_PASSWORD,
                            'groups': ['cfy_admins']
                        },
                        {
                            'username': DEPLOYER_USERNAME,
                            'password': DEPLOYER_PASSWORD,
                            'groups': ['managers', 'users']
                        },
                        {
                            'username': VIEWER_USERNAME,
                            'password': VIEWER_PASSWORD,
                            'groups': ['users'],
                            'roles': ['viewer']
                        },
                        {
                            'username': NO_ROLE_USERNAME,
                            'password': NO_ROLE_PASSWORD,
                            'groups': ['users']
                        }
                    ],
                    'groups': [
                        {
                            'name': 'cfy_admins',
                            'roles': ['administrator']
                        },
                        {
                            'name': 'managers',
                            'roles': ['deployer', 'viewer']
                        },
                        {
                            'name': 'users',
                            'roles': []
                        }
                    ]
                }
            }
        }
