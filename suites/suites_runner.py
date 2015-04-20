import os
import sys
import logging
import json
import shutil
import time
from StringIO import StringIO

import jinja2
import yaml
import sh
from path import path

from helpers import sh_bake
from helpers.suites_builder import build_suites_yaml

logging.basicConfig()

logger = logging.getLogger('suites_runner')
logger.setLevel(logging.INFO)

docker = sh_bake(sh.docker)
vagrant = sh_bake(sh.vagrant)

reports_dir = path(__file__).dirname() / 'xunit-reports'

TEST_SUITES_PATH = 'TEST_SUITES_PATH'
DOCKER_REPOSITORY = 'cloudify/test'
DOCKER_TAG = 'env'
SUITE_ENVS_DIR = 'suite-envs'
WAIT_FOR_SUITES_INTERVAL = 30


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


class TestSuite(object):

    def __init__(self, suite_name, suite_def, suite_work_dir):
        self.suite_name = suite_name
        self.suite_def = suite_def
        self.suite_work_dir = suite_work_dir
        self.suite_reports_dir = suite_work_dir / 'xunit-reports'
        self.process = None

    def create_env(self, variables):
        self.suite_work_dir.makedirs()
        self.suite_reports_dir.makedirs()
        vagrant_file_template = path('Vagrantfile.template').text()
        vagrant_file_content = jinja2.Template(vagrant_file_template).render({
            'suite_name': self.suite_name,
            'suite': json.dumps(self.suite_def),
            'variables': json.dumps(variables)
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
        logger.info('Starting suite in docker container: {0}'.format(
            self.suite_name))
        cwd = path.getcwd()
        try:
            os.chdir(self.suite_work_dir)
            vagrant.up().wait()
            self.process = vagrant('docker-logs', f=True, _bg=True).process
        finally:
            os.chdir(cwd)

    def copy_xunit_reports(self):
        report_files = self.suite_reports_dir.files('*.xml')
        logger.info('Suite [{0}] reports: {1}'.format(
            self.suite_name, [r.name for r in report_files]))
        for report in report_files:
            report.copy(reports_dir / report.name)


def wait_for_suites(running_suites):
    running_suites = {suite.suite_name: suite for suite in running_suites}
    while running_suites:
        logger.info(
            'Waiting for the following suites to terminate: {0}'.format(
                running_suites.keys()))
        time.sleep(WAIT_FOR_SUITES_INTERVAL)
        for suite_name in running_suites.keys():
            suite = running_suites[suite_name]
            if not suite.is_running:
                logger.info('Suite terminated: {0}'.format(suite.suite_name))
                del running_suites[suite_name]


def test_start():
    if os.path.exists(SUITE_ENVS_DIR):
        shutil.rmtree(SUITE_ENVS_DIR)

    with open(os.environ[TEST_SUITES_PATH]) as f:
        suites_yaml = yaml.load(f.read())
    variables = suites_yaml.get('variables', {})

    build_docker_image()

    envs_dir = path.getcwd() / SUITE_ENVS_DIR
    running_suites = []

    for suite_name, suite_def in suites_yaml['test_suites'].iteritems():
        logger.info(
            'Processing suite: {0} - {1}'.format(suite_name, suite_def))
        suite = TestSuite(suite_name, suite_def, envs_dir / suite_name)
        suite.create_env(variables)
        suite.run()
        running_suites.append(suite)

    wait_for_suites(running_suites)

    for suite in running_suites:
        suite.copy_xunit_reports()


def test_run():
    test_start()
    logger.info('wait for containers exit status codes')
    containers = get_containers_names()
    exit_codes = [(c, container_exit_code(c)) for c in containers]
    logger.info('removing containers')
    for c in containers:
        container_kill(c)
    failed_containers = [(c, exit_code)
                         for c, exit_code in exit_codes
                         if exit_code != 0]
    if failed_containers:
        logger.info('Failed test suites:')
        for c, exit_code in failed_containers:
            logger.info('\t{}: exit code: {}'.format(c, exit_code))
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
    handler_configurations = suites['handler_configurations']
    environments = {}
    for suite_name, suite in suites['test_suites'].items():
        configuration = handler_configurations[suite['handler_configuration']]
        env = configuration.get('env', configuration['handler'])
        if env not in environments:
            environments[env] = []
        environments[env].append(suite_name)
    validation_error = False
    message = StringIO()
    message.write('Multiple tests suites found for same environments:\n')
    for env, suite_names in environments.items():
        if len(suite_names) > 1:
            validation_error = True
            message.write('\t{0}: {1}'.format(env, suite_names))
    if validation_error:
        raise AssertionError(message.getvalue())


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
    setenv(variables_path)
    cleanup()
    validate()
    test_run()

if __name__ == '__main__':
    main()
