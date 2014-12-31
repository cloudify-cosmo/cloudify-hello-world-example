import importlib
import os
import json

import sh
import yaml
from path import path

from helpers import sh_bake
from helpers import update_config

git = sh_bake(sh.git)
pip = sh_bake(sh.pip)
nosetests = sh_bake(sh.nosetests)


class SuiteRunner(object):

    def __init__(self):
        self.base_dir = os.environ['BASE_HOST_DIR']
        self.work_dir = os.environ['WORK_DIR']
        self.branch_name_core = os.environ['BRANCH_NAME_CORE']
        self.branch_name_plugins = os.environ['BRANCH_NAME_PLUGINS']
        self.branch_name_system_tests = os.environ['BRANCH_NAME_SYSTEM_TESTS']
        self.opencm_git_pwd = os.environ['OPENCM_GIT_PWD']

        test_suite_name = os.environ['TEST_SUITE_NAME']

        self.test_suite = json.loads(os.environ['TEST_SUITE'])
        with open(os.path.join(self.base_dir, 'suites', 'suites.yaml')) as f:
            suites_yaml = yaml.load(f.read())
        tests = []
        for test in self.test_suite['tests']:
            if test in suites_yaml['tests']:
                tests += suites_yaml['tests']
            else:
                tests.append(test)
        self.tests_to_run = ' '.join(tests)

        self.handler_configuration = suites_yaml[
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
        self.report_file = os.path.join(
            self.base_dir, 'xunit-reports',
            '{0}-report.xml'.format(test_suite_name))

        handler_module = self.handler_configuration['handler_module']
        self.simple_handler_name = handler_module.split('.')[-1]

    def set_env_variables(self):
        os.environ['WORKFLOW_TASK_RETRIES'] = os.environ.get(
            'WORKFLOW_TASK_RETRIES', '20')
        os.environ['HANDLER_CONFIGURATION'] = self.test_suite[
            'handler_configuration']
        os.environ['SUITES_YAML_PATH'] = self.generated_suites_yaml_path

    def clone_and_install_packages(self):
        with path(self.work_dir):
            self._clone_and_checkout_repo(repo='cloudify-system-tests',
                                          branch=self.branch_name_system_tests)
            self._clone_and_checkout_repo(repo='cloudify-cli',
                                          branch=self.branch_name_core)
            self._clone_and_checkout_repo(repo='cloudify-manager-blueprints',
                                          branch=self.branch_name_core)
            pip.install('./cloudify-cli',
                        '-r', './cloudify-cli/requirements.txt').wait()
            pip.install('-e', './cloudify-system-tests').wait()

            handler_requirements_txt = os.path.join(
                os.path.dirname(__file__), 'helpers', 'handlers',
                self.simple_handler_name, 'requirements.txt')

            handler_init = importlib.import_module(
                'helpers.handlers.{0}'.format(self.simple_handler_name))

            pip.install('-r', handler_requirements_txt).wait()

            if self.bootstrap_using_providers:
                provider_repo = handler_init.provider_repo
                self._clone_and_checkout_repo(repo=provider_repo,
                                              branch=self.branch_name_plugins)
                pip.install('./{0}'.format(provider_repo)).wait()

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
        with open(self.original_inputs_path) as rf:
            with open(self.generated_inputs_path, 'w') as wf:
                wf.write(rf.read())
        update_config.update_config(
            config_path=self.generated_inputs_path,
            bootstrap_using_providers=self.bootstrap_using_providers,
            bootstrap_using_docker=self.bootstrap_using_docker,
            simple_handler_name=self.simple_handler_name,
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
        with path(self.work_dir) / 'cloudify-system-tests':
            nosetests(self.tests_to_run,
                      verbose=True,
                      nocapture=True,
                      nologcapture=True,
                      with_xunit=True,
                      xunit_file=self.report_file).wait()


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
