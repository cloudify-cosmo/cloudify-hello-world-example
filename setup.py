########
# Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
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

__author__ = 'dank'

from setuptools import setup

CLI_VERSION = '3.0'
CLI_BRANCH = '3.0'
CLI = \
    "https://github.com/cloudify-cosmo/cloudify-cli/tarball/{0}" \
    .format(CLI_BRANCH)

OPENSTACK_PROVIDER_VERSION = '1.0'
OPENSTACK_PROVIDER_BRANCH = '1.0'
OPENSTACK_PROVIDER = \
    "https://github.com/cloudify-cosmo/cloudify-openstack-provider/tarball/{0}" \
    .format(OPENSTACK_PROVIDER_BRANCH)


setup(
    name='cloudify-system-tests',
    version='3.0',
    author='dank',
    author_email='dank@gigaspaces.com',
    packages=['cosmo_tester'],
    license='LICENSE',
    description='Cosmo system tests framework',
    zip_safe=False,
    install_requires=[
        'fabric',
        'python-novaclient',
        'python-keystoneclient',
        'python-neutronclient',
        'PyYAML==3.10',
        'requests==2.2.1',
        'sh==1.09',
        'path.py==5.1',
        'nose',
        'cloudify-cli',
        'cloudify-openstack-provider'
    ],
    dependency_links=["{0}#egg=cloudify-cli-{1}"
                      .format(CLI, CLI_VERSION),
                      "{0}#egg=cloudify-openstack-provider-{1}"
                      .format(OPENSTACK_PROVIDER, OPENSTACK_PROVIDER_VERSION)]

)
