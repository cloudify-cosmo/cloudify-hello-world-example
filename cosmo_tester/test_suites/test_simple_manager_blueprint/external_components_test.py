from cloudify_cli import constants as cli_constants
from cloudify.workflows import local
from cosmo_tester.test_suites.test_blueprints.hello_world_bash_test import \
    AbstractHelloWorldTest
from cosmo_tester.test_suites.test_simple_manager_blueprint \
    .abstract_single_host_test import \
    AbstractSingleHostTest


class ExternalComponentsTest(AbstractHelloWorldTest, AbstractSingleHostTest):

    def setUp(self):
        super(ExternalComponentsTest, self).setUp()
        self.setup_simple_manager_env()

    def test_external_components(self):
        self._setup_external_components_vm()
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

    def _setup_external_components_vm(self):
        blueprint_path = self.copy_blueprint('external-components-vm')
        self.blueprint_yaml = \
            blueprint_path / 'external-components-blueprint.yaml'
        # rabbitmqctl will fail hard if the hostname (which this is used for)
        # goes over 63 characters, so external-components-host- has been
        # shortened to external-components- (as we were at 64 characters)
        self.prefix = 'external-components-{0}'.format(self.test_id)

        self.manager_blueprint_overrides = {}

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

        if self.env.install_plugins:
            self.logger.info('installing required plugins')
            self.cfy.local(
                'install-plugins',
                blueprint_path=self.blueprint_yaml).wait()

        self.logger.info('initialize external '
                         'components local env for running the '
                         'blueprint that starts a vm of es and influx')
        self.ext_local_env = local.init_env(
            self.blueprint_yaml,
            inputs=self.ext_inputs,
            name=self._testMethodName,
            ignored_modules=cli_constants.IGNORED_LOCAL_WORKFLOW_MODULES)

        self.logger.info('starting vm to serve as the management vm')
        self.ext_local_env.execute('install',
                                   task_retries=10,
                                   task_retry_interval=30)
        self.external_components_public_ip = \
            self.ext_local_env.outputs()[
                'external_components_vm_public_ip_address']
        self.external_components_private_ip = \
            self.ext_local_env.outputs()[
                'external_components_vm_private_ip_address']
        self.addCleanup(self.cleanup_ext)

    def cleanup_ext(self):
        self.ext_local_env.execute('uninstall',
                                   task_retries=40,
                                   task_retry_interval=30)
