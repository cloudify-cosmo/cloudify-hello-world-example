import os
import tempfile
import logging

import yaml

logger = logging.getLogger('suites_builder')
logger.setLevel(logging.INFO)


def build_suites_yaml(all_suites_yaml_path, variables_path):
    env_system_tests_suites = os.environ['SYSTEM_TESTS_SUITES']
    env_custom = os.environ['SYSTEM_TESTS_CUSTOM']
    env_custom_descriptor = os.environ['SYSTEM_TESTS_CUSTOM_DESCRIPTOR']

    logger.info('Generating suites yaml:\n'
                '\tSYSTEM_TESTS_SUITES={}\n'
                '\tSYSTEM_TESTS_CUSTOM={}\n'
                '\tSYSTEM_TESTS_CUSTOM_DESCRIPTOR={}\n'
                .format(env_system_tests_suites,
                        env_custom,
                        env_custom_descriptor))

    tests_suites_names = [s.strip() for s
                          in env_system_tests_suites.split(',')]
    custom = env_custom == 'yes'

    with open(variables_path) as f:
        variables = yaml.load(f.read())
    with open(all_suites_yaml_path) as f:
        suites_yaml = yaml.load(f.read())
    suites_yaml_path = tempfile.mktemp(prefix='suites-', suffix='.json')

    if custom:
        test_suites = parse_custom_descriptor(env_custom_descriptor)
    else:
        test_suites = {suite_name: suite for suite_name, suite
                       in suites_yaml['test_suites'].items()
                       if suite_name in tests_suites_names}

    suites_yaml['variables'] = suites_yaml.get('variables', {})
    suites_yaml['variables'].update(variables)
    suites_yaml['test_suites'] = test_suites
    with open(suites_yaml_path, 'w') as f:
        f.write(yaml.safe_dump(suites_yaml))

    return suites_yaml_path


def parse_custom_descriptor(custom_descriptor):
    result = {}
    suite_descriptors = [s.strip() for s in custom_descriptor.split('#')]
    for i, suite_descriptor in enumerate(suite_descriptors, start=1):
        tests, handler_configuration = suite_descriptor.split('@')
        tests = [s.strip() for s in tests.split(',')]
        handler_configuration = handler_configuration.strip()
        result['{0}{1}'.format(handler_configuration, i)] = {
            'handler_configuration': handler_configuration,
            'tests': tests
        }
    return result
