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

import os

from cosmo_tester.framework.git_helper import clone
from cosmo_tester.test_suites.test_blueprints.nodecellar_test import (
    NodecellarAppTest)


class NodecellarDockerPluginTest(NodecellarAppTest):

    def _test_nodecellar_impl(self, blueprint_file):
        self.repo_dir = clone(self.repo_url, self.workdir, self.repo_branch)
        self.blueprint_yaml = os.path.join(self.repo_dir, blueprint_file)

        self.modify_blueprint()

        before, after = self.upload_deploy_and_execute_install(
            inputs=self.get_inputs()
        )

        self.post_install_assertions(before, after)

        self.execute_uninstall()

        self.post_uninstall_assertions()

    def test_openstack_nodecellar_docker_plugin(self):
        self._test_nodecellar_impl('blueprint/openstack.yaml')

    def get_inputs(self):

        return {
            'image': self.env.ubuntu_image_id,
            'flavor': self.env.small_flavor_id,
            'agent_user': 'ubuntu',
            'web_port': 8080,
            'mongo_port': 27017,
            'web_status_port': 28017,
            'nodecellar_container_port_bindings': {8080: 8080},
            'mongo_container_port_bindings': {27017: 27017, 28017: 28017}
        }

    @property
    def repo_url(self):
        return 'https://github.com/cloudify-cosmo/' \
               'cloudify-nodecellar-docker-example.git'

    @property
    def repo_branch(self):
        return None  # will use git_helper.clone default branch

    @property
    def expected_nodes_count(self):
        return 7
