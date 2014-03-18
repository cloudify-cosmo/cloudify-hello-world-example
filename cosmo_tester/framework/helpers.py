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

__author__ = 'dan'

import logging

logger = logging.getLogger("helpers")
logger.setLevel(logging.INFO)


def get_manager_state(self):
    logger.info('Fetching manager current state')
    blueprints = {}
    for blueprint in self.rest.list_blueprints():
        blueprints[blueprint.id] = blueprint
    deployments = {}
    for deployment in self.rest.list_deployments():
        deployments[deployment.id] = deployment
    nodes = {}
    for deployment_id in deployments.keys():
        for node in self.rest.list_deployment_nodes(deployment_id).nodes:
            nodes[node.id] = node
    workflows = {}
    deployment_nodes = {}
    node_state = {}
    for deployment_id in deployments.keys():
        workflows[deployment_id] = self.rest.list_workflows(deployment_id)
        deployment_nodes[deployment_id] = self.rest.list_deployment_nodes(
            deployment_id,
            get_state=True)
        node_state[deployment_id] = {}
        for node in deployment_nodes[deployment_id].nodes:
            node_state[deployment_id][node.id] = self.rest.get_node_state(
                node.id,
                get_state=True,
                get_runtime_properties=True)

    return {
        'blueprints': blueprints,
        'deployments': deployments,
        'workflows': workflows,
        'nodes': nodes,
        'node_state': node_state,
        'deployment_nodes': deployment_nodes
    }