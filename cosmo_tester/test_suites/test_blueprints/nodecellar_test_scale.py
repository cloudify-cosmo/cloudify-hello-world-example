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

import csv
from StringIO import StringIO

import requests

from cosmo_tester.framework.git_helper import clone
from cosmo_tester.framework.util import YamlPatcher
from cosmo_tester.test_suites.test_blueprints.nodecellar_test import (
    OpenStackNodeCellarTestBase)


class OpenStackScaleNodeCellarTest(OpenStackNodeCellarTestBase):

    def _test_nodecellar_impl(self, blueprint_file):
        self.addCleanup(self._test_cleanup)
        self.repo_dir = clone(self.repo_url, self.workdir)
        self.blueprint_yaml = self.repo_dir / blueprint_file

        self.modify_blueprint()

        # install
        before_install, after_install = self.upload_deploy_and_execute_install(
            inputs=self.get_inputs())
        self.post_install_assertions(before_install, after_install)

        # scale out (+1)
        self._scale(delta=1)
        self.post_scale_assertions(expected_instances=2)

        # scale in (-1)
        self._scale(delta=-1)
        self.post_scale_assertions(expected_instances=1)

        # uninstall
        self.execute_uninstall()
        self.post_uninstall_assertions()

    def test_openstack_scale_nodecellar(self):
        self._test_openstack_nodecellar('openstack-haproxy-blueprint.yaml')

    def post_scale_assertions(self, expected_instances):
        instances = self.client.node_instances.list(deployment_id=self.test_id,
                                                    _include=['id'])
        self.assertEqual(len(instances), self._expected_node_instances_count(
            nodejs_instances=expected_instances))
        self.assert_nodecellar_working(
            self.public_ip,
            expected_number_of_backends=expected_instances)

    @property
    def entrypoint_node_name(self):
        return 'nodecellar_ip'

    @property
    def nodecellar_port(self):
        return 8080

    @property
    def expected_nodes_count(self):
        return self._expected_node_instances_count(nodejs_instances=1)

    def _expected_node_instances_count(self, nodejs_instances):
        # 8 1 instance nodes + (nodecellar contained in nodejs
        #                       contained in nodejs_host) * num_host_instances
        return 8 + 3 * nodejs_instances

    def _scale(self, delta):
        parameters = dict(
            scalable_entity_name='nodecellar',
            delta=delta,
            scale_compute=True
        )
        parameters = self.get_parameters_in_temp_file(parameters, 'scale')
        self.cfy.executions.start(
            'scale',
            deployment_id=self.test_id,
            parameters=parameters
        )

    def _test_cleanup(self):
        try:
            self.cfy.deployments.delete(self.test_id, force=True)
            self.cfy.blueprints.delete(self.test_id)
        except Exception as e:
            self.logger.info('During cleanup: {0}'.format(e))

    # override base
    def assert_nodecellar_working(self, public_ip,
                                  # initial invocation is made
                                  # at the end of post_install_assertions
                                  expected_number_of_backends=1):
        initial_stats = self._read_haproxy_stats()
        number_of_backends = len(initial_stats)
        self.assertEqual(expected_number_of_backends, number_of_backends)
        for count in initial_stats.values():
            self.assertEqual(0, count)
        for i in range(1, number_of_backends + 1):
            self._get_wines_request()
            stats = self._read_haproxy_stats()
            active_backends = [b for b, count in stats.items() if count == 1]
            self.assertEqual(i, len(active_backends))

    def _read_haproxy_stats(self):
        csv_data = requests.get(
            'http://{0}:9000/haproxy_stats;csv'.format(self.public_ip),
            auth=('admin', 'password')).text
        buff = StringIO(csv_data)
        parsed_csv_data = list(csv.reader(buff))
        headers = parsed_csv_data[0]
        structured_csv_data = [dict(zip(headers, row))
                               for row in parsed_csv_data]
        return dict([(struct['svname'], int(struct['stot']))
                     for struct in structured_csv_data
                     if struct['# pxname'] == 'servers' and
                     struct['svname'] != 'BACKEND'])

    def modify_blueprint(self):
        with YamlPatcher(self.blueprint_yaml) as patch:
            patch.set_value('node_templates.nodejs_host.instances.deploy', 1)
