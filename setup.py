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

from setuptools import setup

setup(
    name='cloudify-system-tests',
    version='3.2rc1',
    author='Gigaspaces',
    author_email='cosmo-admin@gigaspaces.com',
    packages=['cosmo_tester'],
    license='LICENSE',
    description='Cosmo system tests framework',
    zip_safe=False,
    install_requires=[
        'fabric',
        'PyYAML==3.10',
        'requests<=2.5.1',
        'sh==1.09',
        'path.py==5.1',
        'nose',
        'retrying==1.2.2',
        'cloudify==3.2rc1',
        'elasticsearch',
        'Jinja2==2.7.2',
        'influxdb==0.1.13',
        'pywinrm==0.0.3'
    ]
)
