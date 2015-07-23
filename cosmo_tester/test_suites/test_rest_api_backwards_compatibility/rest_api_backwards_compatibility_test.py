########
# Copyright (c) 2015 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.


import json
import os
import shutil
import subprocess

from cosmo_tester.framework.testenv import TestCase


SHELL_SCRIPT_NAME = 'test_old_client.sh'
PYTHON_SCRIPT_NAME = 'test_old_client.py'
VIRTUAL_ENV = 'cfy_32_cli_env'
CFY_CLIENT_VERSION = '3.2'


class RestApiBackwardsCompatibilityTest(TestCase):

    def setUp(self):
        super(RestApiBackwardsCompatibilityTest, self).setUp()
        self._create_python_script(PYTHON_SCRIPT_NAME, self.env.management_ip)
        self._create_shell_script(SHELL_SCRIPT_NAME,
                                  PYTHON_SCRIPT_NAME,
                                  VIRTUAL_ENV,
                                  CFY_CLIENT_VERSION)

    def tearDown(self):
        if os.path.exists(VIRTUAL_ENV):
            shutil.rmtree(VIRTUAL_ENV)

        if os.path.exists(PYTHON_SCRIPT_NAME):
            os.remove(PYTHON_SCRIPT_NAME)

        if os.path.exists(SHELL_SCRIPT_NAME):
            os.remove(SHELL_SCRIPT_NAME)

        super(RestApiBackwardsCompatibilityTest, self).tearDown()

    def _create_python_script(self, python_script_name, cfy_manager_ip):
        with open(python_script_name, 'w') as f:
            f.write('import json\n')
            f.write('from cloudify_rest_client.client import CloudifyClient\n')
            f.write('def run_test():\n')
            f.write('    output = {}\n')
            f.write('    try:\n')
            f.write('        rest_client = CloudifyClient(host="{0}")\n'
                    .format(cfy_manager_ip))
            f.write('        rest_client_url = rest_client._client.url\n')
            f.write('        expected_rest_client_url = "http://{0}:80"\n'
                    .format(cfy_manager_ip))
            f.write('        if rest_client_url==expected_rest_client_url:\n')
            f.write('            status = rest_client.manager.get_status()\n')
            f.write('            output["exit_code"] = 0\n')
            f.write('            output["details"] = status\n')
            f.write('        else:\n')
            f.write('            output["exit_code"] = 1\n')
            f.write('            output["details"] = "rest client url is {0} '
                    'instead of {1}".format(rest_client_url, '
                    'expected_rest_client_url)\n')
            f.write('    except Exception as e:\n')
            f.write('        output["exit_code"] = 1\n')
            f.write('        output["details"] = e.message\n')
            f.write('    return output\n')
            f.write('out = run_test()\n')
            f.write('print json.dumps(out)')

    def _create_shell_script(self, shell_script_name, python_script_name,
                             env_name, cfy_client_version):
        with open(shell_script_name, 'w') as f:
            f.write('virtualenv {0} >/dev/null\n'.format(env_name))
            f.write('source {0}/bin/activate >/dev/null\n'.format(env_name))
            f.write('pip install cloudify=={0} >/dev/null\n'
                    .format(cfy_client_version))
            f.write('python {0}\n'.format(python_script_name))
        permissions = os.stat(shell_script_name)
        os.chmod(shell_script_name, permissions.st_mode | 0111)

    def test_old_client_vs_new_server(self):
        output = subprocess.check_output(
            '/bin/bash {0}'.format(SHELL_SCRIPT_NAME), shell=True)
        print('output: {0}'.format(output))
        result = json.loads(output)
        self.assertEqual(result.get('exit_code'), 0,
                         'Failed to get manager status from old client, '
                         'error: {0}'.format(result.get('details')))
