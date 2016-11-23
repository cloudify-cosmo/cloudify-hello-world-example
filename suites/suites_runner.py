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
import signal
import logging
import json
import random
import shutil
import time
import tempfile
from contextlib import contextmanager

import fasteners
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

try:
    docker = sh_bake(sh.docker)
except sh.CommandNotFound:
    docker = None
try:
    vagrant = sh_bake(sh.vagrant)
except sh.CommandNotFound:
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
        self.container_name = '{0}_{1}'.format(os.getpid(), self.suite_name)
        self.suite_def = suite_def
        self.suite_work_dir = suite_work_dir
        self.suite_reports_dir = suite_work_dir / 'xunit-reports'
        self.variables = variables
        self._handler_configuration_def = None
        self.process = None
        self.started = None
        self.terminated = None
        self.timed_out = False
        self.failed = False
        self.exit_code = None

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
            'container_name': self.container_name,
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
            'wheel-requirements.txt',
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
        logger.warn('Terminating suite: {0}'.format(self.suite_name))
        try:
            logger.info('Stopping docker container: {0}'.format(
                self.container_name))
            docker.stop(self.container_name).wait()
            logger.info('Docker container stopped: {0}'.format(
                self.container_name))
        except Exception as e:
            logger.error('Error on suite termination [suite={0}, error'
                         '={1}]'.format(self.suite_name, str(e)))

    def kill(self):
        try:
            kill_container(self.container_name)
        except Exception as e:
            logger.error('Error on suite kill [suite={0}, error'
                         '={1}]'.format(self.container_name, str(e)))

    @staticmethod
    def after_suite(suite):
        # timeout out, need to terminate
        if suite.timed_out:
            suite.terminate()
        else:
            suite.exit_code = int(
                sh.docker.wait(suite.container_name).strip())
            if suite.exit_code:
                suite.failed = True
        suite.copy_xunit_reports()
        # kill removes the container so it should be called after exit code
        # is extracted and xunit reports are generated
        suite.kill()

    def copy_xunit_reports(self):
        report_files = self.suite_reports_dir.files('*.xml')
        if self.timed_out:
            self._generate_custom_xunit_report(
                'Suite {0} timed out after {1} seconds.'.format(
                        self.descriptor, self.running_time),
                error_type='TestSuiteTimeout',
                error_message='Test suite timed out')
        elif not report_files:
            self._generate_custom_xunit_report(
                'Suite {0} has encountered an error before tests ran.'.format(
                        self.descriptor),
                error_type='TestSuiteSkipped',
                error_message='Test suite skipped')
        else:
            import lxml.etree as et
            logger.info('Suite [{0}] reports: {1}'.format(
                    self.suite_name, [r.name for r in report_files]))
            # adding suite name as a prefix to each test in each report
            parser = et.XMLParser(strip_cdata=False)
            for report in report_files:
                root = et.parse(report.realpath(), parser)
                test_elements = root.findall('testcase')
                for test in test_elements:
                    test_name = test.get('name')
                    test.set('name', test_name)
                tmp_file = tempfile.NamedTemporaryFile()
                tmp_file.write(et.tostring(root, pretty_print=True))
                # flushing remaining text in buffer before closing the file
                tmp_file.flush()
                shutil.copy(tmp_file.name, reports_dir / report.name)
                tmp_file.close()

    def _generate_custom_xunit_report(self,
                                      text,
                                      error_type,
                                      error_message,
                                      fetch_logs=True):
        logger.info('Getting docker logs for container: {0}'.format(
            self.container_name))
        if fetch_logs:
            logs = xunit.xml_safe(sh.docker.logs(
                self.container_name, _err_to_out=True).strip())
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


class Environments(object):

    def lock(self, env_id):
        raise NotImplementedError()

    def release(self, env_id):
        raise NotImplementedError()

    def prune(self, include_self=False):
        pass


class InMemoryEnvironments(Environments):

    def __init__(self):
        self._locked_envs = set()

    def lock(self, env_id):
        if env_id in self._locked_envs:
            return False
        self._locked_envs.add(env_id)
        return True

    def release(self, env_id):
        self._locked_envs.remove(env_id)


