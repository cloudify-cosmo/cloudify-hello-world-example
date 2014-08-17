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

__author__ = 'boris'

from cosmo_tester.framework.git_helper import clone
import hello_world_bash_test as bash
from cosmo_tester.framework.testenv import TestCase


CLOUDIFY_EXAMPLES_URL = "https://github.com/cloudify-cosmo/" \
                        "cloudify-examples.git"

class UninstallAfterFailureTest(TestCase):
    #def test_uninstall_after_failure_on_ubuntu(self):
        #self._run(self.env.ubuntu_image_name, self.env.cloudify_agent_user)

    def _run(self, image_name, user):
        self.repo_dir = clone(CLOUDIFY_EXAMPLES_URL, self.workdir)
        self.blueprint_path = self.repo_dir / 'hello-world'
        self.blueprint_yaml = self.blueprint_path / 'blueprint.yaml'
        bash.modify_yaml(env=self.env,
                    yaml_file=self.blueprint_yaml,
                    host_name='bash-web-server',
                    image_name=image_name,
                    user=user,
                    security_groups=['jibrish'])
        try:
            self.upload_deploy_and_execute_install(fetch_state=False)
            self.fail("install should fail!")
        except Exception as e:
            print "failed to upload_deploy_install ", e
        try:
            self.execute_uninstall()
        except Exception as e:
            print "failed to uninstall ", e
            self.fail("uninstall failed!")

