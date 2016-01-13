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
import tempfile

from ec2 import constants
from boto.ec2 import get_region

from cosmo_tester.test_suites.test_security import auth_test_base
from cosmo_tester.framework import util
from cloudify.workflows import local
from cloudify_cli import constants as cli_constants


# used by auth using upn
DOMAIN_NAME = 'welcome.com'

# used by auth using subtree search
BASE_DN = 'CN=Users,DC=welcome,DC=com'
ACTIVE_DIRECTORY_USERNAME_ATTR = 'sAMAccountName'

REMOTE_SECURITY_CONF_PATH = '/opt/manager/rest-security.conf'
REMOTE_USERSTORE_PATH = '/opt/manager/userstore.yaml'


class ADAuthenticationAuthorizationTest(auth_test_base.BaseAuthTest):

    admin_username = 'alice'
    admin_password = '@lice_Aa123456!'
    deployer_username = 'bob'
    deployer_password = 'b0b_Aa123456!'
    viewer_username = 'clair'
    viewer_password = 'cl@ir_Aa123456!'
    no_role_username = 'dave'
    no_role_password = 'd@ve_Aa123456!'

    TEST_CFY_USERNAME = admin_username
    TEST_CFY_PASSWORD = admin_password

    def setUp(self):
        super(ADAuthenticationAuthorizationTest, self).setUp()
        self.ad_ip = self.provision_active_directory_instance()
        self.setup_secured_manager()

    def test_active_directory_authentication_methods(self):
        # Test subtree authentication.
        self.inject_subtree_auth_config()
        self._test_authentication_and_authorization()

        # Test authentication using domain name.
        self.inject_domain_name_auth_config()
        self._test_authentication_and_authorization()

        # Test authentication using the non-standard authentication option
        # enabled in active directory by default. Authenticate according to the
        # full userPrincipalName attribute.
        self._modify_test_users_to_upn()
        self.inject_upn_userstore_users()
        self.inject_upn_auth_config()
        self._test_authentication_and_authorization()

    def inject_upn_userstore_users(self):
        upn_userstore_users = self.get_userstore_users()
        userstore_config = {
            'users': upn_userstore_users
        }
        userstore_file = tempfile.NamedTemporaryFile(delete=False)
        with self.manager_env_fabric() as api:
            with open(userstore_file.name) as f:
                api.get(REMOTE_USERSTORE_PATH, f.name)

            with util.YamlPatcher(userstore_file.name) as patch:
                for key, value in userstore_config.iteritems():
                    patch.set_value(key, value)

            api.put(use_sudo=True,
                    local_path=userstore_file.name,
                    remote_path=REMOTE_USERSTORE_PATH)

    def _modify_test_users_to_upn(self):
        # append domain name to usernames.
        self.admin_username = 'alice@{0}'.format(DOMAIN_NAME)
        self.deployer_username = 'bob@{0}'.format(DOMAIN_NAME)
        self.viewer_username = 'clair@{0}'.format(DOMAIN_NAME)
        self.no_role_username = 'dave@{0}'.format(DOMAIN_NAME)

        # recreate the test client with the new admin username
        self.client = self._create_client(self.admin_username,
                                          self.admin_password)

    def inject_upn_auth_config(self):
        authentication_provider = self.get_authentication_providers()[0]
        authentication_provider['properties'] = {
            'ldap_url': self.ad_ip
        }
        self.inject_authentication_configuration(authentication_provider)

    def inject_domain_name_auth_config(self):
        authentication_provider = self.get_authentication_providers()[0]
        authentication_provider['properties'] = {
            'ldap_url': self.ad_ip,
            'domain_name': DOMAIN_NAME
        }
        self.inject_authentication_configuration(authentication_provider)

    def inject_subtree_auth_config(self):

        authentication_provider = self.get_authentication_providers()[0]
        authentication_provider['properties'] = {
            'ldap_url': self.ad_ip,
            'search_properties': {
                'base_dn': BASE_DN,
                'admin_user_id': self.TEST_CFY_USERNAME,
                'admin_password': self.TEST_CFY_PASSWORD,
                'user_id_attribute': ACTIVE_DIRECTORY_USERNAME_ATTR
            }
        }
        self.inject_authentication_configuration(authentication_provider)

    # Inject a new authentication provider configuration to the manager and
    # restart the rest service.
    def inject_authentication_configuration(self, authentication_provider):
        security_config = {
            'authentication_providers': [authentication_provider]
        }

        rest_security_file = tempfile.NamedTemporaryFile(delete=False)
        with self.manager_env_fabric() as api:
            with open(rest_security_file.name) as f:
                api.get(REMOTE_SECURITY_CONF_PATH, f.name)

            with util.YamlPatcher(rest_security_file.name) as patch:
                for key, value in security_config.iteritems():
                    patch.set_value(key, value)

            api.put(use_sudo=True,
                    local_path=rest_security_file.name,
                    remote_path=REMOTE_SECURITY_CONF_PATH)

            # Restart the rest service
            api.run('sudo systemctl restart cloudify-restservice.service')
        self.wait_for_resource(self.client.manager.get_status, timeout_sec=60)

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
                              task_retries=19,
                              task_retry_interval=20)

        return self.localenv.outputs().get('ldap_endpoint')

    def _terminate_active_directory_instance(self):
        self.localenv.execute('uninstall',
                              task_retries=9,
                              task_retry_interval=10)

    def _get_active_directory_inputs(self):
        return {
            'instance_type': self.env.medium_instance_type,
            'image_id': self.env.windows_server_2012_r2_image_id,
            constants.AWS_CONFIG_PROPERTY: self._get_aws_config()
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
                'implementation': 'authentication.active_directory_'
                                  'authentication_provider'
                                  ':ActiveDirectoryAuthenticationProvider',
                'name': 'ldap_authentication_provider',
                'properties': {
                    'domain_name': DOMAIN_NAME,
                    'ldap_url': '{0}'.format(self.ad_ip)
                }
            }
        ]

    # The LDAP authentication plugin is installed via wagon since it's
    # dependencies require gcc and python-dev.
    def get_rest_plugins(self):
        return {
            'ldap_authentication_provider':
                {
                    'source': 'http://gigaspaces-repository-eu.s3.amazonaws'
                              '.com/org/cloudify3/3.3.1/sp-RELEASE/cloudify'
                              '_ldap_plugin-1.0-py27-none-linux_x86_64-centos'
                              '-Core.wgn',
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
                'username': self.admin_username,
                'groups': [
                    'cfy_admins'
                ]
            },
            {
                'username': self.deployer_username,
                'groups': [
                    'cfy_deployers'
                ]
            },
            {
                'username': self.viewer_username,
                'groups': [
                    'cfy_viewer'
                ]
            },
            {
                'username': self.no_role_username,
                'groups': ['users']
            }
        ]

    def get_file_userstore_enabled(self):
        return True
