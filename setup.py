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
    name='cosmo-tester',
    version='0.3',
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

        # When this was writen the published version was 5.3 but it had
        # problems with its 'progressbar>=2.3' dependency which was not out yet.
        # you can probably remove the explicit version or write a newer explicit version
        # sometime in the future when this versioning issue is resolved
        'attest==0.5.1'
    ],
)
