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

import threading
import Queue

from cosmo_tester.framework.util import YamlPatcher
from cosmo_tester.framework.testenv import TestCase
from cosmo_tester.framework.git_helper import clone
from cosmo_tester.test_suites.test_blueprints import hello_world_bash_test as \
    bash


class TwoDeploymentsTest(TestCase):

    def test_two_deployments(self):
        repo_dir = clone(bash.CLOUDIFY_HELLO_WORLD_EXAMPLE_URL, self.workdir)
        self.blueprint_path = repo_dir
        self.blueprint_yaml = self.blueprint_path / 'blueprint.yaml'

        count = 2

        deployments = [self.Deployment(self, i) for i in range(count)]

        for deployment in deployments:
            deployment.run()

        for deployment in deployments:
            deployment.wait_for()

    def run_deployment(self, index, queue):
        try:
            blueprint_id = '{}_{}'.format(self.test_id, index)
            deployment_id = blueprint_id
            file_name = 'blueprint{}.yaml'.format(index)
            blueprint_yaml = self.blueprint_path / file_name
            blueprint_yaml.write_text(self.blueprint_yaml.text())
            sg = 'sg{}'.format(index)
            self.modify_yaml(blueprint_path=blueprint_yaml,
                             security_group_name=sg)

            self.cfy.upload_deploy_and_execute_install(
                blueprint_path=blueprint_yaml,
                blueprint_id=blueprint_id,
                deployment_id=deployment_id,
                # inputs are not used (overridden by modify_yaml)
                inputs=dict(
                    agent_user='',
                    image='',
                    flavor='',
                ))

            outputs = self.client.deployments.outputs.get(
                deployment_id)['outputs']
            self.logger.info('Deployment outputs: {0}'.format(outputs))
            bash.verify_webserver_running(outputs['http_endpoint'])

            self.cfy.execute_uninstall(deployment_id=deployment_id)
        except Exception, e:
            queue.put(e)
        else:
            queue.put(True)

    def modify_yaml(self,
                    blueprint_path,
                    security_group_name):
        with YamlPatcher(blueprint_path) as patch:
            vm_properties_path = 'node_templates.vm.properties'
            patch.merge_obj(
                '{0}.agent_config'.format(vm_properties_path), {
                    'user': self.env.cloudify_agent_user,
                })
            patch.merge_obj('{0}'.format(vm_properties_path), {
                'image': self.env.ubuntu_trusty_image_name,
                'flavor': self.env.flavor_name,
            })
            sg_name_path = 'node_templates.security_group.properties' \
                           '.security_group.name'
            patch.set_value(sg_name_path, security_group_name)

    class Deployment(object):

        def __init__(self, test_case, index):
            self.index = index
            self.queue = Queue.Queue(maxsize=1)
            self.test_case = test_case
            self.thread = threading.Thread(target=test_case.run_deployment,
                                           args=(self.index, self.queue))

        def run(self):
            self.thread.start()

        def wait_for(self):
            result = self.queue.get(timeout=1800)
            if isinstance(result, Exception):
                raise result
