########
# Copyright (c) 2015 GigaSpaces Technologies Ltd. All rights reserved
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
from ec2 import constants
from boto.ec2 import get_region

from cosmo_tester.test_suites.test_security import security_test_base
from cosmo_tester.test_suites.test_security import auth_test_base

from cloudify.workflows import local
from cloudify_cli import constants as cli_constants

auth_test_base.ADMIN_USERNAME = 'alice@welcome.com'
auth_test_base.ADMIN_PASSWORD = '@lice_Aa123456!'
auth_test_base.DEPLOYER_USERNAME = 'bob@welcome.com'
auth_test_base.DEPLOYER_PASSWORD = 'b0b_Aa123456!'
auth_test_base.VIEWER_USERNAME = 'clair@welcome.com'
auth_test_base.VIEWER_PASSWORD = 'cl@ir_Aa123456!'
auth_test_base.NO_ROLE_USERNAME = 'dave@welcome.com'
auth_test_base.NO_ROLE_PASSWORD = 'd@ve_Aa123456!'

security_test_base.TEST_CFY_USERNAME = auth_test_base.ADMIN_USERNAME
security_test_base.TEST_CFY_PASSWORD = auth_test_base.ADMIN_PASSWORD


class ADAuthenticationAuthorizationTest(auth_test_base.BaseAuthTest):

    def setUp(self):
        super(ADAuthenticationAuthorizationTest, self).setUp()
        self.ad_ip = self.provision_active_directory_instance()
        self.setup_secured_manager()

    def test_ad_authentication_and_authorization(self):
        self._test_authentication_and_authorization(assert_token=False)

    def provision_active_directory_instance(self):

        blueprint_dir_path = self.copy_blueprint('active-directory')
        blueprint_path = (blueprint_dir_path /
                          'active-directory-blueprint.yaml')
        inputs = self._get_active_directory_inputs()

        # init local workflow execution environment
        self.localenv = local.init_env(blueprint_path,
                                       name='active directory instance',
                                       inputs=inputs,
                                       ignored_modules=cli_constants.
                                       IGNORED_LOCAL_WORKFLOW_MODULES)

        self.addCleanup(self._terminate_active_directory_instance)
        # execute the install workflow
        self.localenv.execute('install',
                              task_retries=9,
                              task_retry_interval=9)

        return self.localenv.outputs().get('ldap_endpoint')

    def _terminate_active_directory_instance(self):
        self.localenv.execute('uninstall',
                              task_retries=9,
                              task_retry_interval=9)

    def _get_active_directory_inputs(self):
        return {
            'instance_type': self.env.medium_instance_type,
            'image_id': self.env.windows_server_2012_r2_image_id,
            constants.AWS_CONFIG_PROPERTY:
                self._get_aws_config()
        }

    def _get_aws_config(self):

        region = get_region(self.env.ec2_region_name)
        return {
            'aws_access_key_id': self.env.aws_access_key_id,
            'aws_secret_access_key': self.env.aws_secret_access_key,
            'region': region
        }

    ######################################
    # override default security settings
    ######################################

    # Use the LDAP authentication plugin to authenticate against the running
    # active directory instance.
    def get_authentication_providers(self):
        return [
            {
                'implementation': 'authentication.ldap_authentication_'
                                  'provider:LDAPAuthenticationProvider',
                'name': 'ldap_authentication_provider',
                'properties': {
                    'directory_url': '{0}'.format(self.ad_ip)
                }
            }
        ]

    # The LDAP authentication plugin is installed via wagon since it's
    # dependencies require gcc and python-dev.
    def get_rest_plugins(self):
        return {
            'ldap_authentication_provider':
                {
                    'source': 'http://adaml-bucket.s3.amazonaws.com/'
                              'cloudify_ldap_plugin-1.0-py27-none-linux_'
                              'x86_64-centos-Core.wgn',
                    'install_args': 'cloudify-ldap-plugin --use-wheel'
                                    ' --no-index --find-links=wheels/ --pre'
                }
            }

    # Use file based userstore
    def get_userstore_driver(self):
        return {
            'implementation': 'flask_securest.userstores.file_userstore:'
                              'FileUserstore',
            'properties': {
                'userstore_file_path': '/opt/manager/userstore.yaml'
            }
        }

    # The ldap authentication plugin requires openldap-devel.
    def get_userdata(self):
        return '#!/bin/bash sudo yum install openldap-devel -y'

    # this test does not require the passwords be stored in the userstore
    def get_userstore_users(self):
        return [
            {
                'username': auth_test_base.ADMIN_USERNAME,
                'groups': [
                    'cfy_admins'
                ]
            },
            {
                'username': auth_test_base.DEPLOYER_USERNAME,
                'groups': [
                    'cfy_deployers'
                ]
            },
            {
                'username': auth_test_base.VIEWER_USERNAME,
                'groups': [
                    'cfy_viewer'
                ]
            },
            {
                'username': auth_test_base.NO_ROLE_USERNAME,
                'groups': ['users']
            }
        ]

    def get_file_userstore_enabled(self):
        return True
