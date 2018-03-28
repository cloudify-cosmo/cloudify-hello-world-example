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
    version='4.4.dev1',
    author='Gigaspaces',
    author_email='cosmo-admin@gigaspaces.com',
    packages=['cosmo_tester'],
    license='LICENSE',
    description='Cosmo system tests framework',
    zip_safe=False,
    install_requires=[
        'paramiko==1.18.3',
        'fabric==1.13.1',
        'PyYAML==3.10',
        'requests>=2.7.0,<3.0.0',
        'sh==1.11',
        'path.py==8.1.2',
        'nose',
        'retrying==1.3.3',
        'Jinja2==2.7.2',
        'pywinrm==0.0.3',
        'fasteners==0.13.0',
        # Wagon version has been left out since it better reflects the user
        # use-case
        'wagon[venv]==0.6.3',
        'pytest==3.0.4',
        'testtools==2.2.0',
        'openstacksdk==0.9.13'
    ],
    entry_points={
        'console_scripts': [
            'cfy-systests = cosmo_tester.cli:main'
        ]
    },

)
