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

setup(
    name='cloudify-system-tests',
    version='3.1',
    author='dank',
    author_email='dank@gigaspaces.com',
    packages=['cosmo_tester'],
    license='LICENSE',
    description='Cosmo system tests framework',
    zip_safe=False,
    install_requires=[
        'fabric',
        'python-novaclient==2.17.0',
        'python-keystoneclient==0.7.1',
        'python-neutronclient==2.3.9',
        'PyYAML==3.10',
        'requests==2.2.1',
        'sh==1.09',
        'path.py==5.1',
        'nose',
        'retrying==1.2.2',
        'cloudify==3.1',
        'cloudify-openstack-provider==1.1',
        'cloudify-libcloud-provider==1.1',
        'boto==2.32.1'
    ]
)
