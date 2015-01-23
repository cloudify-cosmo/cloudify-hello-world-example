import tempfile
import logging

import yaml

logger = logging.getLogger('suites_builder')
logger.setLevel(logging.INFO)


def build_suites_yaml(all_suites_yaml_path,
                      variables_path,
                      descriptor):

    logger.info('Generating suites yaml:\n'
                '\descriptor={}'.format(descriptor))

    with open(variables_path) as f:
        variables = yaml.load(f.read())
    with open(all_suites_yaml_path) as f:
        suites_yaml = yaml.load(f.read())
    suites_yaml_path = tempfile.mktemp(prefix='suites-', suffix='.json')

    test_suites = parse_descriptor(suites_yaml, descriptor)

    suites_yaml['variables'] = suites_yaml.get('variables', {})
    suites_yaml['variables'].update(variables)
    suites_yaml['test_suites'] = test_suites
    with open(suites_yaml_path, 'w') as f:
        f.write(yaml.safe_dump(suites_yaml))

    return suites_yaml_path


def parse_descriptor(suites_yaml, custom_descriptor):
    preconfigured = suites_yaml['test_suites']
    result = {}
    suite_descriptors = [s.strip() for s in custom_descriptor.split('#')]
    for i, suite_descriptor in enumerate(suite_descriptors, start=1):
        if '@' in suite_descriptor:
            # custom suite
            tests, handler_configuration = suite_descriptor.split('@')
            tests = [s.strip() for s in tests.split(',')]
            handler_configuration = handler_configuration.strip()
            result['{0}_{1}'.format(handler_configuration, i)] = {
                'handler_configuration': handler_configuration,
                'tests': tests
            }

        else:
            result[suite_descriptor] = preconfigured[suite_descriptor]
    return result
