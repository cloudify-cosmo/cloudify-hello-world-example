########
# Copyright (c) 2018 Cloudify Platform Ltd. All rights reserved
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

import os
import json
import yaml

from cloudify_cli.constants import DEFAULT_TENANT_NAME

from cosmo_tester.framework import util
from cosmo_tester.framework.examples import AbstractExample

from . import constants


class AbstractTier1Cluster(AbstractExample):
    REPOSITORY_URL = 'https://github.com/Cloudify-PS/manager-of-managers.git'  # NOQA
    TRANSFER_AGENTS = None

    def __init__(self, *args, **kwargs):
        super(AbstractTier1Cluster, self).__init__(*args, **kwargs)
        self._deployed = False

    @property
    def inputs(self):
        # To see explanations of the following inputs, see
        # https://github.com/Cloudify-PS/manager-of-managers#blueprint-inputs
        openstack_config = util.get_openstack_config()

        device_mapping_config = {
            'boot_index': '0',
            'uuid': self.attributes.default_linux_image_id,
            'volume_size': 30,
            'source_type': 'image',
            'destination_type': 'volume',
            'delete_on_termination': True
        }

        inputs = {
            'os_password': openstack_config['password'],
            'os_username': openstack_config['username'],
            'os_tenant': openstack_config['tenant_name'],
            'os_auth_url': openstack_config['auth_url'],
            'os_region': os.environ['OS_REGION_NAME'],

            'os_image': '',
            'os_flavor': self.attributes.manager_server_flavor_name,
            'os_device_mapping': [device_mapping_config],
            'os_network': self.attributes.network_name,
            'os_subnet': self.attributes.subnet_name,
            'os_keypair': self.attributes.keypair_name,
            'os_security_group': self.attributes.security_group_name,

            'ssh_user': self.attributes.default_linux_username,
            'ssh_private_key_path': self.manager.remote_private_key_path,

            'ca_cert': self.attributes.LOCAL_REST_CERT_FILE,
            'ca_key': self.attributes.LOCAL_REST_KEY_FILE,
            'install_rpm_path': constants.INSTALL_RPM_PATH,
            'manager_admin_password': self.attributes.cloudify_password,

            'num_of_instances': 2,

            # We're uploading the private SSH key and OS config from
            # the Tier 2 manager to the Tier 1 managers, to be used later
            # in the bash script (see SCRIPT_SH in constants)
            'files': [
                {
                    'src': constants.REMOTE_PRIVATE_KEY_PATH,
                    'dst': constants.SSH_KEY_TMP_PATH
                },
                {
                    'src': constants.REMOTE_OPENSTACK_CONFIG_PATH,
                    'dst': constants.OS_CONFIG_TMP_PATH
                }
            ],
            'scripts': [constants.SCRIPT_SH_PATH, constants.SCRIPT_PY_PATH],

            # Config in the same format as config.yaml
            # Skipping sanity to save time
            'additional_config': {'sanity': {'skip_sanity': True}}
        }

        inputs.update(self.network_inputs)

        if self.first_deployment:
            additional_inputs = self._get_additional_resources_inputs()
        else:
            additional_inputs = self._get_upgrade_inputs()

        inputs.update(additional_inputs)
        return inputs

    def _get_upgrade_inputs(self):
        # A trick to get the deployment ID of the first cluster
        old_deployment_id = self.deployment_id.replace(
            constants.SECOND_DEP_INDICATOR,
            constants.FIRST_DEP_INDICATOR
        )
        return {
                'restore': True,
                'old_deployment_id': old_deployment_id,
                'snapshot_id': old_deployment_id,
                'transfer_agents': self.TRANSFER_AGENTS
            }

    def _get_additional_resources_inputs(self):
        return {
                'tenants': [constants.TENANT_1, constants.TENANT_2],
                'plugins': [
                    {
                        'wagon': constants.HW_OS_PLUGIN_WGN_PATH,
                        'yaml': constants.HW_OS_PLUGIN_YAML_PATH,
                        'tenant': constants.TENANT_1
                    }
                ],
                'secrets': [
                    {
                        'key': constants.SECRET_STRING_KEY,
                        'string': constants.SECRET_STRING_VALUE,
                        'tenant': constants.TENANT_2
                    },
                    {
                        'key': constants.SECRET_FILE_KEY,
                        'file': constants.SCRIPT_PY_PATH,
                        'visibility': 'global'
                    }
                ],
                'blueprints': [
                    {
                        'path': constants.BLUEPRINT_ZIP_PATH,
                        'filename': 'no-monitoring-singlehost-blueprint.yaml'
                    },
                    {
                        'path': constants.BLUEPRINT_ZIP_PATH,
                        'id': 'second_bp',
                        'filename': 'singlehost-blueprint.yaml',
                        'tenant': constants.TENANT_2
                    },
                    {
                        'path': constants.BLUEPRINT_ZIP_PATH,
                        'id': constants.HELLO_WORLD_BP,
                        'filename': 'openstack-blueprint.yaml',
                        'tenant': constants.TENANT_1,
                        'visibility': 'global'
                    }
                ],
                'deployments': [
                    {
                        'deployment_id': constants.HELLO_WORLD_DEP,
                        'blueprint_id': constants.HELLO_WORLD_BP,
                        'tenant': constants.TENANT_1,
                        'inputs': {
                            'key_pair_name': self.attributes.keypair_name,
                            'floating_network_id':
                                self.attributes.floating_network_id,
                            'agent_user':
                                self.attributes.default_linux_username,
                            'private_key_path':
                                self.manager.remote_private_key_path,
                            'image': self.attributes.default_linux_image_id,
                            'network_name': self.attributes.network_name,
                            'flavor': self.attributes.small_flavor_name
                        }
                    }
                ]
            }

    @property
    def network_inputs(self):
        raise NotImplementedError('Each Tier 1 Cluster class needs to '
                                  'add additional network inputs')

    def validate(self):
        raise NotImplementedError('Each Tier 1 Cluster class needs to '
                                  'implement the `validate` method')

    @property
    def first_deployment(self):
        """
        Indicate that this is the initial deployment, as opposed to the second
        one, to which we will upgrade
        """
        return constants.FIRST_DEP_INDICATOR in self.deployment_id

    def upload_blueprint(self):
        # We only want to upload the blueprint once, but create several deps
        if self.first_deployment:
            super(AbstractTier1Cluster, self).upload_blueprint()

    def install(self):
        super(AbstractTier1Cluster, self).install()
        self._populate_status_output()

    def _populate_status_output(self):
        # This workflow populates the deployment outputs with status info
        self.cfy.executions.start('get_status', '-d', self.deployment_id)
        self.cfy.deployments.outputs(self.deployment_id)

    def verify_installation(self):
        super(AbstractTier1Cluster, self).verify_installation()

        cluster_status = self.outputs['cluster_status']
        for service in cluster_status['leader_status']:
            assert service['status'] == 'running'

        for tier_1_manager in cluster_status['cluster_status']:
            for check in ('cloudify services', 'consul',
                          'database', 'heartbeat'):
                assert tier_1_manager[check] == 'OK'

    def deploy_and_validate(self):
        if self._deployed:
            self.logger.info('Tier 1 cluster was already deployed')
            return
        self.logger.info(
            'Deploying Tier 1 cluster on deployment: {0}'.format(
                self.deployment_id
            )
        )
        self._deployed = True
        self.upload_and_verify_install()
        self.validate()

    def backup(self):
        self.logger.info(
            'Running backup workflow on Tier 1 cluster on dep: {0}...'.format(
                self.deployment_id
            )
        )

        backup_params = {
            'snapshot_id': self.deployment_id,
            'backup_params': []
        }
        self.cfy.executions.start(
            'backup', '-d', self.deployment_id,
            '-p', json.dumps(backup_params)
        )
        self.logger.info('Backup completed successfully')

    def execute_hello_world_workflow(self, workflow_id):
        self.logger.info(
            'Executing workflow {0} on deployment {1} '
            'on a Tier 1 cluster...'.format(workflow_id,
                                            constants.HELLO_WORLD_DEP)
        )
        workflow_params = {
            'workflow_id': workflow_id,
            'deployment_id': constants.HELLO_WORLD_DEP,
            'tenant_name': constants.TENANT_1
        }

        self.cfy.executions.start([
            'execute_workflow',
            '-d', self.deployment_id,
            '-p', json.dumps(workflow_params)
        ])
        self.logger.info(
            'Successfully executed workflow {0} on deployment {1} '
            'on a Tier 1 cluster'.format(workflow_id,
                                         constants.HELLO_WORLD_DEP)
        )


