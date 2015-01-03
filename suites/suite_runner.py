import importlib
import os
import json

import sh
import yaml
from path import path

from helpers import sh_bake
# don't put imports that may include system tests code here
# put them inside functions that use them only after cloudify-system-tests
# have been installed

git = sh_bake(sh.git)
pip = sh_bake(sh.pip)
nosetests = sh_bake(sh.nosetests)


CLOUDIFY_SYSTEM_TESTS = 'cloudify-system-tests'


class HandlerPackage(object):

    def __init__(self, handler, external, directory=None):
        if not external:
            self.init = importlib.import_module(
                'helpers.handlers.{0}'.format(handler))
            self.requirements_path = os.path.join(
                os.path.dirname(__file__), 'helpers', 'handlers',
                handler, 'requirements.txt')
            self.update_config = importlib.import_module(
                'helpers.handlers.{0}.update_config'.format(handler))
        else:
            main_package, handler_name = handler.split('.')
            self.init = importlib.import_module(
                '{0}.system_tests.handlers.{1}'.format(main_package,
                                                       handler_name))
            self.requirements_path = os.path.join(
                directory, main_package, 'system_tests', 'handlers',
                handler_name, 'requirements.txt')
            self.update_config = importlib.import_module(
                '{0}.system_tests.handlers.{1}.update_config'.format(
                    main_package, handler_name))


