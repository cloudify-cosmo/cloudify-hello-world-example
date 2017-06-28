########
# Copyright (c) 2017 GigaSpaces Technologies Ltd. All rights reserved
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

import pytest
import requests

from cosmo_tester.framework.examples.nodecellar import NodeCellarExample
from cosmo_tester.framework.fixtures import image_based_manager
from cosmo_tester.framework.util import get_test_tenant, set_client_tenant

manager = image_based_manager


@pytest.fixture(scope='function')
def nodecellar(cfy, manager, attributes, ssh_key, tmpdir, logger):
    tenant = get_test_tenant('nc_scale', manager, cfy)
    nc = NodeCellarExample(
            cfy, manager, attributes, ssh_key, logger, tmpdir,
            tenant=tenant, suffix='scale')
    nc.blueprint_file = 'openstack-haproxy-blueprint.yaml'
    nc.inputs['number_of_instances'] = 1
    yield nc
    nc.cleanup()


def _scale(cfy, deployment_id, delta, tenant):
    cfy.executions.start.scale([
        '-d', deployment_id,
        '-p', 'scalable_entity_name=nodecellar',
        '-p', 'delta={}'.format(delta),
        '-p', 'scale_compute=true',
        '--tenant-name', tenant])


def _read_haproxy_stats(ip_address):
    csv_data = requests.get(
            'http://{0}:9000/haproxy_stats;csv'.format(ip_address),
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


def _assert_haproxy_load_balancing(outputs, expected_number_of_backends=1):
    ip_address = outputs['endpoint']['ip_address']
    port = outputs['endpoint']['port']

    initial_stats = _read_haproxy_stats(ip_address)
    number_of_backends = len(initial_stats)
    assert expected_number_of_backends == number_of_backends
    for count in initial_stats.values():
        assert 0 == count

    for i in range(1, number_of_backends + 1):
        requests.get('http://{0}:{1}/wines'.format(ip_address, port))
        stats = _read_haproxy_stats(ip_address)
        active_backends = [b for b, count in stats.items() if count == 1]
        assert i == len(active_backends)


def _assert_scale(manager, deployment_id, outputs, expected_instances,
                  tenant):
    with set_client_tenant(manager, tenant):
        instances = manager.client.node_instances.list(
            deployment_id=deployment_id,
            _include=['id'],
        )
    assert len(instances) == 9 + 3 * expected_instances

    _assert_haproxy_load_balancing(
            outputs, expected_number_of_backends=expected_instances)


def test_nodecellar_example(cfy, manager, nodecellar, logger):
    nodecellar.upload_blueprint()
    nodecellar.create_deployment()
    nodecellar.install()
    nodecellar.verify_installation()

    # scale out (+1)
    logger.info('Performing scale out +1..')
    _scale(cfy, nodecellar.deployment_id, delta=1, tenant=nodecellar.tenant)
    _assert_scale(
            manager,
            nodecellar.deployment_id,
            nodecellar.outputs,
            expected_instances=2,
            tenant=nodecellar.tenant)

    # scale in (-1)
    logger.info('Performing scale in -1..')
    _scale(cfy, nodecellar.deployment_id, delta=-1, tenant=nodecellar.tenant)
    _assert_scale(
            manager,
            nodecellar.deployment_id,
            nodecellar.outputs,
            expected_instances=1,
            tenant=nodecellar.tenant)

    # uninstall
    nodecellar.uninstall()
    nodecellar.delete_deployment()