class FileEnvironments(Environments):

    def __init__(self, locked_environments_path):
        self._locked_environments_path = locked_environments_path
        self._locked_environments_lock = fasteners.InterProcessLock(
            '{}.lock'.format(locked_environments_path))

    def lock(self, env_id):
        with self._update() as locked_environments:
            if env_id in locked_environments:
                return False
            locked_environments[env_id] = os.getpid()
            return True

    def release(self, env_id):
        with self._update() as locked_environments:
            del locked_environments[env_id]

    def prune(self, include_self=False):
        with self._update() as locked_environments:
            current_pid = os.getpid()
            for k in locked_environments.keys():
                pid = locked_environments[k]
                if ((include_self and current_pid == pid) or
                        not is_pid_of_suites_runner(pid)):
                    del locked_environments[k]

    @contextmanager
    def _update(self):
        with self._locked_environments_lock:
            if os.path.exists(self._locked_environments_path):
                with open(self._locked_environments_path, 'r') as f:
                    locked_environments = json.load(f)
            else:
                locked_environments = {}
            yield locked_environments
            with open(self._locked_environments_path, 'w') as f:
                json.dump(locked_environments, f)


class SuitesScheduler(object):
    def __init__(self,
                 test_suites,
                 handler_configurations,
                 scheduling_interval=1,
                 optimize=False,
                 after_suite_callback=None,
                 suite_timeout=-1,
                 environments=None):
        self._test_suites = test_suites
        if optimize:
            self._test_suites = sorted(
                test_suites,
                key=lambda x: x.handler_configuration is None)
        self._handler_configurations = handler_configurations
        self._environments = environments or InMemoryEnvironments()
        self._scheduling_interval = scheduling_interval
        self._after_suite_callback = after_suite_callback
        self._suite_timeout = suite_timeout
        self._validate()
        self._log_test_suites()
        self.timed_out_suites = []
        self.failed_suites = []

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
                    config_names = matches.keys()
                    random.shuffle(config_names)
                    logger.info(
                        'Matching handler configurations for {0} are: {1}'
                        .format(suite.suite_name, ', '.join(config_names)))
                    for name in config_names:
                        configuration = matches[name]
                        if self._environments.lock(configuration['env']):
                            suite.handler_configuration = (name,
                                                           configuration)
                            suite.started = time.time()
                            logger.info(
                                'Suite {0} will run using handler '
                                'configuration: {1}'.format(
                                        suite.suite_name,
                                        suite.handler_configuration))
                            suite.run()
                            break
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
                    if suite.failed:
                        self.failed_suites.append(suite)
                # Suite timed out
                elif self._suite_timeout != -1 \
                        and suite.running_time > self._suite_timeout:
                    self.timed_out_suites.append(suite)
                    suite.timed_out = True
                    config = self._handler_configurations[
                        suite.handler_configuration]
                    logger.warn(
                        'Suite timed out: {0} [handler_configuration={1}, '
                        'suite_running_time={2}s]'.format(
                            suite.suite_name,
                            config,
                            int(suite.running_time)))
                    self._after_suite(suite)
                # Suite is running
                else:
                    remaining_suites.append(suite)
            suites_list = remaining_suites
            time.sleep(self._scheduling_interval)
        logger.info('Test suites scheduler stopped')

    def _after_suite(self, suite):
        suite.terminated = time.time()
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
        config = self._handler_configurations.get(suite.handler_configuration)
        if config:
            self._environments.release(config['env'])

    def _find_matching_handler_configurations(self, suite):
        if suite.handler_configuration:
            config = self._handler_configurations.get(
                suite.handler_configuration)
            return {
                suite.handler_configuration:
                    self._handler_configurations[suite.handler_configuration]
            } if config else {}

        def tags_match(x, y):
            return set(x) & set(y) == set(x)

        return {
            k: v for k, v in self._handler_configurations.iteritems()
            if tags_match(suite.requires, v.get('tags', set()))
        }


