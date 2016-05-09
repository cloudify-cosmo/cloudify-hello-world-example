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
from cloudify_rest_client.exceptions import UserUnauthorizedError
from cosmo_tester.framework import util
from cosmo_tester.test_suites.test_security import security_test_base


RUNNING_EXECUTIONS_MESSAGE = 'There are running executions for this deployment'


class BaseAuthTest(security_test_base.SecurityTestBase):

    admin_username = 'alice'
    admin_password = 'alice_password'
    deployer_username = 'bob'
    deployer_password = 'bob_password'
    viewer_username = 'clair'
    viewer_password = 'clair_password'
    no_role_username = 'dave'
    no_role_password = 'dave_password'

    def _test_authentication_and_authorization(self, assert_token=None):
        self._test_authentication(assert_token=assert_token)
        self._test_authorization()

    def _test_authorization(self):
        # setup temp blueprint
        self.blueprints_dir = self.copy_mocks_blueprints_dir()
        self.blueprint_path = '{0}/empty-blueprint.yaml'\
                              .format(self.blueprints_dir)
        self.blueprint_yaml = self.blueprint_path

        # start authorization assertions
        self._assert_blueprint_operations()
        self._assert_deployment_operations()
        self._assert_execution_operations()

    def copy_mocks_blueprints_dir(self):
        dest_path = '{0}/{1}'.format(self.workdir, 'mocks')
        if not os.path.exists(dest_path):
            dest_path = self.copy_blueprint('mocks')
        return dest_path

    def _test_authentication(self, assert_token=None):
        self._assert_valid_credentials_authenticate()
        self._assert_invalid_credentials_fails()
        self._assert_empty_credentials_fails()
        self._assert_no_credentials_or_token_fails()
        if assert_token:
            self._assert_valid_token_authenticates()
            self._assert_invalid_token_fails()
            self._assert_empty_token_fails()

    def _assert_blueprint_operations(self):
        blueprint_ids = self._assert_upload_blueprint()
        self._assert_list_blueprint(blueprint_ids)
        self._assert_get_blueprint(blueprint_ids[0])
        self._assert_delete_blueprint(blueprint_ids[0])

        # cleanup
        self._login_cli(self.admin_username, self.admin_password)
        # item 0 has already been deleted in _assert_delete_blueprint
        for blueprint_id in blueprint_ids[1:]:
            self.cfy.delete_blueprint(blueprint_id)

    def _assert_deployment_operations(self):
        blueprint_id = 'test_deployment_blueprint1'
        # setup
        self._login_cli(self.admin_username, self.admin_password)
        self.cfy.upload_blueprint(blueprint_id, self.blueprint_path)

        # test
        deployment_ids = self._assert_create_deployment(blueprint_id)
        self._assert_list_deployment(deployment_ids)
        self._assert_delete_deployment(deployment_ids)

        # cleanup
        self._login_cli(self.admin_username, self.admin_password)
        # item 0 has already been deleted in _assert_delete_deployment
        for deployment_id in deployment_ids[1:]:
            self.cfy.delete_deployment(deployment_id)
        self.cfy.delete_blueprint(blueprint_id)

    def _assert_execution_operations(self):
        blueprint_id = 'test_execution_blueprint1'
        deployment_ids = ['test_execution_deployment1',
                          'test_execution_deployment2',
                          'test_execution_deployment3']
        # setup
        self._login_cli(self.admin_username, self.admin_password)
        self.cfy.upload_blueprint(blueprint_id, self.blueprint_path)
        for deployment_id in deployment_ids:
            self.cfy.create_deployment(blueprint_id, deployment_id)
            self.wait_until_all_deployment_executions_end(
                deployment_id=deployment_id,
                verify_no_failed_execution=True)

        # test
        self._assert_start_execution(deployment_ids)
        execution_ids = self._get_execution_ids()
        self._assert_list_executions(execution_ids)
        self._assert_get_execution(execution_ids[0])
        self._assert_cancel_executions(execution_id1=execution_ids[0],
                                       execution_id2=execution_ids[1])

        # cleanup
        self._login_cli(self.admin_username, self.admin_password)
        for deployment_id in deployment_ids:
            self.wait_until_all_deployment_executions_end(deployment_id)
            self.cfy.delete_deployment(deployment_id, ignore_live_nodes=True)
        self.cfy.delete_blueprint(blueprint_id)

    ##############################
    # blueprint tests
    ##############################
    def _assert_upload_blueprint(self):

        def _upload_and_assert(blueprint_id):
            out, err = self._execute_and_get_streams(self.cfy.upload_blueprint,
                                                     blueprint_id,
                                                     self.blueprint_path)
            self._assert_in_output(out, 'Uploaded blueprint')
            self.assertEqual('', err)

        # admins and deployers should be able to upload blueprints...
        blueprint1_id = 'blueprint1_id'
        blueprint2_id = 'blueprint2_id'

        self._login_cli(self.admin_username, self.admin_password)
        _upload_and_assert(blueprint1_id)

        self._login_cli(self.deployer_username, self.deployer_password)
        _upload_and_assert(blueprint2_id)

        # ...but viewers and simple users should not
        self._login_cli(self.viewer_username, self.viewer_password)
        self._assert_unauthorized(self.cfy.upload_blueprint,
                                  'dummy_bp',
                                  self.blueprint_path)

        self._login_cli(self.no_role_username, self.no_role_password)
        self._assert_unauthorized(self.cfy.upload_blueprint,
                                  'dummy_bp',
                                  self.blueprint_path)

        return blueprint1_id, blueprint2_id

    def _assert_list_blueprint(self, blueprint_ids):

        def _list_and_assert():
            out, err = self._execute_and_get_streams(self.cfy.list_blueprints)
            self._assert_in_output(out, *blueprint_ids)
            self.assertEqual('', err)

        # admins, deployers and viewers should be able to list blueprints...
        self._login_cli(self.admin_username, self.admin_password)
        _list_and_assert()

        self._login_cli(self.deployer_username, self.deployer_password)
        _list_and_assert()

        self._login_cli(self.viewer_username, self.viewer_password)
        _list_and_assert()

        # ...but simple users should not
        self._login_cli(self.no_role_username, self.no_role_password)
        self._assert_unauthorized(self.cfy.list_blueprints)

    def _assert_get_blueprint(self, blueprint_id):

        def _get_and_assert():
            out, err = self._execute_and_get_streams(
                self.cfy.get_blueprint, blueprint_id)
            self._assert_in_output(out, blueprint_id)
            self.assertEqual('', err)

        # admins, deployers and viewers should be able to get blueprints...
        self._login_cli(self.admin_username, self.admin_password)
        _get_and_assert()

        self._login_cli(self.deployer_username, self.deployer_password)
        _get_and_assert()

        self._login_cli(self.viewer_username, self.viewer_password)
        _get_and_assert()

        # ...but simple users should not
        self._login_cli(self.no_role_username, self.no_role_password)
        self._assert_unauthorized(self.cfy.get_blueprint, blueprint_id)

    def _assert_delete_blueprint(self, blueprint_id):

        def _delete_and_assert():
            out, err = self._execute_and_get_streams(
                self.cfy.delete_blueprint, blueprint_id)
            self._assert_in_output(out, 'Deleted blueprint successfully')
            self.assertEqual('', err)

        # admins should be able to delete blueprints...
        self._login_cli(self.admin_username, self.admin_password)
        self._login_cli(self.admin_username, self.admin_password)
        _delete_and_assert()

        # ...but deployers, viewers and simple users should not
        self._login_cli(self.deployer_username, self.deployer_password)
        self._assert_unauthorized(self.cfy.delete_blueprint, blueprint_id)

        self._login_cli(self.viewer_username, self.viewer_password)
        self._assert_unauthorized(self.cfy.delete_blueprint, blueprint_id)

        self._login_cli(self.no_role_username, self.no_role_password)
        self._assert_unauthorized(self.cfy.delete_blueprint, blueprint_id)

    ##############################
    # deployment tests
    ##############################
    def _assert_create_deployment(self, blueprint_id):

        def _create_and_assert(deployment_id):
            out, err = self._execute_and_get_streams(
                self.cfy.create_deployment, blueprint_id, deployment_id)
            self._assert_in_output(out, 'Deployment created')

            # polling for deployments requires an authorized client
            self._login_client(username=self.admin_username,
                               password=self.admin_password)
            self.wait_until_all_deployment_executions_end(deployment_id)
            self.assertEqual('', err)

        # admins and deployers should be able to create deployments...
        deployment1_id = 'deployment1'
        deployment2_id = 'deployment2'
        self._login_cli(self.admin_username, self.admin_password)
        _create_and_assert(deployment1_id)
        self._login_cli(self.deployer_username, self.deployer_password)
        _create_and_assert(deployment2_id)

        # ...but viewers and simple users should not
        self._login_cli(self.viewer_username, self.viewer_password)
        self._assert_unauthorized(self.cfy.create_deployment,
                                  blueprint_id,
                                  'dummy_dp')

        self._login_cli(self.no_role_username, self.no_role_password)
        self._assert_unauthorized(self.cfy.create_deployment,
                                  blueprint_id,
                                  'dummy_dp')

        return deployment1_id, deployment2_id

    def _assert_list_deployment(self, deployment_ids):

        def _list_and_assert():
            out, err = self._execute_and_get_streams(self.cfy.list_deployments)
            self._assert_in_output(out, *deployment_ids)
            self.assertEqual('', err)

        # admins, deployers and viewers should be able to list deployments...
        self._login_cli(self.admin_username, self.admin_password)
        _list_and_assert()

        self._login_cli(self.deployer_username, self.deployer_password)
        _list_and_assert()

        self._login_cli(self.viewer_username, self.viewer_password)
        _list_and_assert()

        # ...but simple users should not
        self._login_cli(self.no_role_username, self.no_role_password)
        self._assert_unauthorized(self.cfy.list_deployments)

    def _assert_delete_deployment(self, deployment_ids):

        def _delete_and_assert():
            out, err = self._execute_and_get_streams(
                self.cfy.delete_deployment, deployment_ids[0])
            self._assert_in_output(out, 'Deleted deployment successfully')
            self.assertEqual('', err)

        # admins should be able to delete deployments...
        self._login_cli(self.admin_username, self.admin_password)
        _delete_and_assert()

        # ...but deployers, viewers and simple users should not
        self._login_cli(self.deployer_username, self.deployer_password)
        self._assert_unauthorized(self.cfy.delete_deployment,
                                  deployment_ids[1])

        self._login_cli(self.viewer_username, self.viewer_password)
        self._assert_unauthorized(self.cfy.delete_deployment,
                                  deployment_ids[1])

        self._login_cli(self.no_role_username, self.no_role_password)
        self._assert_unauthorized(self.cfy.delete_deployment,
                                  deployment_ids[1])

    ##############################
    # execution tests
    ##############################
    def _assert_start_execution(self, deployment_ids):
        workflow = 'install'

        def _start_and_assert(deployment_id):
            out, err = self._execute_and_get_streams(
                self.cfy.execute_workflow, workflow, deployment_id)
            self._assert_in_output(out, 'Finished executing workflow')
            self.assertEqual('', err)

        # admins and deployers should be able to start executions...
        self._login_cli(self.admin_username, self.admin_password)
        _start_and_assert(deployment_ids[0])

        self._login_cli(self.deployer_username, self.deployer_password)
        _start_and_assert(deployment_ids[1])

        # ...but viewers and simple users should not
        self._login_cli(self.viewer_username, self.viewer_password)
        self._assert_unauthorized(
            self.cfy.execute_workflow, workflow, deployment_ids[2])

        self._login_cli(self.no_role_username, self.no_role_password)
        self._assert_unauthorized(
            self.cfy.execute_workflow, workflow, deployment_ids[2])

    def _assert_list_executions(self, execution_ids):

        def _list_and_assert():
            out, err = self._execute_and_get_streams(self.cfy.list_executions)
            self._assert_in_output(out, *execution_ids)
            self.assertEqual('', err)

        # admins, deployers and viewers should be able so list executions...
        self._login_cli(self.admin_username, self.admin_password)
        _list_and_assert()

        self._login_cli(self.deployer_username, self.deployer_password)
        _list_and_assert()

        self._login_cli(self.viewer_username, self.viewer_password)
        _list_and_assert()

        # ...but simple users should not
        self._login_cli(self.no_role_username, self.no_role_password)
        self._assert_unauthorized(self.cfy.list_executions)

    def _assert_get_execution(self, execution_id):

        def _get_and_assert():
            out, err = self._execute_and_get_streams(
                self.cfy.get_execution, execution_id)
            self._assert_in_output(out, execution_id)
            self.assertEqual('', err)

        # admins, deployers and viewers should be able to get executions...
        self._login_cli(self.admin_username, self.admin_password)
        _get_and_assert()

        self._login_cli(self.deployer_username, self.deployer_password)
        _get_and_assert()

        self._login_cli(self.viewer_username, self.viewer_password)
        _get_and_assert()

        # ...but simple users should not
        self._login_cli(self.no_role_username, self.no_role_password)
        self._assert_unauthorized(self.cfy.get_execution, execution_id)

    def _assert_cancel_executions(self, execution_id1, execution_id2):

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
        self._login_cli(self.admin_username, self.admin_password)
        _cancel_and_assert(execution_id1)

        self._login_cli(self.deployer_username, self.deployer_password)
        _cancel_and_assert(execution_id2)

        # ...but viewers and simple users should not
        self._login_cli(self.viewer_username, self.viewer_password)
        self._assert_unauthorized(self.cfy.cancel_execution, execution_id1)

        self._login_cli(self.no_role_username, self.no_role_password)
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
            except UserUnauthorizedError as e:
                out.write(str(e))

        return out.getvalue(), err.getvalue()

    def _assert_in_output(self, out, *output_values):
        for value in output_values:
            self.assertIn(value, out)

    def _login_cli(self, username=None, password=None):
        self.logger.info('performing login to CLI with username: {0}, '
                         'password: {1}'.format(username, password))
        os.environ['CLOUDIFY_USERNAME'] = username
        os.environ['CLOUDIFY_PASSWORD'] = password

    def _login_client(self, username=None, password=None, token=None):
        self.logger.info('performing login to test client with username: {0}, '
                         'password: {1}, token: {2}'
                         .format(username, password, token))
        self.client = self._create_client(username=username,
                                          password=password,
                                          token=token)

    def _create_client(self, username=None, password=None, token=None):
        user_pass_header = util.get_auth_header(username=username,
                                                password=password,
                                                token=token)
        return CloudifyClient(host=self.env.management_ip,
                              headers=user_pass_header)

    def _get_execution_ids(self):
        alice_client = self._create_client(self.admin_username,
                                           self.admin_password)
        return [execution.id for execution in alice_client.executions.list()]

    def _assert_valid_credentials_authenticate(self):
        self._login_client(username=self.admin_username,
                           password=self.admin_password)
        self._assert_authorized()

    def _assert_invalid_credentials_fails(self):
        self._login_client(username='wrong_username',
                           password='wrong_password')
        self._assert_unauthorized(self.client.manager.get_status)

    def _assert_empty_credentials_fails(self):
        self._login_client(username='',
                           password='')
        self._assert_unauthorized(self.client.manager.get_status)

    def _assert_valid_token_authenticates(self):
        client = self._create_client(self.admin_username, self.admin_password)
        token = client.tokens.get().value
        self._login_client(token=token)
        self._assert_authorized()

    def _assert_invalid_token_fails(self):
        self._login_client(token='wrong_token')
        self._assert_unauthorized(self.client.manager.get_status)

    def _assert_empty_token_fails(self):
        self._login_client(token='')
        self._assert_unauthorized(self.client.manager.get_status)

    def _assert_no_credentials_or_token_fails(self):
        self.client = CloudifyClient(host=self.env.management_ip)
        self._assert_unauthorized(self.client.manager.get_status)

    def _assert_authorized(self):
        response = self.client.manager.get_status()
        if not response['status'] == 'running':
            self.fail('Failed to get manager status using username and '
                      'password')

    def _assert_unauthorized(self, method, *args):
        out, err = self._execute_and_get_streams(method, *args)
        self.assertIn('401: user unauthorized', out)
        self.assertEqual('', err)

    def get_userstore_users(self):
        return [
            {
                'username': self.admin_username,
                'password': self.admin_password,
                'groups': [
                    'cfy_admins'
                ]
            },
            {
                'username': self.deployer_username,
                'password': self.deployer_password,
                'groups': [
                    'cfy_deployers'
                ]
            },
            {
                'username': self.viewer_username,
                'password': self.viewer_password,
                'groups': [
                    'cfy_viewer'
                ]
            },
            {
                'username': self.no_role_username,
                'password': self.no_role_password,
                'groups': ['users']
            }
        ]

    def get_userstore_groups(self):
        return [
            {
                'name': 'cfy_admins',
                'roles': [
                    'administrator'
                ]
            },
            {
                'name': 'cfy_deployers',
                'roles': [
                    'deployer'
                ]
            },
            {
                'name': 'cfy_viewer',
                'roles': [
                    'viewer'
                ]
            }
        ]