class FixedIpTier1Cluster(AbstractTier1Cluster):
    TRANSFER_AGENTS = False
    RESOURCE_POOLS = [
        {
            'ip_address': '10.0.0.11',
            'hostname': 'Tier_1_Manager_1'
        },
        {
            'ip_address': '10.0.0.12',
            'hostname': 'Tier_1_Manager_2'
        }
    ]

    @property
    def network_inputs(self):
        return {
            # Only relevant when working with the Private Fixed IP paradigm.
            # See more in private_fixed_ip.yaml
            'resource_pool': self.RESOURCE_POOLS
        }

    def validate(self):
        self.logger.info('Validating deployment outputs...')
        cluster_ips = self.outputs['cluster_ips']
        actual_ips = set(cluster_ips['Slaves'] + [cluster_ips['Master']])

        fixed_ips = {r['ip_address'] for r in self.RESOURCE_POOLS}

        assert actual_ips == fixed_ips
        self.logger.info('Outputs validated successfully')


class FloatingIpTier1Cluster(AbstractTier1Cluster):
    TRANSFER_AGENTS = True

    def __init__(self, *args, **kwargs):
        super(FloatingIpTier1Cluster, self).__init__(*args, **kwargs)
        self._tier_1_client = None

    @property
    def network_inputs(self):
        return {
            # Only relevant when working with the Floating IP paradigm.
            # See more in floating_ip.yaml
            'os_floating_network': self.attributes.floating_network_id
        }

    def _patch_blueprint(self):
        # We want to import `floating_ip.yaml` instead of
        # `private_fixed_ip.yaml`, to use the Floating IP paradigm
        infra_path = str(self._cloned_to / 'include' /
                         'openstack' / 'infra.yaml')
        with open(infra_path, 'r') as f:
            blueprint_dict = yaml.load(f)

        imports = blueprint_dict['imports']
        imports.remove('private_fixed_ip.yaml')
        imports.append('floating_ip.yaml')
        blueprint_dict['imports'] = imports

        with open(infra_path, 'w') as f:
            yaml.dump(blueprint_dict, f)

    @property
    def client(self):
        if not self._tier_1_client:
            self._tier_1_client = util.create_rest_client(
                manager_ip=self.master_ip,
                username=self.attributes.cloudify_username,
                password=self.attributes.cloudify_password,
                tenant=self.attributes.cloudify_tenant,
                protocol='https',
                cert=self._get_tier_1_cert()
            )

        return self._tier_1_client

    @property
    def master_ip(self):
        return self.outputs['cluster_ips']['Master']

    def _get_tier_1_cert(self):
        local_cert = str(self.tmpdir / 'ca_cert.pem')
        self.manager.get_remote_file(
            self.attributes.LOCAL_REST_CERT_FILE,
            local_cert,
            use_sudo=True
        )
        return local_cert

    def validate(self):
        """
        For Floating IP clusters validation involves creating a REST client
        to connect to the master manager, and making sure that certain
        Cloudify resources (tenants, plugins, etc) were created
        """
        self._validate_tenants_created()
        self._validate_blueprints_created()
        self._validate_deployments_created()
        self._validate_secrets_created()
        self._validate_plugins_created()

    def _validate_tenants_created(self):
        self.logger.info(
            'Validating that tenants were created on Tier 1 cluster...'
        )
        tenants = self.client.tenants.list(_include=['name'])
        tenant_names = {t['name'] for t in tenants}
        assert tenant_names == {DEFAULT_TENANT_NAME,
                                constants.TENANT_1,
                                constants.TENANT_2}
        self.logger.info('Tenants validated successfully')

    def _validate_blueprints_created(self):
        self.logger.info(
            'Validating that blueprints were created on Tier 1 cluster...'
        )
        blueprints = self.client.blueprints.list(
            _all_tenants=True,
            _include=['id', 'tenant_name']
        )
        blueprint_pairs = {(b['id'], b['tenant_name']) for b in blueprints}
        assert blueprint_pairs == {
            (
                'cloudify-hello-world-example-4.5.no-monitoring-singlehost-blueprint',  # NOQA
                DEFAULT_TENANT_NAME
            ),
            ('second_bp', constants.TENANT_2),
            (constants.HELLO_WORLD_BP, constants.TENANT_1)
        }
        self.logger.info('Blueprints validated successfully')

    def _validate_deployments_created(self):
        self.logger.info(
            'Validating that deployments were created on Tier 1 cluster...'
        )
        deployments = self.client.deployments.list(
            _all_tenants=True,
            _include=['id', 'blueprint_id']
        )
        assert len(deployments) == 1
        deployment = deployments[0]
        assert deployment.id == constants.HELLO_WORLD_DEP
        assert deployment.blueprint_id == constants.HELLO_WORLD_BP

        self.logger.info('Deployments validated successfully')

    def _validate_secrets_created(self):
        self.logger.info(
            'Validating that secrets were created on Tier 1 cluster...'
        )
        secrets = self.client.secrets.list(_all_tenants=True)
        secrets = {s['key']: s for s in secrets}

        expected_set = {constants.SECRET_FILE_KEY, constants.SECRET_STRING_KEY}

        # During upgrade we add secrets for ssh keys, so the actual set might
        # not be equal exactly, but may contain extra values
        assert set(secrets.keys()).issuperset(expected_set)

        file_secret_value = self.client.secrets.get(constants.SECRET_FILE_KEY)
        assert file_secret_value.value == constants.PY_SCRIPT

        tenant = secrets[constants.SECRET_STRING_KEY]['tenant_name']

        # Temporarily change the tenant in the REST client, to access a secret
        # on this tenant
        with util.set_client_tenant(self, tenant):
            string_secret_value = self.client.secrets.get(
                constants.SECRET_STRING_KEY).value
            assert string_secret_value == constants.SECRET_STRING_VALUE
        self.logger.info('Secrets validated successfully')

    def _validate_plugins_created(self):
        self.logger.info(
            'Validating that plugins were created on Tier 1 cluster...'
        )

        plugins = self.client.plugins.list(_all_tenants=True)
        assert len(plugins) == 1

        plugin = plugins[0]
        assert plugin.package_name == 'cloudify-openstack-plugin'
        assert plugin.package_version == constants.HW_OS_PLUGIN_VERSION
        assert plugin['tenant_name'] == constants.TENANT_1
        self.logger.info('Plugins validated successfully')
