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

from cosmo_tester.test_suites.test_dockercompute import DockerComputeTestCase
from cosmo_tester.test_suites.test_dockercompute.test_helloworld import (
    DockerHelloWorld)


class TwoDeploymentsTest(DockerComputeTestCase):

    def test_two_concurrent_deployments(self):
        count = 2
        deployments = [self.Deployment(self, i) for i in range(count)]
        deployments[0].helloworld.prepare()
        for deployment in deployments:
            deployment.run()
        for deployment in deployments:
            deployment.wait_for()

    @staticmethod
    def run_deployment(helloworld, queue):
        try:
            helloworld.install()
            helloworld.assert_installed()
            helloworld.uninstall()
        except Exception, e:
            queue.put(e)
        else:
            queue.put(True)

    class Deployment(object):

        def __init__(self, test_case, index):
            self.test_case = test_case
            self.queue = Queue.Queue(maxsize=1)
            blueprint_id = '{}_{}'.format(test_case.test_id, index)
            deployment_id = blueprint_id
            self.helloworld = DockerHelloWorld(
                test_case,
                blueprint_id=blueprint_id,
                deployment_id=deployment_id)
            self.thread = threading.Thread(target=test_case.run_deployment,
                                           args=(self.helloworld, self.queue))

        def run(self):
            self.thread.start()

        def wait_for(self):
            result = self.queue.get(timeout=1800)
            if isinstance(result, Exception):
                raise result
