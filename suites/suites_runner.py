#! /usr/bin/env python
# flake8: NOQA

import os
import sys
import json
import logging

import sh
from path import path

from helpers.suites_builder import build_suites_json

logging.basicConfig()

logger = logging.getLogger('suites_runner')
logger.setLevel(logging.INFO)

def sh_bake(command):
    return command.bake(_out=lambda line: sys.stdout.write(line),
                        _err=lambda line: sys.stderr.write(line))

docker = sh_bake(sh.docker)
vagrant = sh_bake(sh.vagrant)

reports_dir = path('xunit-reports')

env_variables = {
    'TEST_SUITES_PATH': '',

    # keystone
    'KEYSTONE_PASSWORD': '',
    'KEYSTONE_USERNAME': '',
    'KEYSTONE_TENANT': '',
    'KEYSTONE_AUTH_URL': '',

    # branch names
    'BRANCH_NAME': 'master',
    'BRANCH_NAME_OPENSTACK_PROVIDER': '',
    'BRANCH_NAME_SYSTEM_TESTS': '',
    'BRANCH_NAME_CLI': '',

    # packages
    'COMPONENTS_PACKAGE_URL': '',
    'CORE_PACKAGE_URL': '',
    'UBUNTU_PACKAGE_URL': '',
    'CENTOS_PACKAGE_URL': '',
    'WINDOWS_PACKAGE_URL': '',
    'UI_PACKAGE_URL': ''
}

def container_exit_code(container_name):
    return int(sh.docker.wait(container_name).strip())

def container_kill(container_name):
    docker.rm('-f', container_name).wait()

def test_logs():
    vagrant('docker-logs', f=True).wait()

def test_start():
    setup_reports_dir()
    vagrant.up().wait()

def test_run():
    containers = get_containers_names()
    test_start()
    test_logs()
    logger.info('wait for containers exit status codes')
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
    cloudify_enviroment_varaible_names = ':'.join(env_variables.keys())
    os.environ['CLOUDIFY_ENVIRONMENT_VARIABLE_NAMES'] = cloudify_enviroment_varaible_names
    if not os.environ.get('TEST_SUITES_PATH'):
        suite_json_path = build_suites_json('suites/suites.json')
        os.environ['TEST_SUITES_PATH'] = suite_json_path

def setup_reports_dir():
    if not reports_dir.exists():
        reports_dir.mkdir()
    for report in reports_dir.files():
        report.remove()

def get_containers_names():
    with open(os.environ['TEST_SUITES_PATH']) as f:
        suites = json.loads(f.read())
    return [s['suite_name'] for s in suites]

def main():
    setenv()
    test_run()

if __name__ == '__main__':
    main()
