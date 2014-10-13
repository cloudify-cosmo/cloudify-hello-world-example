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


import random
import os
import copy
import logging
from time import sleep
from contextlib import contextmanager

import boto.ec2

from cosmo_tester.framework.handlers import BaseHandler
from cosmo_tester.framework.util import get_actual_keypath
from cosmo_tester.framework.testenv import CLOUDIFY_TEST_NO_CLEANUP


def boto_client(libcloud_provider_name, access_id=None, secret_key=None):
    # We use the libcloud provider to determine the region to use with boto
    region = _get_region_by_libcloud_provider(libcloud_provider_name)
    if access_id and secret_key:
        return boto.ec2.connect_to_region(region, aws_access_key_id=access_id,
                                          aws_secret_access_key=secret_key)
    elif 'AWS_ACCESS_KEY_ID' in os.environ \
            and 'AWS_SECRET_ACCESS_KEY' in os.environ:
        # try to connect using env var credentials
        return boto.ec2.connect_to_region(region)

    raise RuntimeError('Unable to initialize aws client. aws credentials '
                       'were not found in config file or environment.')


def _get_region_by_libcloud_provider(provider_name):
    region = None
    if provider_name == 'ec2_ap_northeast':
        region = 'ap-northeast-1'
    elif provider_name == 'ec2_ap_southeast':
        region = 'ap-southeast-1'
    elif provider_name == 'ec2_ap_southeast_2':
        region = 'ap-southeast-2'
    elif provider_name == 'ec2_eu_west':
        region = 'eu-west-1'
    elif provider_name == 'ec2_sa_east':
        region = 'sa-east-1'
    elif provider_name == 'ec2_us_east':
        region = 'us-east-1'
    elif provider_name == 'ec2_us_west':
        region = 'us-west-1'
    elif provider_name == 'ec2_us_west_oregon':
        region = 'us-west-2'

    if region is None:
        raise RuntimeError('Unable to map libcloud provider name \'{0}\' with '
                           'the appropriate region'.format(provider_name))
    return region


def ec2_infra_state(cloudify_config):
    config_reader = CloudifyEc2ConfigReader(cloudify_config)
    ec2_conn = boto_client(config_reader.libcloud_provider_name,
                           access_id=config_reader.aws_access_id,
                           secret_key=config_reader.aws_secret_key)
    # TODO: The resource name prefix is currently not implemented on the ec2
    # provider.Using wild-card until we get it fixed. (CFY-1261)
    sg_prefix_regex = config_reader.resources_prefix + '*'
    prefix_regex = '*'
    return {
        # Too many sg groups could cause the test to fail.
        'security_groups': dict(_security_groups(ec2_conn, sg_prefix_regex)),
        'servers': dict(_servers(ec2_conn, prefix_regex)),
        'key_pairs': dict(_key_pairs(ec2_conn, prefix_regex)),
        'elastic_ips': dict(_elastic_ips(ec2_conn))
    }


def _security_groups(ec2_conn, prefix_regex):
    return [(n.id, n.name)
            for n in ec2_conn.get_all_security_groups(
                filters={'group-name': prefix_regex})]


def _servers(ec2_conn, prefix_regex):
    return [(s.instances[0].id, s.instances[0].tags['Name'])
            for s in
            ec2_conn.get_all_instances(filters={'tag:Name': prefix_regex})]


def _key_pairs(ec2_conn, prefix_regex):
    return [(kp.fingerprint, kp.name)
            for kp in
            ec2_conn.get_all_key_pairs(filters={'key-name': prefix_regex})]


def _elastic_ips(ec2_conn):
    return [(ip.allocation_id, ip.public_ip)
            for ip in ec2_conn.get_all_addresses()]


def ec2_infra_state_delta(before, after):
    after = copy.deepcopy(after)
    return {
        prop: _remove_keys(after[prop], before[prop].keys())
        for prop in before.keys()
    }


def _remove_keys(dct, keys):
    for key in keys:
        if key in dct:
            del dct[key]
    return dct


def remove_ec2_resources(cloudify_config, resources_to_remove):
    for _ in range(3):
        resources_to_remove = _remove_ec2_resources_impl(
            cloudify_config, resources_to_remove)
        if all([len(g) == 0 for g in resources_to_remove.values()]):
            break
        sleep(3)
    return resources_to_remove


def _remove_ec2_resources_impl(cloudify_config,
                               resources_to_remove):
    conn = boto_client(cloudify_config['connection']['cloud_provider_name'],
                       access_id=cloudify_config['connection']['access_id'],
                       secret_key=cloudify_config['connection']['secret_key'])
    failed = {
        'servers': {},
        'key_pairs': {},
        'elastic_ips': {},
        'security_groups': {}
    }

    for server_id, server_name in resources_to_remove['servers'].items():
        with _handled_exception(server_id, failed, 'servers'):
            conn.terminate_instances(instance_ids=list(id))
    for key_fingerprint, key_name in resources_to_remove['key_pairs'].items():
        with _handled_exception(key_fingerprint, failed, 'key_pairs'):
            conn.delete_key_pair(key_name=key_name)
    for alloc_id, public_ip in resources_to_remove['elastic_ips'].items():
        with _handled_exception(alloc_id, failed, 'elastic_ips'):
            conn.release_address(public_ip=public_ip)
    for sg_id, sg_name in resources_to_remove['security_groups'].items():
        if sg_name == 'default':
            continue
        with _handled_exception(sg_id, failed, 'security_groups'):
            conn.delete_security_group(name=sg_name)

    return failed


