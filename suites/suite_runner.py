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

import importlib
import os
import json
import sys
import logging

import sh
import yaml
from path import path
import lxml.etree as et

from helpers import sh_bake
# don't put imports that may include system tests code here
# put them inside functions that use them only after cloudify-system-tests
# have been installed


logging.basicConfig()

logger = logging.getLogger('suite_runner')
logger.setLevel(logging.INFO)

git = sh_bake(sh.git)
pip = sh_bake(sh.pip)
nosetests = sh_bake(sh.nosetests)
suite_reports_dir = path(__file__).dirname() / 'xunit-reports'

CLOUDIFY_SYSTEM_TESTS = 'cloudify-system-tests'


class HandlerPackage(object):
    def __init__(self, handler, external, directory=None):
        if not external:
            requirements_path = os.path.join(
                os.path.dirname(__file__), 'helpers', 'handlers',
                handler, 'requirements.txt')
            self._handler_module = 'helpers.handlers.{0}.handler'.format(
                handler)
        else:
            requirements_path = os.path.join(
                directory, 'system_tests', 'requirements.txt')
            self._handler_module = ('system_tests.{0}'.format(handler))
        self.requirements_path = path(requirements_path)

    @property
    def handler(self):
        return importlib.import_module(self._handler_module)


class SuiteRunner(object):
    def __init__(self):
        self.base_dir = os.environ['BASE_HOST_DIR']
        self.work_dir = os.environ['WORK_DIR']

        self.test_suite_name = os.environ['TEST_SUITE_NAME']
        self.test_suite = json.loads(os.environ['TEST_SUITE'])
        self.variables = json.loads(os.environ['TEST_SUITES_VARIABLES'])
        with open(os.path.join(self.base_dir, 'suites', 'suites.yaml')) as f:
            self.suites_yaml = yaml.load(f.read())
        self.suites_yaml['variables'] = self.variables

        self.branch_name_core = self.variables['core_branch']
        self.branch_name_system_tests = self.variables['system_tests_branch']
        self.branch_name_manager_blueprints = self.variables.get(
            'manager_blueprints_branch', self.branch_name_core)
        self.branch_name_cli = self.variables.get(
            'cli_branch', self.branch_name_core)
        self.windows_cli_package_url = \
            self.variables['windows_cli_package_url']
        self.rhel_centos_cli_package_url = \
            self.variables['rhel_centos_cli_package_url']
        self.debian_cli_package_url = \
            self.variables['debian_cli_package_url']
        self.cloudify_automation_token = \
            self.variables['cloudify_automation_token']

        self.handler_configuration = self.suites_yaml[
            'handler_configurations'][self.test_suite['handler_configuration']]

        inputs = self.handler_configuration['inputs']
        self.inputs_path = os.path.join(self.base_dir, 'configurations',
                                        inputs)
        self.generated_suites_yaml_path = os.path.join(
            self.work_dir, 'generated-suites.yaml')
        self.manager_blueprints_dir = os.path.join(
            self.work_dir, 'cloudify-manager-blueprints')

        self.handler = self.handler_configuration['handler']
        self.handler_package = None

    def set_env_variables(self):
        os.environ['HANDLER_CONFIGURATION'] = self.test_suite[
            'handler_configuration']
        os.environ['SUITES_YAML_PATH'] = self.generated_suites_yaml_path
        os.environ['BRANCH_NAME_CORE'] = self.branch_name_core
        os.environ['WINDOWS_CLI_PACKAGE_URL'] = self.windows_cli_package_url
        os.environ['RHEL_CENTOS_CLI_PACKAGE_URL'] = \
            self.rhel_centos_cli_package_url
        os.environ['DEBIAN_CLI_PACKAGE_URL'] = \
            self.debian_cli_package_url
        os.environ['CLOUDIFY_AUTOMATION_TOKEN'] = \
            self.cloudify_automation_token

    def clone_and_install_packages(self):
        with path(self.work_dir):
            self._clone_and_checkout_repo(
                repo=CLOUDIFY_SYSTEM_TESTS,
                branch=self.branch_name_system_tests)
            self._clone_and_checkout_repo(
                repo='cloudify-cli',
                branch=self.branch_name_cli)
            self._clone_and_checkout_repo(
                repo='cloudify-manager-blueprints',
                branch=self.branch_name_manager_blueprints)

            self._pip_install(
                'cloudify-cli',
                requirements=os.path.join(self.work_dir, 'cloudify-cli',
                                          'dev-requirements.txt'))
            self._pip_install(CLOUDIFY_SYSTEM_TESTS, editable=True)

            plugin_repo = None
            if 'external' in self.handler_configuration:
                external = self.handler_configuration['external']
                external = _process_variables(self.suites_yaml, external)
                plugin_repo = external['repo']
                branch = external['branch']
                organization = external.get('organization', 'cloudify-cosmo')
                private = external.get('private', False)
                username = external.get('username')
                password = external.get('password')
                self._clone_and_checkout_repo(repo=plugin_repo,
                                              branch=branch,
                                              organization=organization,
                                              private_repo=private,
                                              username=username,
                                              password=password)
                self._pip_install(plugin_repo, editable=True)

                self.handler_package = HandlerPackage(
                    self.handler,
                    external=True,
                    directory=os.path.join(self.work_dir, plugin_repo))
            else:
                self.handler_package = HandlerPackage(self.handler,
                                                      external=False)

            if self.handler_package.requirements_path.exists():
                self._pip_install(
                    requirements=self.handler_package.requirements_path)

            handler = self.handler_package.handler
            if plugin_repo and getattr(handler, 'has_manager_blueprint',
                                       False):
                self.manager_blueprints_dir = os.path.join(
                    self.work_dir, plugin_repo)

    def _clone_and_checkout_repo(self,
                                 repo,
                                 branch,
                                 organization='cloudify-cosmo',
                                 private_repo=False,
                                 username=None,
                                 password=None):
        with path(self.work_dir):
            if private_repo:
                git.clone(
                    'https://{0}:{1}@github.com/{2}/{3}'
                    .format(username, password, organization, repo)).wait()
            else:
                git.clone('https://github.com/{0}/{1}'
                          .format(organization, repo)).wait()

            with path(repo):
                git.checkout(branch).wait()

    def _pip_install(self, repo=None, requirements=None, editable=False):
        install_arguments = []
        if repo:
            if editable:
                install_arguments.append('-e')
            install_arguments.append('./{0}'.format(repo))
        if requirements:
            install_arguments += ['-r', requirements]
        with path(self.work_dir):
            pip.install(*install_arguments).wait()
        if repo and editable:
            repo_path = os.path.join(self.work_dir, repo)
            if repo_path not in sys.path:
                sys.path.append(repo_path)

    def generate_config(self):
        handler = self.handler_package.handler
        if hasattr(handler, 'update_config'):
            handler.update_config(
                manager_blueprints_dir=self.manager_blueprints_dir,
                variables=self.variables)

        if 'manager_blueprint' in self.handler_configuration:
            self.handler_configuration['manager_blueprint'] = \
                os.path.join(self.manager_blueprints_dir,
                             self.handler_configuration['manager_blueprint'])
        self.handler_configuration['inputs'] = self.inputs_path
        if 'clean_env_on_init' not in self.handler_configuration:
            self.handler_configuration['clean_env_on_init'] = True
        generated_suites_yaml = self.suites_yaml.copy()
        handler_configuration_name = self.test_suite['handler_configuration']
        generated_suites_yaml['handler_configurations'] = {
            handler_configuration_name: self.handler_configuration
        }
        with open(self.generated_suites_yaml_path, 'w') as f:
            f.write(yaml.dump(generated_suites_yaml))

        for _path, desc in self.suites_yaml.get('files', {}).items():
            processed_desc = _process_variables(self.suites_yaml, desc)
            _path = os.path.expanduser(_path)
            _dir = os.path.dirname(_path)
            if not os.path.isdir(_dir):
                os.makedirs(_dir)
            with open(_path, 'w') as f:
                f.write(processed_desc['content'])
            if processed_desc.get('chmod'):
                os.chmod(_path, processed_desc.get('chmod'))

    def run_nose(self):
        test_groups = {}
        for test in self.test_suite['tests']:
            if test in self.suites_yaml['tests']:
                test = self.suites_yaml['tests'][test]
            elif isinstance(test, basestring):
                test = {'tests': [test]}

            if 'external' in self.test_suite:
                test['external'] = self.test_suite['external']

            if 'external' in test:
                external = test['external']
                external = _process_variables(self.suites_yaml, external)
                repo = external['repo']
                if not (path(self.work_dir) / repo).isdir():
                    self._clone_and_checkout_repo(
                        repo=repo,
                        branch=external['branch'],
                        organization=external.get('organization',
                                                  'cloudify-cosmo'),
                        private_repo=external.get('private', False),
                        username=external.get('username'),
                        password=external.get('password'))
                test_group = repo
            else:
                test_group = CLOUDIFY_SYSTEM_TESTS

            if test_group not in test_groups:
                test_groups[test_group] = []
            test_groups[test_group] += test['tests']

        failed_groups = []

        for test_group, tests in test_groups.items():
            tests_dir = test_group
            report_file = suite_reports_dir / '{0}-{1}-report.xml'.format(
                self.test_suite_name, tests_dir)
            processed_tests = []
            for test in tests:
                processed_tests += test.split(' ')

            with path(self.work_dir) / tests_dir:
                tests_list_file_path = \
                    suite_reports_dir / '{0}-{1}-tests_list.json'.format(
                        self.test_suite_name, tests_dir)
                try:
                    nosetests(with_testnameextractor=True,
                              verbose=True,
                              tests_list_path=tests_list_file_path,
                              *processed_tests)

                    nosetests(verbose=True,
                              nocapture=True,
                              nologcapture=True,
                              with_xunit=True,
                              xunit_file=report_file,
                              xunit_testsuite_name=self.test_suite_name,
                              *processed_tests).wait()

                except sh.ErrorReturnCode:
                    failed_groups.append(test_group)

                self.add_missing_tests(report_file, tests_list_file_path)

        if failed_groups:
            raise AssertionError('Failed test groups: {}'.format(
                failed_groups))

    def add_missing_tests(self, report_file_path, expected_tests_file_path):

        # comparing tests that should have run to tests that actually
        # ran, and adding missing test to the xml report
        parser = et.XMLParser(strip_cdata=False)
        run_tests = set()
        missing_tests = []

        # preparing expected tests list
        with open(expected_tests_file_path) as data_file:
            expected_tests = json.load(data_file)

        # preparing run tests set
        root = et.parse(report_file_path.realpath(), parser)
        test_elements = root.findall('testcase')
        for test in test_elements:
            run_test_name = test.get('name')
            run_test_class = test.get('classname')
            run_tests.add('{0}.{1}'.format(run_test_class, run_test_name))

        # preparing missing tests list
        for expected_test in expected_tests:
            expected_test_module = expected_test['test_module']
            expected_test_class = expected_test['test_class']
            expected_test_name = expected_test['test_name']
            expected_test_full_name = '{0}.{1}.{2}'.format(
                expected_test_module,
                expected_test_class,
                expected_test_name)
            if expected_test_full_name not in run_tests:
                missing_tests.append(expected_test)

        # writing missing tests to xml report
        for missing_test in missing_tests:
            testcase_elem = et.SubElement(root.getroot(), 'testcase',
                                          classname='{0}.{1}'.
                                          format(missing_test['test_module'],
                                                 missing_test['test_class']),
                                          name=missing_test['test_name'])
            et.SubElement(testcase_elem, 'skipped',
                          message='Test should have run, but did not')
            with open(report_file_path, 'w') as report:
                report.write(et.tostring(root, pretty_print=True))


def _process_variables(suites_yaml, unprocessed_dict):
    from cosmo_tester.framework.util import process_variables
    return process_variables(suites_yaml, unprocessed_dict)


def main():
    suite_runner = SuiteRunner()
    suite_runner.set_env_variables()
    suite_runner.clone_and_install_packages()
    suite_runner.generate_config()
    suite_runner.run_nose()

if __name__ == '__main__':
    main()
