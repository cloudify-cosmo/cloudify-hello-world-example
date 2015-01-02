# flake8: NOQA

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

env_variables = {
    'SYSTEM_TESTS_MANAGER_KEY': '',
    'SYSTEM_TESTS_AGENT_KEY': '',
    'TEST_SUITES_PATH': '',
    # opencm creds for private repos
    'OPENCM_GIT_PWD': '',
    # tokens used to access private repos
    'CLOUDIFY_AUTOMATION_TOKEN': '',

    # vSphere creds
    'VSPHERE_USERNAME': '',
    'VSPHERE_PASSWORD': '',
    'VSPHERE_URL': '',
    'VSPHERE_DATACENTER_NAME': '',

    # ec2 creds
    'AWS_ACCESS_ID': '',
    'AWS_SECRET_KEY': '',

    # keystone
    'HP_KEYSTONE_PASSWORD': '',
    'HP_KEYSTONE_USERNAME': '',

    # branch names
    'BRANCH_NAME_CORE': '',
    'BRANCH_NAME_PLUGINS': '',
    'BRANCH_NAME_OPENSTACK_PROVIDER': '',
    'BRANCH_NAME_LIBCLOUD_PROVIDER': '',
    'BRANCH_NAME_SYSTEM_TESTS': '',
    'BRANCH_NAME_CLI': '',
    'BRANCH_NAME_MANAGER_BLUEPRINTS': '',
    'BRANCH_NAME_VSPHERE_PLUGIN': '',

    # manager packages
    'COMPONENTS_PACKAGE_URL': '',
    'CORE_PACKAGE_URL': '',
    'UI_PACKAGE_URL': '',

    # agent packages
    'UBUNTU_PACKAGE_URL': '',
    'CENTOS_PACKAGE_URL': '',
    'WINDOWS_PACKAGE_URL': '',

    # docker packages
    'DOCKER_IMAGE_URL': '',
    'DOCKER_DATA_URL': '',
}


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


def test_logs():
    vagrant('docker-logs', f=True).wait()


def test_start():
    setup_reports_dir()
    vagrant.up().wait()


def test_run():
    logger.info('Current containers:\n{0}'
                .format(list_containers()))
    kill_containers()
    test_start()
    test_logs()
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
    if 'Docker version 1.1.2' not in sh.docker(version=True):
        raise RuntimeError('Tested with docker 1.1.2 only. If you know this will work with other versions, '
                           'Update this code to be more flexible')
    if 'Vagrant 1.6.3' not in sh.vagrant(version=True):
        raise RuntimeError('Tested with vagrant 1.6.3 only. If you know this will work with other versions, '
                           'Update this code to be more flexible')
    for env_var, default_value in env_variables.items():
        if default_value and not os.environ.get(env_var):
            os.environ[env_var] = default_value
    cloudify_environment_variable_names = ':'.join(env_variables.keys())
    os.environ['CLOUDIFY_ENVIRONMENT_VARIABLE_NAMES'] = cloudify_environment_variable_names
    if not os.environ.get('TEST_SUITES_PATH'):
        suite_json_path = build_suites_yaml('suites/suites.yaml')
        os.environ['TEST_SUITES_PATH'] = suite_json_path


def setup_reports_dir():
    if not reports_dir.exists():
        reports_dir.mkdir()
    for report in reports_dir.files():
        report.remove()


def get_containers_names():
    with open(os.environ['TEST_SUITES_PATH']) as f:
        suites = yaml.load(f.read())['test_suites'].keys()
    return [s for s in suites]


def main():
    setenv()
    test_run()

if __name__ == '__main__':
    main()
