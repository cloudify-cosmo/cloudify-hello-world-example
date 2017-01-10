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
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import tempfile

import yaml


def build_suites_yaml(all_suites_yaml_path,
                      variables_path,
                      descriptor,
                      resources_package):
    with open(variables_path) as f:
        variables = yaml.load(f.read())
    with open(all_suites_yaml_path) as f:
        suites_yaml = yaml.load(f.read())
    suites_yaml_path = tempfile.mktemp(prefix='suites-', suffix='.json')
    test_suites = parse_descriptor(suites_yaml, descriptor)
    suites_yaml['variables'] = suites_yaml.get('variables', {})
    suites_yaml['variables']['manager_resources_package'] = resources_package
    suites_yaml['variables'].update(variables)
    suites_yaml['test_suites'] = test_suites
    with open(suites_yaml_path, 'w') as f:
        f.write(yaml.safe_dump(suites_yaml))
    return suites_yaml_path


def parse_descriptor(suites_yaml, custom_descriptor):
    preconfigured = suites_yaml['test_suites']
    configurations = suites_yaml['handler_configurations']
    result = {}
    suite_descriptors = [s.strip() for s in custom_descriptor.split('#')]
    for i, suite_descriptor in enumerate(suite_descriptors, start=1):
        if '@' in suite_descriptor:
            # custom suite
            descriptor_parts = suite_descriptor.split('@')
            tests, handler_configuration = \
                descriptor_parts[0], descriptor_parts[-1]

            tests = [s.strip() for s in tests.split(',')]
            handler_configuration = [
                s.strip() for s in handler_configuration.split(',')]
            suite_id = '{0}_{1}'.format('-'.join(handler_configuration), i)
            result[suite_id] = {'tests': tests}

            if len(descriptor_parts) == 3:
                external = descriptor_parts[1]
                external = external.split(';')
                external = [e.split('=') for e in external]
                external = {key.strip(): value.strip()
                            for key, value in external}
                result[suite_id]['external'] = external

            if len(handler_configuration) == 1 and handler_configuration[0] \
                    in configurations:
                result[suite_id]['handler_configuration'] = \
                    handler_configuration[0]
            else:
                result[suite_id]['requires'] = handler_configuration
        else:
            suite_id = suite_descriptor
            result[suite_id] = preconfigured[suite_descriptor]
        result[suite_id]['descriptor'] = suite_descriptor
    return result
