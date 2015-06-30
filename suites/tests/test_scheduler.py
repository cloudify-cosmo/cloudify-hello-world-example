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


import logging
import threading
import time
import unittest

from path import path
from suites.suites_runner import TestSuite, SuitesScheduler

logger = logging.getLogger('suites_scheduler')
logger.setLevel(logging.INFO)


class MockTestSuite(TestSuite):

    def __init__(self, *args, **kwargs):
        super(MockTestSuite, self).__init__(*args, **kwargs)
        self._running = False
        self.run_for = 0

    def _do_something(self):
        deadline = time.time() + self.run_for
        while time.time() < deadline and self._running:
            time.sleep(1)
        self._running = False

    def run(self):
        self._running = True
        t = threading.Thread(target=self._do_something)
        t.start()

    def terminate(self):
        self._running = False

    @property
    def is_running(self):
        return self._running


class TestSuiteScheduler(unittest.TestCase):

    def _new_test_suite(self,
                        suite_name,
                        requires=None,
                        handler_configuration=None,
                        run_for=0):
        suite_def = {}
        if requires:
            suite_def['requires'] = requires
        if handler_configuration:
            suite_def['handler_configuration'] = handler_configuration
        mock_test_suite = MockTestSuite(
            suite_name=suite_name,
            suite_def=suite_def,
            suite_work_dir=path('/tmp'),
            variables={})
        mock_test_suite.run_for = run_for
        return mock_test_suite

    def test_run_suite(self):
        test_suites = [
            self._new_test_suite('suite1', ['env1'])
        ]
        handler_configurations = {
            'config1': {'env': 'env1_id', 'tags': ['env1']}
        }
        scheduler = SuitesScheduler(test_suites, handler_configurations)
        scheduler.run()
        self.assertFalse(test_suites[0].is_running)

    def test_run_two_suites(self):
        test_suites = [
            self._new_test_suite('suite1', ['env1']),
            self._new_test_suite('suite2', ['env1'])
        ]
        handler_configurations = {
            'config1': {'env': 'env1_id', 'tags': ['env1']}
        }
        scheduler = SuitesScheduler(
            test_suites,
            handler_configurations)
        scheduler.run()
        self.assertFalse(test_suites[0].is_running)
        self.assertFalse(test_suites[1].is_running)
        self.assertTrue(test_suites[1].started > test_suites[0].terminated)

    def test_handler_configuration_and_tags_matching(self):
        test_suites = [
            self._new_test_suite('suite1', requires=['env1']),
            self._new_test_suite('suite2', handler_configuration='config1'),
            self._new_test_suite('suite3', requires=['env1'])
        ]
        handler_configurations = {
            'config1': {'env': 'env1_id', 'tags': ['env1']}
        }
        scheduler = SuitesScheduler(
            test_suites,
            handler_configurations)
        scheduler.run()
        self.assertFalse(test_suites[0].is_running)
        self.assertFalse(test_suites[1].is_running)
        self.assertFalse(test_suites[2].is_running)
        self.assertTrue(test_suites[1].started > test_suites[0].terminated)
        self.assertTrue(test_suites[2].started > test_suites[1].terminated)

    def test_no_matching_envs(self):
        test_suites = [
            self._new_test_suite('suite1', requires=['aaa'])
        ]
        handler_configurations = {
            'config1': {'env': 'env1_id', 'tags': ['env1']}
        }
        self.assertRaisesRegexp(ValueError,
                                'Cannot find a matching handler configuration',
                                SuitesScheduler,
                                test_suites,
                                handler_configurations)

    def test_suites_running_in_parallel(self):
        suites = [
            self._new_test_suite('suite1', requires=['env1'], run_for=10),
            self._new_test_suite('suite2',
                                 handler_configuration='config1',
                                 run_for=1),
            self._new_test_suite('suite3', requires=['env2'], run_for=5)
        ]
        handler_configurations = {
            'config1': {'env': 'env1_id', 'tags': ['env1']},
            'config2': {'env': 'env2_id', 'tags': ['env2']}
        }
        scheduler = SuitesScheduler(
            suites,
            handler_configurations)
        scheduler.run()
        self.assertEqual('config1', suites[0].handler_configuration)
        self.assertEqual('config1', suites[1].handler_configuration)
        self.assertEqual('config2', suites[2].handler_configuration)
        self.assertFalse(suites[0].is_running)
        self.assertFalse(suites[1].is_running)
        self.assertFalse(suites[2].is_running)
        self.assertTrue(suites[1].started > suites[0].terminated)
        self.assertTrue(suites[2].started < suites[0].terminated)

    def test_configuration_specific_prioritization(self):
        suites = [
            self._new_test_suite('suite1', requires=['env2']),
            self._new_test_suite('suite2',
                                 handler_configuration='config1'),
            self._new_test_suite('suite3',
                                 handler_configuration='config2')
        ]
        handler_configurations = {
            'config1': {'env': 'env1_id', 'tags': ['env1']},
            'config2': {'env': 'env2_id', 'tags': ['env2']}
        }
        scheduler = SuitesScheduler(
            suites,
            handler_configurations,
            optimize=True)
        scheduler.run()
        self.assertTrue(suites[0].started > suites[1].started)
        self.assertTrue(suites[0].started > suites[2].started)
        self.assertTrue(suites[2].terminated < suites[0].started)

    def test_timed_out_suite(self):
        suite_time = 10
        suites = [
            self._new_test_suite('suite1',
                                 requires=['env1'],
                                 run_for=suite_time)
        ]
        handler_configurations = {
            'config1': {'env': 'env1_id', 'tags': ['env1']}
        }
        scheduler = SuitesScheduler(
            suites,
            handler_configurations,
            suite_timeout=1)
        start = time.time()
        scheduler.run()
        delta = time.time() - start
        self.assertTrue(
            delta < suite_time,
            msg='Scheduler running time should be less than {0} seconds but '
                'was {1} seconds.'.format(suite_time, delta))
        self.assertTrue(suites[0].timed_out)

    def test_timed_out_env_removed_from_envs_list(self):
        suite_time = 10
        suites = [
            self._new_test_suite('suite1',
                                 requires=['env1'],
                                 run_for=suite_time),
            self._new_test_suite('suite2',
                                 requires=['env1'],
                                 run_for=suite_time),
            self._new_test_suite('suite3',
                                 handler_configuration='config1',
                                 run_for=suite_time)
        ]
        handler_configurations = {
            'config1': {'env': 'env1_id', 'tags': ['env1']}
        }
        scheduler = SuitesScheduler(
            suites,
            handler_configurations,
            suite_timeout=1)
        scheduler.run()
        self.assertIsNone(suites[1].started)
        self.assertIsNone(suites[2].started)
        self.assertEqual(2, len(scheduler.skipped_suites))
