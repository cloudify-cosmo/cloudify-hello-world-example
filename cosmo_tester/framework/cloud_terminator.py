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

__author__ = 'nirb'

import logging

import yaml
import novaclient.v1_1.client as nvclient
import neutronclient.v2_0.client as neclient
from path import path


logger = logging.getLogger('cloud-terminator')
logger.setLevel(logging.INFO)


def teardown(cloud_config_file_path,
             remove_server=True,
             remove_network=False,
             remove_security_groups=False,
             remove_keypairs=False):
    logger.info('Terminating cloud bootstrapped earlier using configuration'
                ' from {0}'.format(cloud_config_file_path))

    cloud_config = yaml.load(path(cloud_config_file_path).text())

    creds = get_client_creds(cloud_config)
    nova = nvclient.Client(**creds)
    neutron = neclient.Client(username=creds['username'],
                              password=creds['api_key'],
                              tenant_name=creds['project_id'],
                              region_name=creds['region_name'],
                              auth_url=creds['auth_url'])

    networking = cloud_config['networking']
    compute = cloud_config['compute']
    management_server = compute['management_server']

    mng_instance_name = management_server['instance']['name']
    network_name = networking['int_network']['name']
    mng_keypair_name = management_server['management_keypair']['name']
    agents_keypair_name = compute['agent_servers']['agents_keypair']['name']
    mng_security_group_name = networking['management_security_group']['name']
    agents_security_group_name = networking['agents_security_group']['name']

    if remove_server:
        for server in nova.servers.list():
            if mng_instance_name == server.human_id:
                server.delete()
                break

    if remove_network:
        for network in neutron.list_networks()['networks']:
            if network_name == network['name']:
                neutron.delete_network(network['id'])
                break

    if remove_keypairs:
        for keypair in nova.keypairs.list():
            if mng_keypair_name == keypair.name:
                nova.keypairs.delete(keypair)
            elif agents_keypair_name == keypair.name:
                nova.keypairs.delete(keypair)

    if remove_security_groups:
        for sg in nova.security_groups.list():
            if mng_security_group_name == sg.name:
                nova.security_groups.delete(sg)
            elif agents_security_group_name == sg.name:
                nova.security_groups.delete(sg)


def get_client_creds(cloud_config):
    return {
        'username': cloud_config['keystone']['username'],
        'api_key': cloud_config['keystone']['password'],
        'auth_url': cloud_config['keystone']['auth_url'],
        'project_id': cloud_config['keystone']['tenant_name'],
        'region_name': cloud_config['compute']['region']
    }
