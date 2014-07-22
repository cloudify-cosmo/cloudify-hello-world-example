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


import random
import logging
import os
import time
import copy
from contextlib import contextmanager

import novaclient.v1_1.client as nvclient
import neutronclient.v2_0.client as neclient
from retrying import retry

from cosmo_tester.framework.handlers import BaseHandler


logging.getLogger('neutronclient.client').setLevel(logging.INFO)
logging.getLogger('novaclient.client').setLevel(logging.INFO)

CLOUDIFY_TEST_NO_CLEANUP = 'CLOUDIFY_TEST_NO_CLEANUP'

ubuntu_image_name = 'Ubuntu Server 12.04 LTS (amd64 20140606) - Partner Image'
centos_image_name = 'centos-python2.7'
centos_image_user = 'root'
flavor_name = 'standard.small'
ubuntu_image_id = '75d47d10-fef8-473b-9dd1-fe2f7649cb41'
small_flavor_id = 101


def openstack_clients(cloudify_config):
    creds = _client_creds(cloudify_config)
    return nvclient.Client(**creds), \
           neclient.Client(username=creds['username'],
                           password=creds['api_key'],
                           tenant_name=creds['project_id'],
                           region_name=creds['region_name'],
                           auth_url=creds['auth_url'])


@retry(stop_max_attempt_number=5, wait_fixed=20000)
def openstack_infra_state(cloudify_config):
    """
    @retry decorator is used because this error sometimes occur:
    ConnectionFailed: Connection to neutron failed: Maximum attempts reached
    """
    nova, neutron = openstack_clients(cloudify_config)
    config_reader = CloudifyOpenstackConfigReader(cloudify_config)
    prefix = config_reader.resource_prefix
    return {
        'networks': dict(_networks(neutron, prefix)),
        'subnets': dict(_subnets(neutron, prefix)),
        'routers': dict(_routers(neutron, prefix)),
        'security_groups': dict(_security_groups(neutron, prefix)),
        'servers': dict(_servers(nova, prefix)),
        'key_pairs': dict(_key_pairs(nova, prefix)),
        'floatingips': dict(_floatingips(neutron, prefix)),
        'ports': dict(_ports(neutron, prefix))
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
    config_reader = CloudifyOpenstackConfigReader(cloudify_config)

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


def _networks(neutron, prefix):
    return [(n['id'], n['name'])
            for n in neutron.list_networks()['networks']
            if _check_prefix(n['name'], prefix)]


def _subnets(neutron, prefix):
    return [(n['id'], n['name'])
            for n in neutron.list_subnets()['subnets']
            if _check_prefix(n['name'], prefix)]


def _routers(neutron, prefix):
    return [(n['id'], n['name'])
            for n in neutron.list_routers()['routers']
            if _check_prefix(n['name'], prefix)]


def _security_groups(neutron, prefix):
    return [(n['id'], n['name'])
            for n in neutron.list_security_groups()['security_groups']
            if _check_prefix(n['name'], prefix)]


def _servers(nova, prefix):
    return [(s.id, s.human_id)
            for s in nova.servers.list()
            if _check_prefix(s.human_id, prefix)]


def _key_pairs(nova, prefix):
    return [(kp.id, kp.name)
            for kp in nova.keypairs.list()
            if _check_prefix(kp.name, prefix)]


def _floatingips(neutron, prefix):
    # return [(ip['id'], ip['floating_ip_address'])
    #         for ip in neutron.list_floatingips()['floatingips']]
    return []


def _ports(neutron, prefix):
    return [(p['id'], p['name'])
            for p in neutron.list_ports()['ports']
            if _check_prefix(p['name'], prefix)]


def _check_prefix(name, prefix):
    return name.startswith(prefix)


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


class OpenstackCleanupContext(BaseHandler.CleanupContext):

    def __init__(self, context_name, cloudify_config):
        super(OpenstackCleanupContext, self).__init__(context_name,
                                                      cloudify_config)
        self.before_run = openstack_infra_state(cloudify_config)

    def cleanup(self):
        super(OpenstackCleanupContext, self).cleanup()
        resources_to_teardown = self.get_resources_to_teardown()
        if os.environ.get(CLOUDIFY_TEST_NO_CLEANUP):
            self.logger.warn('[{0}] SKIPPING cleanup: of the resources: {1}'
                             .format(self.context_name, resources_to_teardown))
            return
        self.logger.info('[{0}] Performing cleanup: will try removing these '
                         'resources: {1}'
                         .format(self.context_name, resources_to_teardown))

        leftovers = remove_openstack_resources(self.cloudify_config,
                                               resources_to_teardown)
        self.logger.info('[{0}] Leftover resources after cleanup: {1}'
                         .format(self.context_name, leftovers))

    def get_resources_to_teardown(self):
        current_state = openstack_infra_state(self.cloudify_config)
        return openstack_infra_state_delta(before=self.before_run,
                                           after=current_state)


class CloudifyOpenstackConfigReader(BaseHandler.CloudifyConfigReader):

    def __init__(self, cloudify_config):
        super(CloudifyOpenstackConfigReader, self).__init__(cloudify_config)

    @property
    def management_server_name(self):
        return self.config['compute']['management_server']['instance']['name']

    @property
    def management_server_floating_ip(self):
        return self.config['compute']['management_server']['floating_ip']

    @property
    def management_network_name(self):
        return self.config['networking']['int_network']['name']

    @property
    def management_sub_network_name(self):
        return self.config['networking']['subnet']['name']

    @property
    def management_router_name(self):
        return self.config['networking']['router']['name']

    @property
    def agent_key_path(self):
        return self.config['compute']['agent_servers']['agents_keypair'][
            'private_key_path']

    @property
    def managment_user_name(self):
        return self.config['compute']['management_server'][
            'user_on_management']

    @property
    def management_key_path(self):
        return self.config['compute']['management_server'][
            'management_keypair']['private_key_path']

    @property
    def agent_keypair_name(self):
        return self.config['compute']['agent_servers']['agents_keypair'][
            'name']

    @property
    def management_keypair_name(self):
        return self.config['compute']['management_server'][
            'management_keypair']['name']

    @property
    def external_network_name(self):
        return self.config['networking']['ext_network']['name']

    @property
    def agents_security_group(self):
        return self.config['networking']['agents_security_group']['name']

    @property
    def management_security_group(self):
        return self.config['networking']['management_security_group']['name']


class OpenstackHandler(BaseHandler):

    provider = 'openstack'
    CleanupContext = OpenstackCleanupContext
    CloudifyConfigReader = CloudifyOpenstackConfigReader

    @staticmethod
    def make_unique_configuration(patch):
        suffix = '-%06x' % random.randrange(16 ** 6)
        patch.append_value('compute.management_server.instance.name',
                           suffix)

handler = OpenstackHandler
