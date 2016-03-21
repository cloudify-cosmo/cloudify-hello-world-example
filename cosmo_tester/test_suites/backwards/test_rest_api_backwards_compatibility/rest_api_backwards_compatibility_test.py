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
import pkg_resources
import subprocess
import jinja2

import cosmo_tester
from cosmo_tester.framework.testenv import TestCase


SHELL_SCRIPT_TEMPLATE = 'run_old_rest_client_in_shell.template'
PYTHON_SCRIPT_TEMPLATE = 'use_old_rest_client.template'
SHELL_SCRIPT_NAME = 'test_old_client.sh'
PYTHON_SCRIPT_NAME = 'test_old_client.py'
VENV_NAME = 'cfy_32_cli_env'
CFY_CLIENT_VERSION_1 = '3.2'
CFY_CLIENT_VERSION_2 = '3.3.1'
URL_VERSION_POSTFIX_1 = ''
URL_VERSION_POSTFIX_2 = '/api/v2'


class RestApiBackwardsCompatibilityTest(TestCase):

    def setUp(self):
        super(RestApiBackwardsCompatibilityTest, self).setUp()

    def _render_python_script(self, url_version_postfix):
        python_script_template = pkg_resources.resource_string(
            cosmo_tester.__name__,
            'resources/scripts/{0}'.format(PYTHON_SCRIPT_TEMPLATE)
        )
        rendered_python_script = jinja2.Template(python_script_template). \
            render(cfy_manager_ip=self.env.management_ip,
                   url_version_postfix=url_version_postfix)
        with open(os.path.join(self.workdir, PYTHON_SCRIPT_NAME), 'w') as f:
            f.write(rendered_python_script)

    def _render_shell_script(self, client_version):
        shell_script_template = pkg_resources.resource_string(
            cosmo_tester.__name__,
            'resources/scripts/{0}'.format(SHELL_SCRIPT_TEMPLATE)
        )
        template_values = {'work_dir': self.workdir,
                           'venv_name': VENV_NAME,
                           'client_version': client_version,
                           'python_script_name': PYTHON_SCRIPT_NAME}
        rendered_shell_script = jinja2.Template(shell_script_template).\
            render(template_values)
        shell_script_path = os.path.join(self.workdir, SHELL_SCRIPT_NAME)
        with open(shell_script_path, 'w') as f:
            f.write(rendered_shell_script)

        # set permission to execute file
        permissions = os.stat(shell_script_path)
        os.chmod(shell_script_path, permissions.st_mode | 0111)

    def test_3_2_client_vs_new_server(self):
        self._render_shell_script(CFY_CLIENT_VERSION_1)
        self._render_python_script(URL_VERSION_POSTFIX_1)
        self.run_script()

    def test_3_3_1_client_vs_new_server(self):
        self._render_shell_script(CFY_CLIENT_VERSION_2)
        self._render_python_script(URL_VERSION_POSTFIX_2)
        self.run_script()

    def run_script(self):
        output = subprocess.check_output(
            '/bin/bash {0}'.format(
                os.path.join(self.workdir, SHELL_SCRIPT_NAME)), shell=True)
        result = json.loads(output)
        self.assertEqual(result.get('exit_code'), 0,
                         'Failed to get manager status from old client, '
                         'error: {0}'.format(result.get('details')))
