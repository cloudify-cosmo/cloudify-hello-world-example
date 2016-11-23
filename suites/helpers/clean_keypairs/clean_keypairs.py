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

import argparse

from novaclient.v2 import client


def _parse_args():
    parser = argparse.ArgumentParser(description='clean openstack keypairs')

    parser.add_argument('-u', '--username', dest='username', required=True,
                        help='Openstack username')
    parser.add_argument('-p', '--password', dest='password', required=True,
                        help='Openstack password')
    parser.add_argument('-i', '--project-id', dest='project_id', required=True,
                        help='Openstack project ID')
    parser.add_argument('-a', '--auth-url', dest='auth_url', required=True,
                        help='Openstack authentication url')
    parser.add_argument('-e', '--exclude', dest='exclude', nargs='*',
                        default=[], help='Keypairs that should not be deleted')

    return vars(parser.parse_args())


def clean(username, password, project_id, auth_url, exclude):
    with client.Client(username=username,
                       api_key=password,
                       project_id=project_id,
                       auth_url=auth_url) as nova:
        keypairs = nova.keypairs.list()
        for keypair in keypairs:
            if keypair.name not in exclude:
                nova.keypairs.delete(keypair.name)


def main():
    clean(**_parse_args())


if __name__ == '__main__':
    main()