@contextmanager
def _handled_exception(resource_id, failed, resource_group):
    try:
        yield
    except BaseException, ex:
        failed[resource_group][resource_id] = ex


class Ec2CleanupContext(BaseHandler.CleanupContext):
    def __init__(self, context_name, cloudify_config):
        super(Ec2CleanupContext, self).__init__(context_name,
                                                cloudify_config)
        self.before_run = ec2_infra_state(cloudify_config)
        self.logger = logging.getLogger('Ec2CleanupContext')

    def cleanup(self):
        super(Ec2CleanupContext, self).cleanup()
        resources_to_teardown = self.get_resources_to_teardown()
        if os.environ.get(CLOUDIFY_TEST_NO_CLEANUP):
            self.logger.warn('[{0}] SKIPPING cleanup: of the resources: {1}'
                             .format(self.context_name, resources_to_teardown))
            return
        self.logger.info('[{0}] Performing cleanup: will try removing these '
                         'resources: {1}'
                         .format(self.context_name, resources_to_teardown))

        leftovers = remove_ec2_resources(self.cloudify_config,
                                         resources_to_teardown)
        self.logger.info('[{0}] Leftover resources after cleanup: {1}'
                         .format(self.context_name, leftovers))

    def get_resources_to_teardown(self):
        current_state = ec2_infra_state(self.cloudify_config)
        return ec2_infra_state_delta(before=self.before_run,
                                     after=current_state)


class CloudifyEc2ConfigReader(BaseHandler.CloudifyConfigReader):
    def __init__(self, cloudify_config):
        super(CloudifyEc2ConfigReader, self).__init__(cloudify_config)

    @property
    def management_server_name(self):
        return self.config['compute']['management_server']['instance']['name']

    @property
    def management_server_floating_ip(self):
        return self.config['compute']['management_server']['floating_ip']

    @property
    def agent_key_path(self):
        return self.config['compute']['agent_servers']['agents_keypair'][
            'private_key_path']

    @property
    def management_user_name(self):
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
    def agents_security_group(self):
        return self.config['networking']['agents_security_group']['name']

    @property
    def management_security_group(self):
        return self.config['networking']['management_security_group']['name']

    @property
    def libcloud_provider_name(self):
        return self.config['connection']['cloud_provider_name']

    @property
    def aws_access_id(self):
        return self.config['connection']['access_id']

    @property
    def aws_secret_key(self):
        return self.config['connection']['secret_key']


class LibcloudHandler(BaseHandler):
    provider = 'libcloud'
    CleanupContext = Ec2CleanupContext
    CloudifyConfigReader = CloudifyEc2ConfigReader

    medium_instance_type = 'm1.medium'
    ubuntu_agent_ami = 'ami-a73264ce'

    def __init__(self, env):
        super(LibcloudHandler, self).__init__(env)
        self._ubuntu_ami = None

    @property
    def ubuntu_ami(self):
        if self._ubuntu_ami is not None:
            return self._ubuntu_ami

        conn = boto_client(self.env._config_reader.libcloud_provider_name,
                           access_id=self.env._config_reader.aws_access_id,
                           secret_key=self.env._config_reader.aws_secret_key)
        ubuntu_images = conn.get_all_images(filters={
            'name': 'ubuntu/images/ebs/'
                    'ubuntu-precise-12.04-amd64-server-20131003'
        })
        if ubuntu_images.__len__() == 0:
            raise RuntimeError('could not find ubuntu ami')

        self._ubuntu_ami = ubuntu_images[0].id
        return self._ubuntu_ami

    def before_bootstrap(self):
        with self.update_cloudify_config() as patch:
            suffix = '-%06x' % random.randrange(16 ** 6)
            patch.append_value('compute.management_server.instance.name',
                               suffix)

    def after_bootstrap(self, provider_context):
        resources = provider_context['resources']
        agent_keypair = resources['agents_keypair']
        management_keypair = resources['management_keypair']
        self.remove_agent_keypair = agent_keypair['created'] is True
        self.remove_management_keypair = management_keypair['created'] is True

    def after_teardown(self):
        if self.remove_agent_keypair:
            agent_key_path = get_actual_keypath(self.env,
                                                self.env.agent_key_path,
                                                raise_on_missing=False)
            if agent_key_path:
                os.remove(agent_key_path)
        if self.remove_management_keypair:
            management_key_path = get_actual_keypath(
                self.env,
                self.env.management_key_path,
                raise_on_missing=False)
            if management_key_path:
                os.remove(management_key_path)


handler = LibcloudHandler
