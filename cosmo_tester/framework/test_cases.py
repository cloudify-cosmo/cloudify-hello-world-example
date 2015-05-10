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


from influxdb import InfluxDBClient


def _assert_general_deployment_data(instance, influx_client):

    try:
        # select monitoring events for deployment from
        # the past 5 seconds. a NameError will be thrown only if NO
        # deployment events exist in the DB regardless of time-span
        # in query.
        influx_client.query('select * from /^{0}\./i '
                            'where time > now() - 5s'
                            .format(instance.test_id))
    except NameError as e:
        instance.fail('monitoring events list for deployment with ID {0} were'
                      ' not found on influxDB. error is: {1}'
                      .format(instance.deployment_id, e))
0

def assert_monitoring_data_exists(instance):
    client = InfluxDBClient(instance.env.management_ip, 8086, 'root', 'root',
                            'cloudify')
    _assert_general_deployment_data(instance, client)

def assert_outputs(instance,expected_output)
    outputs = instance.client.deployments.outputs.get(instance.test_id)
    outputs = outputs['outputs']
    instance.assertEqual(expected_output, outputs)
