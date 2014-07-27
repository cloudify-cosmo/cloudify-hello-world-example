#! /usr/bin/env python
# flake8: NOQA

import sys
import os
import json
import tempfile

all_suites_json_path = 'suites.json'
tests_suites = os.environ['SYSTEM_TESTS_SUITES'].split(',')
custom_suite = os.environ['SYSTEM_TESTS_CUSTOM_SUITE'] == 'yes'
custom_suite_name = os.environ['SYSTEM_TESTS_CUSTOM_SUITE_NAME']
custom_tests_to_run = os.environ['SYSTEM_TESTS_CUSTOM_TESTS_TO_RUN']
custom_cloudify_config = os.environ['SYSTEM_TESTS_CUSTOM_CLOUDIFY_CONFIG']
custom_handler_module = os.environ['SYSTEM_TESTS_CUSTOM_HANDLER_MODULE']

suites_json_path = tempfile.mktemp(prefix='suites-', suffix='.json')

if custom_suite:
    suites = [{
        'suite_name': custom_suite_name,
        'tests_to_run': custom_tests_to_run,
        'cloudify_test_config': custom_cloudify_config,
        'cloudify_test_handler_module': custom_handler_module
    }]
else:
    with open(all_suites_json_path) as f:
        all_suites = json.loads(f.read())
    suites = []
    for suite in all_suites:
        if suite['suite_name'] in tests_suites:
            suites.append(suite)

with open(suites_json_path, 'w') as f:
    f.write(json.dumps(suites))

sys.stdout.write(suites_json_path)
