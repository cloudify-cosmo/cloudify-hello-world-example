import os
import sys
import logging
from StringIO import StringIO

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

reports_dir = path(os.path.dirname(__file__)) / 'xunit-reports'

TEST_SUITES_PATH = 'TEST_SUITES_PATH'


def list_containers(quiet=False):
    return sh.docker.ps(a=True, q=quiet).strip()


def kill_containers():
    containers = list_containers(quiet=True)
    if containers:
        logger.info('Killing containers: {0}'.format(containers))
        docker.rm('-f', containers).wait()


def container_exit_code(container_name):
    return int(sh.docker.wait(container_name).strip())


def container_kill(container_name):
    logger.info('Killing container: {0}'.format(container_name))
    docker.rm('-f', container_name).wait()


def test_start():
    vagrant.up().wait()
    vagrant('docker-logs', f=True).wait()


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
    os.environ[TEST_SUITES_PATH] = build_suites_yaml('suites/suites.yaml',
                                                     variables_path)


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
