#! /usr/bin/env python
# flake8: NOQA

import os
import json
import tempfile
import logging

import yaml

logger = logging.getLogger('suites_builder')
logger.setLevel(logging.INFO)


def build_suites_yaml(all_suites_yaml_path):
    env_system_tests_suites = os.environ['SYSTEM_TESTS_SUITES']
    env_custom_suite = os.environ['SYSTEM_TESTS_CUSTOM_SUITE']
    env_custom_suite_name = os.environ['SYSTEM_TESTS_CUSTOM_SUITE_NAME']
    env_custom_handler_configuration = os.environ['SYSTEM_TESTS_CUSTOM_HANDLER_CONFIGURATION']
    env_custom_tests_to_run = os.environ['SYSTEM_TESTS_CUSTOM_TESTS_TO_RUN']

    logger.info('Creating suites json configuration:\n'
                '\tSYSTEM_TESTS_SUITES={}\n'
                '\tSYSTEM_TESTS_CUSTOM_SUITE={}\n'
                '\tSYSTEM_TESTS_CUSTOM_SUITE_NAME={}\n'
                '\tSYSTEM_TESTS_CUSTOM_TESTS_TO_RUN={}\n'
                '\tSYSTEM_TESTS_CUSTOM_HANDLER_CONFIGURATION={}\n'
                .format(env_system_tests_suites,
                        env_custom_suite,
                        env_custom_suite_name,
                        env_custom_tests_to_run,
                        env_custom_handler_configuration))

    tests_suites_names = [s.strip() for s in env_system_tests_suites.split(',')]
    custom_suite = env_custom_suite == 'yes'
    custom_suite_name = env_custom_suite_name
    custom_tests_to_run = [s.strip() for s in env_custom_tests_to_run.split(',')]
    custom_handler_configuration = env_custom_handler_configuration

    with open(all_suites_yaml_path) as f:
        suites_yaml = yaml.load(f.read())
    suites_yaml_path = tempfile.mktemp(prefix='suites-', suffix='.json')

    if custom_suite:
        test_suites = {
            custom_suite_name: {
                'tests': custom_tests_to_run,
                'handler_configuration': custom_handler_configuration
            }
        }
    else:
        all_test_suites = suites_yaml['test_suites']
        test_suites = {suite_name: suite for suite_name, suite in all_test_suites
                       if suite_name in tests_suites_names}

    suites_yaml['test_suites'] = test_suites
    with open(suites_yaml_path, 'w') as f:
        f.write(yaml.safe_dump(suites_yaml))

    return suites_yaml_path
