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

import sh

from cosmo_tester.framework.testenv import TestCase


class ExecutionLoggingTest(TestCase):

    def test_execution_logging(self):
        blueprint_dir = self.copy_blueprint('execution-logging')
        self.blueprint_yaml = blueprint_dir / 'blueprint.yaml'
        self.upload_deploy_and_execute_install()
        for user_cause in [False, True]:
            with self.assertRaises(sh.ErrorReturnCode):
                self.cfy.executions.start(
                    'execute_operation',
                    deployment_id=self.test_id,
                    include_logs=True,
                    parameters={'operation': 'test.op',
                                'operation_kwargs': {
                                    'user_cause': user_cause}}
                )
        executions = self.client.executions.list(
            deployment_id=self.test_id,
            workflow_id='execute_operation').items
        no_user_cause_ex_id = [
            e for e in executions
            if not e.parameters['operation_kwargs'].get('user_cause')][0].id
        user_cause_ex_id = [
            e for e in executions
            if e.parameters['operation_kwargs'].get('user_cause')][0].id

        def assert_output(verbosity,
                          expect_debug,
                          expect_traceback,
                          expect_rest_logs):
            events = self.cfy.events.list(no_user_cause_ex_id, verbosity)

            assert_in = self.assertIn
            assert_not_in = self.assertNotIn
            assert_in('INFO: INFO_MESSAGE', events)
            assert_in('Task failed', events)
            assert_in('ERROR_MESSAGE', events)
            debug_assert = assert_in if expect_debug else assert_not_in
            debug_assert('DEBUG: DEBUG_MESSAGE', events)
            trace_assert = assert_in if expect_traceback else assert_not_in
            trace_assert('NonRecoverableError: ERROR_MESSAGE', events)
            assert_not_in('Causes', events)
            assert_not_in('RuntimeError: ERROR_MESSAGE', events)
            rest_assert = assert_in if expect_rest_logs else assert_not_in
            rest_assert('Sending request:', events)
            user_cause_events = self.cfy.events.list(
                user_cause_ex_id,
                verbosity
            )
            causes_assert = assert_in if expect_traceback else assert_not_in
            causes_assert('Causes', user_cause_events)
            causes_assert('RuntimeError: ERROR_MESSAGE', user_cause_events)
        assert_output(verbosity=[],  # sh handles '' as an argument, but not []
                      expect_traceback=False,
                      expect_debug=False,
                      expect_rest_logs=False)
        assert_output(verbosity='-v',
                      expect_traceback=True,
                      expect_debug=False,
                      expect_rest_logs=False)
        assert_output(verbosity='-vv',
                      expect_traceback=True,
                      expect_debug=True,
                      expect_rest_logs=False)
        assert_output(verbosity='-vvv',
                      expect_traceback=True,
                      expect_debug=True,
                      expect_rest_logs=True)