class SuitesRunner(object):

    def __init__(self, variables_path, descriptor):
        self.descriptor = descriptor
        self.variables_path = variables_path
        self.suites_yaml = None
        self.envs_dir = path.getcwd() / SUITE_ENVS_DIR

    def setenv(self):
        if os.path.exists(self.envs_dir):
            shutil.rmtree(self.envs_dir)

        if not reports_dir.exists():
            reports_dir.mkdir()
        for report in reports_dir.files():
            report.remove()

        logger.info('Generating suites yaml:\n'
                    '\descriptor={}'.format(self.descriptor))
        test_suites_path = build_suites_yaml('suites/suites.yaml',
                                             self.variables_path,
                                             self.descriptor)
        os.environ[TEST_SUITES_PATH] = test_suites_path
        with open(test_suites_path) as f:
            self.suites_yaml = yaml.safe_load(f)

    def validate(self):
        for suite_name, suite in self.suites_yaml['test_suites'].items():
            requires = suite.get('requires')
            configuration_name = suite.get('handler_configuration')
            if requires and configuration_name:
                raise AssertionError(
                    'Suite: {0} has both "requires" and '
                    '"handler_configuration" set'.format(suite_name))
            elif not requires and not configuration_name:
                raise AssertionError(
                    'Suite: {0} does not have "requires" or '
                    '""handler_configuration" specified'.format(suite_name))
        for name, configuration in self.suites_yaml[
                'handler_configurations'].iteritems():
            if 'env' not in configuration:
                raise AssertionError(
                    '"{0}" handler configuration does not contain an env '
                    'property'.format(name))

    def run_suites(self):
        self.build_docker_image()
        variables = self.suites_yaml.get('variables', {})
        test_suites = [
            TestSuite(suite_name=suite_name,
                      suite_def=suite_def,
                      suite_work_dir=self.envs_dir / suite_name,
                      variables=variables) for suite_name, suite_def in
            self.suites_yaml['test_suites'].iteritems()]
        environments_path = os.path.join(sys.prefix, 'environments.json')
        environments = FileEnvironments(
            locked_environments_path=environments_path)
        logger.info('Pruning environments before suites run')
        environments.prune()

        def sigterm_handler(num, frame):
            logger.info('Pruning environments on sigterm')
            environments.prune(include_self=True)
            logger.info('Pruning containers on sigterm')
            self.prune_containers(include_self=True)
            sys.exit(1)
        signal.signal(signal.SIGTERM, sigterm_handler)

        scheduler = SuitesScheduler(
            test_suites=test_suites,
            handler_configurations=self.suites_yaml['handler_configurations'],
            scheduling_interval=SCHEDULER_INTERVAL,
            optimize=True,
            after_suite_callback=TestSuite.after_suite,
            suite_timeout=60 * 60 * 5,
            environments=environments)
        scheduler.run()
        if scheduler.failed_suites or scheduler.timed_out_suites:
            logger.warn('Failed test suites: {0}'.format(
                ''.join(['\n\t{0} (exit_code: {1})'.format(x.suite_name,
                                                           x.exit_code)
                        for x in scheduler.failed_suites])))
            logger.warn('Timed out test suites: {0}'.format(
                ''.join(['\n\t{0}'.format(x.suite_name)
                         for x in scheduler.timed_out_suites])))
            sys.exit(1)

    @staticmethod
    def prune_containers(include_self=False):
        container_ids = sh.docker.ps(a=True, q=True).stdout.strip()
        container_ids = [c.strip() for c in container_ids.split(os.linesep)
                         if c.strip()]
        for container_id in container_ids:
            container_name = sh.docker.ps(filter='id={0}'.format(container_id),
                                          format='{{.Names}}').stdout.strip()
            split_container_name = container_name.split('_', 1)
            if len(split_container_name) < 2:
                continue
            try:
                pid = int(split_container_name[0])
            except ValueError:
                continue
            current_pid = os.getpid()
            if ((include_self and pid == current_pid) or
                    not is_pid_of_suites_runner(pid)):
                kill_container(container_id)

    def build_docker_image(self):
        docker.build(
                ['-t',
                 '{0}:{1}'.format(DOCKER_REPOSITORY, DOCKER_TAG), '.']).wait()
        docker_image_id = self._get_docker_image_id()
        if not docker_image_id:
            raise RuntimeError(
                    'Docker image not found after docker image was built.')

    @staticmethod
    def _get_docker_image_id():
        image_ids = [line for line in sh.docker.images(
                ['-q', DOCKER_REPOSITORY]).strip().split(os.linesep)
                 if len(line) > 0]
        if len(image_ids) > 1:
            raise RuntimeError(
                    'Found several docker image ids instead of a single one.')
        return image_ids[0] if image_ids else None


def kill_container(container_name):
    logger.info('Killing container: {0}'.format(container_name))
    docker.rm('-f', container_name).wait()


def is_pid_of_suites_runner(pid):
    try:
        os.kill(int(pid), 0)
    except (ValueError, OSError):
        return False
    try:
        cmd = sh.ps('h', p=str(pid), o='cmd').stdout.strip()
        return 'suites_runner' in cmd
    except sh.ErrorReturnCode:
        return False


def main():
    suites_runner = SuitesRunner(variables_path=sys.argv[1],
                                 descriptor=sys.argv[2])
    suites_runner.setenv()
    suites_runner.validate()
    logger.info('Pruning containers before suites run')
    suites_runner.prune_containers()
    suites_runner.run_suites()


if __name__ == '__main__':
    main()
