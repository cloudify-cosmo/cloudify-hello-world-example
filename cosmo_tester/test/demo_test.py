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
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.

__author__ = 'nirb'


from cosmo_tester.framework import cfy_helper, git_helper
from cosmo_tester.framework import testenv


class BootstrapTest(testenv.TestCase):

    def test_bootstrap(self):
        cfy = cfy_helper.CfyHelper()

        cfy.bootstrap(
            '/home/dan/work/cfy-openstack/cloudify-config.yaml',
            keep_up_on_failure=True,
            verbose=True,
            dev_mode=False,
            alternate_bootstrap_method=True
        )

        cfy.upload_deploy_and_execute_install(
            '/home/dan/dev/cosmo/cloudify-hello-world/openstack/blueprint.yaml',
            blueprint_id='b1',
            deployment_id='d1',
            verbose=False,
        )

    def test_uninstall(self):
        cfy = cfy_helper.CfyHelper('/tmp/tmp6mNw0o')
        cfy.execute_uninstall(deployment_id='d1',
                              verbose=False)

    def test_install(self):
        cfy = cfy_helper.CfyHelper(management_ip='192.168.15.15')
        cfy.execute_install(deployment_id='d1')

    def test_clone(self):
        git_helper.clone_if_needed(
            url='https://github.com/CloudifySource/cloudify-hello-world.git',
            target='/tmp/hello-world-tmp')
