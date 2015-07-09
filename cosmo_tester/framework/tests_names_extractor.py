#########
# Copyright (c) 2015 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#  * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  * See the License for the specific language governing permissions and
#  * limitations under the License.

import json

from nose.plugins import collect


def _extract_test_info(test):
    test_details_dict = {'test_module': test.test.__module__,
                         'test_class': type(test.test).__name__,
                         'test_name': test.test._testMethodName}
    return test_details_dict


def _write_tests_json(tests_summary, test_list_path):
    with open(test_list_path, 'w') as outfile:
        json.dump(tests_summary, outfile, indent=4)


class TestsNamesExtractor(collect.CollectOnly):

    name = 'testnameextractor'
    enableOpt = 'test_name_extractor'

    def __init__(self):
        super(TestsNamesExtractor, self).__init__()
        self.accumulated_tests = []
        self.tests_list_path = None

    def options(self, parser, env):
        super(collect.CollectOnly, self).options(parser, env)
        parser.add_option('--tests-list-path', default='nose.cfy')

    def configure(self, options, conf):
        super(TestsNamesExtractor, self).configure(options, conf)
        self.tests_list_path = options.tests_list_path

    def addSuccess(self, test):
        self.accumulated_tests.append(_extract_test_info(test))

    def finalize(self, result):
        _write_tests_json(self.accumulated_tests, self.tests_list_path)
