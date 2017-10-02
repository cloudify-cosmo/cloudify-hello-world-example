#########
# Copyright (c) 2017 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#  * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  * See the License for the specific language governing permissions and
#  * limitations under the License.

import argparse
import logging
import os
import sys

from path import Path
import sh

from cosmo_tester.framework.test_hosts import TestHosts
from cosmo_tester.framework.util import sh_bake, get_attributes
from . import conftest


logger = logging.getLogger()
logger.setLevel(logging.INFO)
ch = logging.StreamHandler(sys.stdout)
ch.setLevel(logging.INFO)
formatter = logging.Formatter(fmt='%(asctime)s [%(levelname)s] '
                                  '[%(name)s] %(message)s',
                              datefmt='%H:%M:%S')
ch.setFormatter(formatter)
logger.addHandler(ch)


tmpdir = Path(os.getcwd()) / '.cfy-systests'


def create_cluster_object(ssh_key):
    logger.info('Cloudify manager context will be stored in: %s', tmpdir)
    cfy = sh_bake(sh.cfy)
    attributes = get_attributes(logger)
    hosts = TestHosts(
            cfy,
            ssh_key,
            tmpdir,
            attributes,
            logger)
    return hosts


def create_ssh_key_object():
    ssh_key = conftest.SSHKey(tmpdir, logger)
    return ssh_key


def bootstrap():
    if tmpdir.exists():
        raise IOError('Context folder exist [{}] - either remove it, or '
                      'destroy the manager first'.format(tmpdir))

    tmpdir.makedirs()
    ssh_key = create_ssh_key_object()
    ssh_key.create()
    hosts = create_cluster_object(ssh_key)
    try:
        hosts.create()
    except Exception as e:
        logger.error('Error on manager creation: %s', e)
        tmpdir.rmtree()
        sys.exit(1)

    logger.info('Cloudify manager is up!')
    logger.info(' - IP address: %s', hosts.instances[0].ip_address)


def destroy():
    if not tmpdir.exists():
        raise IOError('Context folder does not exist [{}] - are you sure '
                      'you have a manager running? :-)'.format(tmpdir))

    hosts = create_cluster_object(create_ssh_key_object())
    hosts.destroy()

    logger.info('Cloudify manager destroyed!')
    tmpdir.rmtree_p()


def create_parser():
    parser = argparse.ArgumentParser(
            description='== Cloudify system tests utility! ==')
    sub_parsers = parser.add_subparsers()
    bootstrap_parser = sub_parsers.add_parser(
            'bootstrap',
            help='Bootstrap an image based cloudify manager.')
    bootstrap_parser.set_defaults(which='bootstrap')
    destroy_parser = sub_parsers.add_parser(
            'destroy',
            help='Destroy cloudify manager.')
    destroy_parser.set_defaults(which='destroy')
    return parser


def main():
    args = create_parser().parse_args()
    method = getattr(sys.modules[__name__], args.which)
    method()
