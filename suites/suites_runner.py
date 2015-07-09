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

import os
import sys
import logging
import json
import random
import shutil
import time
import tempfile

import jinja2
import yaml
import sh
from path import path
from nose.plugins import xunit

from helpers import sh_bake
from helpers.suites_builder import build_suites_yaml

logging.basicConfig()

logger = logging.getLogger('suites_runner')
logger.setLevel(logging.INFO)

docker = None
vagrant = None

reports_dir = path(__file__).dirname() / 'xunit-reports'

TEST_SUITES_PATH = 'TEST_SUITES_PATH'
DOCKER_REPOSITORY = 'cloudify/test'
DOCKER_TAG = 'env'
SUITE_ENVS_DIR = 'suite-envs'
SCHEDULER_INTERVAL = 30


class TestSuite(object):

    def __init__(self, suite_name, suite_def, suite_work_dir, variables):
        self.suite_name = suite_name
        self.suite_def = suite_def
        self.suite_work_dir = suite_work_dir
        self.suite_reports_dir = suite_work_dir / 'xunit-reports'
        self.variables = variables
        self._handler_configuration_def = None
        self.process = None
        self.started = None
        self.terminated = None
        self.timed_out = False

    @property
    def descriptor(self):
        return self.suite_def.get('descriptor')

    @property
    def handler_configuration(self):
        return self.suite_def.get('handler_configuration')

    @handler_configuration.setter
    def handler_configuration(self, (config_name, config_def)):
        self.suite_def['handler_configuration'] = config_name
        self._handler_configuration_def = config_def

    @property
    def requires(self):
        return self.suite_def.get('requires', [])

    @property
    def running_time(self):
        if self.terminated:
            return self.terminated - self.started
        elif self.started:
            return time.time() - self.started
        else:
            return 0

    def create_env(self):
        self.suite_work_dir.makedirs()
        self.suite_reports_dir.makedirs()
        vagrant_file_template = path('Vagrantfile.template').text()
        vagrant_file_content = jinja2.Template(vagrant_file_template).render({
            'suite_name': self.suite_name,
            'suite': json.dumps(self.suite_def),
            'variables': json.dumps(self.variables)
        })
        path(self.suite_work_dir / 'Vagrantfile').write_text(
            vagrant_file_content)
        files_to_copy = [
            'Dockerfile',
            'suite_runner.py',
            'suite_runner.sh',
            'requirements.txt',
            'suites',
            'helpers',
            'configurations']
        for file_name in files_to_copy:
            if os.path.isdir(file_name):
                shutil.copytree(file_name, os.path.join(self.suite_work_dir,
                                                        file_name))
            else:
                shutil.copy(file_name, os.path.join(self.suite_work_dir,
                                                    file_name))

    @property
    def is_running(self):
        return self.process is not None and self.process.is_alive()

    def run(self):
        logger.info('Creating environment for suite: {0}'.format(
            self.suite_name))
        self.create_env()
        logger.info('Starting suite in docker container: {0}'.format(
            self.suite_name))
        cwd = path.getcwd()
        try:
            os.chdir(self.suite_work_dir)
            vagrant.up().wait()
            self.process = vagrant('docker-logs', f=True, _bg=True).process
        finally:
            os.chdir(cwd)

    def terminate(self):
        logger.info('Stopping docker container: {0}'.format(self.suite_name))
        docker.stop(self.suite_name).wait()
        logger.info('Docker container stopped: {0}'.format(self.suite_name))

    def _generate_custom_xunit_report(self,
                                      text,
                                      error_type,
                                      error_message,
                                      fetch_logs=True):
        logger.info('Getting docker logs for container: {0}'.format(
            self.suite_name))
        if fetch_logs:
            logs = xunit.xml_safe(sh.docker.logs(self.suite_name).strip())
        else:
            logs = ''
        if self._handler_configuration_def:
            env_id = self._handler_configuration_def['env']
            config = {
                self.handler_configuration: self._handler_configuration_def}
        else:
            env_id = None
            config = None
        err = """{0}

Suite definition:
{1}

Environment: {2}

Handler configuration:
{3}""".format(text,
              json.dumps(self.suite_def, indent=2),
              env_id,
              json.dumps(config, indent=2))
        xunit_file_template = path('xunit-template.xml').text()
        xunit_file_content = jinja2.Template(xunit_file_template).render({
            'suite_name': self.suite_name,
            'test_name': 'TEST-SUITE: {0} ENV-ID: {1}'.format(
                self.descriptor,
                env_id),
            'time': self.running_time,
            'error_type': error_type,
            'error_message': error_message,
            'system_out': logs,
            'system_err': err
        })
        report_file = reports_dir / path(
            '{0}-docker-container-report.xml'.format(self.suite_name))
        logger.info('Writing xunit report file to: {0}'.format(
            report_file.abspath()))
        report_file.write_text(xunit_file_content, encoding='utf-8')

    def copy_xunit_reports(self):
        if self.timed_out:
            self._generate_custom_xunit_report(
                'Suite {0} timed out after {1} seconds.'.format(
                    self.descriptor, self.running_time),
                error_type='TestSuiteTimeout',
                error_message='Test suite timed out')
        elif not self.started:
            self._generate_custom_xunit_report(
                "Suite {0} skipped (couldn't find a matching "
                "environment).".format(self.descriptor),
                error_type='TestSuiteSkipped',
                error_message='Test suite skipped',
                fetch_logs=False)
        else:
            import lxml.etree as et
            report_files = self.suite_reports_dir.files('*.xml')
            logger.info('Suite [{0}] reports: {1}'.format(
                self.suite_name, [r.name for r in report_files]))

            # adding suite name as a prefix to each test in each report
            parser = et.XMLParser(strip_cdata=False)
            for report in report_files:
                root = et.parse(report.realpath(), parser)
                test_elements = root.findall('testcase')
                for test in test_elements:
                    test_name = test.get('name')
                    test.set('name', '{0} @ {1}'.format(test_name,
                                                        self.suite_name))
                tmp_file = tempfile.NamedTemporaryFile()
                tmp_file.write(et.tostring(root, pretty_print=True))
                # flushing remaining text in buffer before closing the file
                tmp_file.flush()
                shutil.copy(tmp_file.name, reports_dir / report.name)
                tmp_file.close()


