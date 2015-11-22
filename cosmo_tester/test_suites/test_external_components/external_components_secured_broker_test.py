from cosmo_tester.test_suites.test_broker_security import \
    inputs
from cosmo_tester.test_suites.test_broker_security \
    .broker_security_test_base import BrokerSecurityTestBase
from cosmo_tester.test_suites.test_external_components \
    .base_external_components import BaseExternalComponentsTest
from cosmo_tester.framework.util import create_rest_client


class ExternalComponentsSecuredBrokerTest(BaseExternalComponentsTest,
                                          BrokerSecurityTestBase):

    def test_external_components_with_secured_broker(self):
        self._handle_ssl_files()
        broker_security_inputs = inputs.BrokerSecurity(
            cert_path=self.cert_path,
            key_path=self.key_path,
        )

        # rabbitmqctl will fail hard if the hostname (which this is used for)
        # goes over 63 characters, so external-components-host- has been
        # shortened to external-components- (as we were at 64 characters)
        self.prefix = 'ext-comp-sec-broker-{0}'.format(self.test_id)
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
            'broker_ssl_public_cert': broker_security_inputs.public_cert,
            'broker_ssl_private_cert': broker_security_inputs.private_key,
            'key_pair_path': '{0}/{1}-keypair.pem'.format(self.workdir,
                                                          self.prefix)
        }
        self.manager_blueprint_overrides = {}

        self.setup_external_components_vm()
        additional_bootstrap_inputs = {
            'rabbitmq_endpoint_ip': self.external_components_public_ip,
            'rabbitmq_ssl_enabled': True,
            'rabbitmq_cert_public': broker_security_inputs.public_cert,
        }
        self.logger.info(str(additional_bootstrap_inputs))
        self.bootstrap_simple_manager_blueprint(additional_bootstrap_inputs)
        import time
        time.sleep(5)
        self._run(blueprint_file='singlehost-blueprint.yaml',
                  inputs=dict(self.access_credentials,
                              **{'server_ip': self.public_ip_address}))

    def _running_env_setup(self, management_ip):
        # Copied from abstract single host test as this one must be used
        # rather than the one from the broker security test base
        self.env.management_ip = management_ip
        self.client = create_rest_client(management_ip)
        response = self.client.manager.get_status()
        if not response['status'] == 'running':
            raise RuntimeError('Manager at {0} is not running.'
                               .format(management_ip))
