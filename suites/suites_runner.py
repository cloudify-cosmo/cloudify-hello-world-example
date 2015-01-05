import os
import sys
import logging

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

env_variables = [
    'BRANCH_NAME_SYSTEM_TESTS',
    'BRANCH_NAME_CORE',
    'BRANCH_NAME_PLUGINS',
    'SYSTEM_TESTS_MANAGER_KEY',
    'SYSTEM_TESTS_AGENT_KEY',
    'OPENCM_GIT_PWD',
    'CLOUDIFY_AUTOMATION_TOKEN',

    'COMPONENTS_PACKAGE_URL',
    'CORE_PACKAGE_URL',
    'UI_PACKAGE_URL',
    'UBUNTU_PACKAGE_URL',
    'CENTOS_PACKAGE_URL',
    'WINDOWS_PACKAGE_URL',
    'DOCKER_IMAGE_URL',

    'VSPHERE_USERNAME',
    'VSPHERE_PASSWORD',
    'VSPHERE_URL',
    'VSPHERE_DATACENTER_NAME',

    'SOFTLAYER_USERNAME',
    'SOFTLAYER_API_KEY',

    'AWS_ACCESS_ID',
    'AWS_SECRET_KEY',

    'HP_KEYSTONE_PASSWORD',
    'HP_KEYSTONE_USERNAME',
]


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


def setenv():
    setup_reports_dir()
    os.environ['CLOUDIFY_ENVIRONMENT_VARIABLE_NAMES'] = ':'.join(env_variables)
    os.environ[TEST_SUITES_PATH] = build_suites_yaml('suites/suites.yaml')


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
    setenv()
    cleanup()
    test_run()

if __name__ == '__main__':
    main()
