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

import time
from contextlib import contextmanager
import copy

import novaclient.v1_1.client as nvclient
import neutronclient.v2_0.client as neclient


from cosmo_tester.framework.util import CloudifyConfigReader


def openstack_clients(cloudify_config):
    creds = _client_creds(cloudify_config)
    return nvclient.Client(**creds), \
        neclient.Client(username=creds['username'],
                        password=creds['api_key'],
                        tenant_name=creds['project_id'],
                        region_name=creds['region_name'],
                        auth_url=creds['auth_url'])


def openstack_infra_state(cloudify_config):
    nova, neutron = openstack_clients(cloudify_config)
    return {
        'networks': dict(_networks(neutron)),
        'subnets': dict(_subnets(neutron)),
        'routers': dict(_routers(neutron)),
        'security_groups': dict(_security_groups(neutron)),
        'servers': dict(_servers(nova)),
        'key_pairs': dict(_key_pairs(nova)),
        'floatingips': dict(_floatingips(neutron)),
        'ports': dict(_ports(neutron))
    }


def remove_openstack_resources(cloudify_config, resources_to_remove):
    # basically sort of a workaround, but if we get the order wrong
    # the first time, there is a chance things would better next time
    # 3'rd time can't really hurt, can it?
    # 3 is a charm
    for _ in range(3):
        resources_to_remove = _remove_openstack_resources_impl(
            cloudify_config, resources_to_remove)
        if all([len(g) == 0 for g in resources_to_remove.values()]):
            break
        # give openstack some time to update its data structures
        time.sleep(3)
    return resources_to_remove


def _remove_openstack_resources_impl(cloudify_config,
                                     resources_to_remove):
    nova, neutron = openstack_clients(cloudify_config)
    config_reader = CloudifyConfigReader(cloudify_config)

    servers = nova.servers.list()
    ports = neutron.list_ports()['ports']
    routers = neutron.list_routers()['routers']
    subnets = neutron.list_subnets()['subnets']
    networks = neutron.list_networks()['networks']
    keypairs = nova.keypairs.list()
    floatingips = neutron.list_floatingips()['floatingips']
    security_groups = neutron.list_security_groups()['security_groups']

    failed = {
        'servers': {},
        'routers': {},
        'ports': {},
        'subnets': {},
        'networks': {},
        'key_pairs': {},
        'floatingips': {},
        'security_groups': {}
    }

    for server in servers:
        if server.id in resources_to_remove['servers']:
            with _handled_exception(server.id, failed, 'servers'):
                nova.servers.delete(server)
    for router in routers:
        if router['id'] in resources_to_remove['routers']:
            with _handled_exception(router['id'], failed, 'routers'):
                for p in neutron.list_ports(device_id=router['id'])['ports']:
                    neutron.remove_interface_router(router['id'], {
                        'port_id': p['id']
                    })
                neutron.delete_router(router['id'])
    for port in ports:
        if port['id'] in resources_to_remove['ports']:
            with _handled_exception(port['id'], failed, 'ports'):
                neutron.delete_port(port['id'])
    for subnet in subnets:
        if subnet['id'] in resources_to_remove['subnets']:
            with _handled_exception(subnet['id'], failed, 'subnets'):
                neutron.delete_subnet(subnet['id'])
    for network in networks:
        if network['name'] == config_reader.external_network_name:
            continue
        if network['id'] in resources_to_remove['networks']:
            with _handled_exception(network['id'], failed, 'networks'):
                neutron.delete_network(network['id'])
    for key_pair in keypairs:
        if key_pair.id in resources_to_remove['key_pairs']:
            with _handled_exception(key_pair.id, failed, 'key_pairs'):
                nova.keypairs.delete(key_pair)
    for floatingip in floatingips:
        if floatingip['id'] in resources_to_remove['floatingips']:
            with _handled_exception(floatingip['id'], failed, 'floatingips'):
                neutron.delete_floatingip(floatingip['id'])
    for security_group in security_groups:
        if security_group['name'] == 'default':
            continue
        if security_group['id'] in resources_to_remove['security_groups']:
            with _handled_exception(security_group['id'],
                                    failed, 'security_groups'):
                neutron.delete_security_group(security_group['id'])

    return failed


def openstack_infra_state_delta(before, after):
    after = copy.deepcopy(after)
    return {
        prop: _remove_keys(after[prop], before[prop].keys())
        for prop in before.keys()
    }


def _client_creds(cloudify_config):
    return {
        'username': cloudify_config['keystone']['username'],
        'api_key': cloudify_config['keystone']['password'],
        'auth_url': cloudify_config['keystone']['auth_url'],
        'project_id': cloudify_config['keystone']['tenant_name'],
        'region_name': cloudify_config['compute']['region']
    }


def _networks(neutron):
    return [(n['id'], n['name'])
            for n in neutron.list_networks()['networks']]


def _subnets(neutron):
    return [(n['id'], n['name'])
            for n in neutron.list_subnets()['subnets']]


def _routers(neutron):
    return [(n['id'], n['name'])
            for n in neutron.list_routers()['routers']]


def _security_groups(neutron):
    return [(n['id'], n['name'])
            for n in neutron.list_security_groups()['security_groups']]


def _servers(nova):
    return [(s.id, s.human_id)
            for s in nova.servers.list()]


def _key_pairs(nova):
    return [(kp.id, kp.name)
            for kp in nova.keypairs.list()]


def _floatingips(neutron):
    return [(ip['id'], ip['floating_ip_address'])
            for ip in neutron.list_floatingips()['floatingips']]


def _ports(neutron):
    return [(p['id'], p['name'])
            for p in neutron.list_ports()['ports']]


def _remove_keys(dct, keys):
    for key in keys:
        if key in dct:
            del dct[key]
    return dct


@contextmanager
def _handled_exception(resource_id, failed, resource_group):
    try:
        yield
    except BaseException, ex:
        failed[resource_group][resource_id] = ex