class SuitesScheduler(object):

    def __init__(self,
                 test_suites,
                 handler_configurations,
                 scheduling_interval=1,
                 optimize=False,
                 after_suite_callback=None,
                 suite_timeout=-1):
        self._test_suites = test_suites
        if optimize:
            self._test_suites = sorted(
                test_suites,
                key=lambda x: x.handler_configuration is None)
        self._handler_configurations = handler_configurations
        self._locked_envs = set()
        self._scheduling_interval = scheduling_interval
        self._after_suite_callback = after_suite_callback
        self._suite_timeout = suite_timeout
        self._validate()
        self._log_test_suites()
        self.skipped_suites = []

    def _log_test_suites(self):
        output = {x.suite_name: x.suite_def for x in self._test_suites}
        logger.info('SuitesScheduler initialized with the following suites'
                    ':\n{0}'.format(json.dumps(output, indent=2)))

    def _validate(self):
        for suite in self._test_suites:
            if not self._find_matching_handler_configurations(suite):
                raise ValueError(
                    'Cannot find a matching handler configuration for '
                    'suite: {0}'.format(suite.suite_name))

    def run(self):
        logger.info('Test suites scheduler started')
        suites_list = self._test_suites
        while len(suites_list) > 0:
            logger.info('Current suites in scheduler: {0}'.format(
                ', '.join(
                    ['{0} [started={1}]'.format(
                        s.suite_name,
                        s.started is not None) for s in suites_list])))
            remaining_suites = []
            for suite in suites_list:
                logger.info('Processing suite: {0}'.format(suite.suite_name))
                # Run suite
                if not suite.started:
                    matches = self._find_matching_handler_configurations(suite)
                    if not matches:
                        logger.warn(
                            'Suite: {0} has no matching handler configuration.'
                            ' Suite will be skipped.'.format(suite.suite_name))
                        self._after_suite(suite)
                        self.skipped_suites.append(suite)
                    else:
                        config_names = matches.keys()
                        random.shuffle(config_names)
                        logger.info(
                            'Matching handler configurations for {0} are: {1}'
                            .format(suite.suite_name, ', '.join(config_names)))
                        for name in config_names:
                            configuration = matches[name]
                            if self._lock_env(configuration['env']):
                                suite.handler_configuration = (name,
                                                               configuration)
                                suite.started = time.time()
                                suite.run()
                                break
                        if suite.started:
                            logger.info('Suite {0} will run using handler '
                                        'configuration: {1}'.format(
                                            suite.suite_name,
                                            suite.handler_configuration))
                        else:
                            logger.info(
                                'All matching handler configurations for {0} '
                                'are currently taken'.format(suite.suite_name))
                        remaining_suites.append(suite)
                # Suite terminated
                elif not suite.is_running:
                    logger.info(
                        'Suite terminated: {0}'.format(suite.suite_name))
                    self._after_suite(suite)
                # Suite timed out
                elif self._suite_timeout != -1 \
                        and suite.running_time > self._suite_timeout:
                    suite.timed_out = True
                    config = self._handler_configurations[
                        suite.handler_configuration]
                    logger.warn(
                        'Suite timed out: {0} [handler_configuration={1}, '
                        'suite_running_time={2}s]'.format(
                            suite.suite_name,
                            config,
                            int(suite.running_time)))
                    logger.warn(
                        'Terminating suite: {0}'.format(suite.suite_name))
                    try:
                        suite.terminate()
                    except Exception as e:
                        logger.error(
                            'Error on suite termination [suite={0}, error'
                            '={1}]'.format(suite.suite_name, str(e)))
                    self._after_suite(suite)
                    self._remove_env(config['env'])
                # Suite is running
                else:
                    remaining_suites.append(suite)
            suites_list = remaining_suites
            time.sleep(self._scheduling_interval)
        logger.info('Test suites scheduler stopped')

    def _remove_env(self, env_id):
        logger.warn(
            'Removing all handler configurations which use '
            'env: {0}'.format(env_id))
        for k in self._handler_configurations.keys():
            config = self._handler_configurations[k]
            if config['env'] == env_id:
                logger.warn(
                    'Removing handler configuration: {0} '
                    '[env_id={1}]'.format(k, env_id))
                del self._handler_configurations[k]

    def _after_suite(self, suite):
        if suite.started:
            suite.terminated = time.time()
        if suite.handler_configuration:
            config = self._handler_configurations.get(
                suite.handler_configuration)
            if config:
                self._release_env(config['env'])
        try:
            if self._after_suite_callback:
                logger.info(
                    'Invoking after suite callback for suite: {0}'.format(
                        suite.suite_name))
                self._after_suite_callback(suite)
        except Exception as e:
            logger.error(
                'After suite callback failed for suite: {0} - '
                'error: {1}'.format(suite.suite_name, str(e)))

    def _find_matching_handler_configurations(self, suite):
        if suite.handler_configuration:
            config = self._handler_configurations.get(
                suite.handler_configuration)
            return {
                suite.handler_configuration:
                    self._handler_configurations[suite.handler_configuration]
            } if config else {}
        tags_match = lambda x, y: set(x) & set(y) == set(x)
        return {
            k: v for k, v in self._handler_configurations.iteritems()
            if tags_match(suite.requires, v.get('tags', set()))
        }

    def _lock_env(self, env_id):
        if env_id in self._locked_envs:
            return False
        self._locked_envs.add(env_id)
        return True

    def _release_env(self, env_id):
        self._locked_envs.remove(env_id)


