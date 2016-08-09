########
# Copyright (c) 2016 GigaSpaces Technologies Ltd. All rights reserved
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
import StringIO

from cosmo_tester.test_suites.test_dockercompute import DockerComputeTestCase
from cosmo_tester.test_suites.test_dockercompute.test_nodecellar import (
    DockerNodeCellar)
from cosmo_tester.test_suites.test_blueprints.nodecellar_test import (
    NodecellarAppTest)


class DockerComputeNodeCellarScaleTest(DockerComputeTestCase,
                                       NodecellarAppTest):

    def test_dockercompute_nodecellar_scale(self):
        nodecellar = DockerHAProxyNodeCellar(self)
        nodecellar.prepare()
        nodecellar.install()
        nodecellar.assert_installed()
        nodecellar.scale(delta=1)
        nodecellar.assert_post_scale(expected_instances=2)
        nodecellar.scale(delta=-1)
        nodecellar.assert_post_scale(expected_instances=1)
        nodecellar.uninstall()
        nodecellar.assert_uninstalled()


class DockerHAProxyNodeCellar(DockerNodeCellar):

    @property
    def blueprint_file(self):
        return 'dockercompute-haproxy-blueprint.yaml'

    @property
    def ip(self):
        if not self._ip:
            self._ip = self.test_case.ip('haproxy_frontend_host',
                                         deployment_id=self.deployment_id)
        return self._ip

    def scale(self, delta):
        parameters = dict(
            scalable_entity_name='nodecellar',
            delta=delta,
            scale_compute=True
        )
        parameters = self.test_case.get_parameters_in_temp_file(parameters,
                                                                'scale')
        self.test_case.cfy.executions.start(
            'scale',
            deployment_id=self.deployment_id,
            parameters=parameters
        )

    def assert_post_scale(self, expected_instances):
        initial_stats = self._read_haproxy_stats()
        number_of_backends = len(initial_stats)
        self.test_case.assertEqual(expected_instances, number_of_backends)
        for count in initial_stats.values():
            self.test_case.assertEqual(0, count)
        for i in range(1, number_of_backends + 1):
            self._webserver_request()
            stats = self._read_haproxy_stats()
            active_backends = [b for b, count in stats.items() if count == 1]
            self.test_case.assertEqual(i, len(active_backends))

    def _read_haproxy_stats(self):
        url = 'http://admin:password@{0}:9000/haproxy_stats;csv'.format(
            self.ip)
        csv_data = self.test_case.request(url)
        buff = StringIO.StringIO(csv_data)
        parsed_csv_data = list(csv.reader(buff))
        headers = parsed_csv_data[0]
        structured_csv_data = [dict(zip(headers, row))
                               for row in parsed_csv_data]
        return dict([(struct['svname'], int(struct['stot']))
                     for struct in structured_csv_data
                     if struct['# pxname'] == 'servers' and
                     struct['svname'] != 'BACKEND'])