class SuiteRunner(object):

    def __init__(self):
        self.base_dir = os.environ['BASE_HOST_DIR']
        self.work_dir = os.environ['WORK_DIR']
        self.branch_name_core = os.environ['BRANCH_NAME_CORE']
        self.branch_name_plugins = os.environ['BRANCH_NAME_PLUGINS']
        self.branch_name_system_tests = os.environ['BRANCH_NAME_SYSTEM_TESTS']
        self.opencm_git_pwd = os.environ['OPENCM_GIT_PWD']

        self.test_suite_name = os.environ['TEST_SUITE_NAME']
        self.test_suite = json.loads(os.environ['TEST_SUITE'])
        with open(os.path.join(self.base_dir, 'suites', 'suites.yaml')) as f:
            self.suites_yaml = yaml.load(f.read())

        self.handler_configuration = self.suites_yaml[
            'handler_configurations'][self.test_suite['handler_configuration']]
        self.bootstrap_using_providers = self.handler_configuration.get(
            'bootstrap_using_providers', False)
        self.bootstrap_using_docker = self.handler_configuration.get(
            'bootstrap_using_docker', True)

        inputs = self.handler_configuration['inputs']
        self.original_inputs_path = os.path.join(self.base_dir,
                                                 'configurations', inputs)
        self.generated_inputs_path = os.path.join(
            self.work_dir, 'generated-config.{0}'.format(
                'yaml' if self.bootstrap_using_providers else 'json'))
        self.generated_suites_yaml_path = os.path.join(
            self.work_dir, 'generated-suites.yaml')
        self.manager_blueprints_dir = os.path.join(
            self.work_dir, 'cloudify-manager-blueprints')

        self.handler = self.handler_configuration['handler']
        self.handler_package = None

    def set_env_variables(self):
        os.environ['WORKFLOW_TASK_RETRIES'] = os.environ.get(
            'WORKFLOW_TASK_RETRIES', '20')
        os.environ['HANDLER_CONFIGURATION'] = self.test_suite[
            'handler_configuration']
        os.environ['SUITES_YAML_PATH'] = self.generated_suites_yaml_path

    def clone_and_install_packages(self):
        with path(self.work_dir):
            self._clone_and_checkout_repo(repo=CLOUDIFY_SYSTEM_TESTS,
                                          branch=self.branch_name_system_tests)
            self._clone_and_checkout_repo(repo='cloudify-cli',
                                          branch=self.branch_name_core)
            self._clone_and_checkout_repo(repo='cloudify-manager-blueprints',
                                          branch=self.branch_name_core)
            pip.install('./cloudify-cli',
                        '-r', './cloudify-cli/dev-requirements.txt').wait()
            pip.install('-e', './{0}'.format(CLOUDIFY_SYSTEM_TESTS)).wait()
            import cosmo_tester.framework.handlers
            import suites.helpers.handlers.openstack

            if 'external' in self.handler_configuration:
                external = self.handler_configuration['external']
                repo = external['repo']
                branch = external.get('branch', self.branch_name_plugins)
                organization = external.get('organization', 'cloudify-cosmo')
                self._clone_and_checkout_repo(repo=repo,
                                              branch=branch,
                                              organization=organization)
                pip.install('-e', './{0}'.format(repo)).wait()

                import openstack_plugin_common.system_tests.handlers.openstack
                self.handler_package = HandlerPackage(
                    self.handler,
                    external=True,
                    directory=os.path.join(self.work_dir, repo))
            else:
                self.handler_package = HandlerPackage(self.handler,
                                                      external=False)

            pip.install('-r', self.handler_package.requirements_path).wait()

            handler_init = self.handler_package.init
            if self.bootstrap_using_providers:
                provider_repo = handler_init.provider_repo
                self._clone_and_checkout_repo(repo=provider_repo,
                                              branch=self.branch_name_plugins)
                pip.install('./{0}'.format(provider_repo)).wait()

            # TODO: this logic only exists for the vpshere handler
            # move handler into plugin code and install it like any
            # other external handler
            if hasattr(handler_init, 'plugin_repo'):
                plugin_repo = handler_init.plugin_repo
                private_repo = getattr(handler_init, 'private', False)
                self._clone_and_checkout_repo(repo=plugin_repo,
                                              branch=self.branch_name_plugins,
                                              private_repo=private_repo)
                pip.install('./{0}'.format(plugin_repo)).wait()
                if getattr(handler_init, 'has_manager_blueprint', False):
                    self.manager_blueprints_dir = os.path.join(
                        self.work_dir, plugin_repo)

    def _clone_and_checkout_repo(self,
                                 repo,
                                 branch,
                                 organization='cloudify-cosmo',
                                 private_repo=False):
        with path(self.work_dir):
            if private_repo:
                git.clone('https://opencm:{0}@github.com/{1}/{2}'
                          .format(self.opencm_git_pwd, organization, repo),
                          depth=1).wait()
            else:
                git.clone('https://github.com/{0}/{1}'
                          .format(organization, repo), depth=1).wait()

            with path(repo):
                git.checkout(branch).wait()

    def generate_config(self):
        from helpers import update_config
        with open(self.original_inputs_path) as rf:
            with open(self.generated_inputs_path, 'w') as wf:
                wf.write(rf.read())
        update_config.update_config(
            config_path=self.generated_inputs_path,
            bootstrap_using_providers=self.bootstrap_using_providers,
            bootstrap_using_docker=self.bootstrap_using_docker,
            handler_update_config=self.handler_package.update_config,
            manager_blueprints_dir=self.manager_blueprints_dir)

        self.handler_configuration['manager_blueprints_dir'] = \
            self.manager_blueprints_dir
        self.handler_configuration['inputs'] = self.generated_inputs_path
        with open(self.generated_suites_yaml_path, 'w') as f:
            f.write(yaml.dump({
                'handler_configurations': {
                    self.test_suite['handler_configuration']:
                        self.handler_configuration
                }}))

    def run_nose(self):

        test_groups = {}
        for test in self.test_suite['tests']:
            if test in self.suites_yaml:
                test = self.suites_yaml[test]
            elif isinstance(test, basestring):
                test = {'tests': [test]}

            if 'external' in test:
                repo = test['external']['repo']
                if not (path(self.work_dir) / repo).isdir():
                    self._clone_and_checkout_repo(
                        repo=repo,
                        branch=test['external'].get('branch',
                                                    self.branch_name_plugins),
                        organization=test['external'].get('organization',
                                                          'cloudify-cosmo'))
                test_group = repo
            else:
                test_group = CLOUDIFY_SYSTEM_TESTS

            if test_group not in test_groups:
                test_groups[test_group] = []
            test_groups[test_group] += test['tests']

        failed_groups = []

        for test_group, tests in test_groups.items():
            tests_dir = test_group
            report_file = os.path.join(
                self.base_dir, 'xunit-reports',
                '{0}-{1}-report.xml'.format(self.test_suite_name,
                                            tests_dir))
            tests = ' '.join(tests)
            with path(self.work_dir) / tests_dir:
                try:
                    nosetests(tests,
                              verbose=True,
                              nocapture=True,
                              nologcapture=True,
                              with_xunit=True,
                              xunit_file=report_file).wait()
                except sh.ErrorReturnCode:
                    failed_groups.append(test_group)

        if failed_groups:
            raise AssertionError('Failed test groups: {}'.format(
                failed_groups))


def main():
    suite_runner = SuiteRunner()
    # called once before generate config (which uses some variables
    # internally)
    suite_runner.set_env_variables()
    suite_runner.clone_and_install_packages()
    suite_runner.generate_config()
    # called once again before running node because manager blueprints dir
    # may have changed in a previous step
    suite_runner.set_env_variables()
    suite_runner.run_nose()

if __name__ == '__main__':
    main()
