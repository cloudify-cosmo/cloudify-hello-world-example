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

from cosmo_tester.test_suites.test_blueprints.nodecellar_test import (
    NodecellarAppTest)


class DockerPluginNodecellarTest(NodecellarAppTest):

    def test_docker_plugin_openstack_nodecellar(self):
        self._test_nodecellar_impl('openstack-blueprint.yaml')

    def get_inputs(self):

        return {
            'image': self.env.ubuntu_trusty_image_id,
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

    def _assert_mongodb_collector_data(self, influx_client):
        pass

    @property
    def nodecellar_port(self):
        return 8080

    @property
    def entrypoint_node_name(self):
        return 'nodecellar_floatingip'