def list_containers(quiet=False):
    return sh.docker.ps(a=True, q=quiet).strip()


def get_docker_image_id():
    image_ids = [line for line in sh.docker.images(
        ['-q', DOCKER_REPOSITORY]).strip().split(os.linesep) if len(line) > 0]
    if len(image_ids) > 1:
        raise RuntimeError(
            'Found several docker image ids instead of a single one.')
    return image_ids[0] if image_ids else None


def build_docker_image():
    docker.build(
        ['-t', '{0}:{1}'.format(DOCKER_REPOSITORY, DOCKER_TAG), '.']).wait()
    docker_image_id = get_docker_image_id()
    if not docker_image_id:
        raise RuntimeError(
            'Docker image not found after docker image was built.')


def kill_containers():
    containers = list_containers(quiet=True).replace(os.linesep, ' ')
    if containers:
        logger.info('Killing containers: {0}'.format(containers))
        docker.rm('-f', containers).wait()


def container_exit_code(container_name):
    return int(sh.docker.wait(container_name).strip())


def container_kill(container_name):
    logger.info('Killing container: {0}'.format(container_name))
    docker.rm('-f', container_name).wait()


def copy_xunit_report(suite):
    suite.copy_xunit_reports()


def test_start():
    if os.path.exists(SUITE_ENVS_DIR):
        shutil.rmtree(SUITE_ENVS_DIR)

    with open(os.environ[TEST_SUITES_PATH]) as f:
        suites_yaml = yaml.load(f.read())
    variables = suites_yaml.get('variables', {})

    build_docker_image()

    envs_dir = path.getcwd() / SUITE_ENVS_DIR

    test_suites = [
        TestSuite(suite_name,
                  suite_def,
                  envs_dir / suite_name,
                  variables) for suite_name, suite_def in
        suites_yaml['test_suites'].iteritems()]

    scheduler = SuitesScheduler(test_suites,
                                suites_yaml['handler_configurations'],
                                scheduling_interval=SCHEDULER_INTERVAL,
                                optimize=True,
                                after_suite_callback=copy_xunit_report,
                                suite_timeout=60*60*5)
    scheduler.run()
    return scheduler


