from cosmo_tester.test_suites.test_external_components \
    .base_external_components import BaseExternalComponentsTest


class ExternalComponentsTest(BaseExternalComponentsTest):

    def test_external_components(self):
        # rabbitmqctl will fail hard if the hostname (which this is used for)
        # goes over 63 characters, so external-components-host- has been
        # shortened to external-components- (as we were at 64 characters)
        self.prefix = 'external-components-{0}'.format(self.test_id)
        self.ext_inputs = {
            'prefix': self.prefix,
            'external_network': self.env.external_network_name,
            'os_username': self.env.keystone_username,
            'os_password': self.env.keystone_password,
            'os_tenant_name': self.env.keystone_tenant_name,
            'os_region': self.env.region,
            'os_auth_url': self.env.keystone_url,
            'image_id': self.env.centos_7_image_name,
            'flavor': self.env.medium_flavor_id,
            'key_pair_path': '{0}/{1}-keypair.pem'.format(self.workdir,
                                                          self.prefix)
        }
        self.manager_blueprint_overrides = {}

        self.setup_external_components_vm()
        additional_bootstrap_inputs = {
            'elasticsearch_endpoint_ip': self.external_components_public_ip,
            'influxdb_endpoint_ip': self.external_components_public_ip,
            'rabbitmq_endpoint_ip': self.external_components_public_ip,
        }
        self.logger.info(str(additional_bootstrap_inputs))
        self.bootstrap_simple_manager_blueprint(additional_bootstrap_inputs)
        self._run(blueprint_file='singlehost-blueprint.yaml',
                  inputs=dict(self.access_credentials,
                              **{'server_ip': self.public_ip_address}),
                  influx_host_ip=self.external_components_public_ip)