def test_run():
    scheduler = test_start()
    logger.info('wait for containers exit status codes')
    containers = [x for x in get_containers_names()
                  if x not in scheduler.skipped_suites]
    exit_codes = [(c, container_exit_code(c)) for c in containers]
    logger.info('removing containers')
    for c in containers:
        container_kill(c)
    failed_containers = [(c, exit_code)
                         for c, exit_code in exit_codes
                         if exit_code != 0]
    if failed_containers or scheduler.skipped_suites:
        logger.warn('Failed test suites:')
        for c, exit_code in failed_containers:
            logger.warn('\t{}: exit code: {}'.format(c, exit_code))
        logger.warn('Skipped test suites: {0}'.format(
            x.suite_name for x in scheduler.skipped_suites))
        sys.exit(1)


def setenv(variables_path):
    setup_reports_dir()
    descriptor = os.environ['SYSTEM_TESTS_DESCRIPTOR']
    os.environ[TEST_SUITES_PATH] = build_suites_yaml('suites/suites.yaml',
                                                     variables_path,
                                                     descriptor)


def validate():
    with open(os.environ[TEST_SUITES_PATH]) as f:
        suites = yaml.load(f.read())
    for suite_name, suite in suites['test_suites'].items():
        requires = suite.get('requires')
        configuration_name = suite.get('handler_configuration')
        if requires and configuration_name:
            raise AssertionError(
                'Suite: {0} has both "requires" and "handler_configuration" '
                'set'.format(suite_name))
        elif not requires and not configuration_name:
            raise AssertionError(
                'Suite: {0} does not have "requires" or '
                '""handler_configuration" specified'.format(suite_name))
    for name, configuration in suites['handler_configurations'].iteritems():
        if 'env' not in configuration:
            raise AssertionError(
                '"{0}" handler configuration does not contain an env '
                'property'.format(name))


def cleanup():
    logger.info('Current containers:\n{0}'
                .format(list_containers()))
    kill_containers()


def setup_reports_dir():
    if not reports_dir.exists():
        reports_dir.mkdir()
    for report in reports_dir.files():
        report.remove()


def get_containers_names():
    with open(os.environ[TEST_SUITES_PATH]) as f:
        suites = yaml.load(f.read())['test_suites'].keys()
    return [s for s in suites]


def main():
    variables_path = sys.argv[1]
    global docker, vagrant
    docker = sh_bake(sh.docker)
    vagrant = sh_bake(sh.vagrant)
    setenv(variables_path)
    cleanup()
    validate()
    test_run()

if __name__ == '__main__':
    main()
