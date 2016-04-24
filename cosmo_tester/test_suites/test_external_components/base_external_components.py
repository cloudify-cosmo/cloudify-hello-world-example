from cloudify_cli import constants as cli_constants
from cloudify.workflows import local
from cosmo_tester.test_suites.test_blueprints.hello_world_bash_test import \
    AbstractHelloWorldTest
from cosmo_tester.test_suites.test_simple_manager_blueprint \
    .abstract_single_host_test import \
    AbstractSingleHostTest


class BaseExternalComponentsTest(AbstractHelloWorldTest,
                                 AbstractSingleHostTest):

    def setUp(self):
        super(BaseExternalComponentsTest, self).setUp()
        self.setup_simple_manager_env()

    def setup_external_components_vm(self):
        blueprint_path = self.copy_blueprint('external-components-vm')
        self.blueprint_yaml = \
            blueprint_path / 'external-components-blueprint.yaml'

        if self.env.install_plugins:
            self.logger.info('installing required plugins')
            self.cfy.install_plugins_locally(
                blueprint_path=self.blueprint_yaml)

        self.logger.info('initialize external '
                         'components local env for running the '
                         'blueprint that starts a vm of es, rabbit, and '
                         'influx')
        self.ext_local_env = local.init_env(
            self.blueprint_yaml,
            inputs=self.ext_inputs,
            name=self._testMethodName,
            ignored_modules=cli_constants.IGNORED_LOCAL_WORKFLOW_MODULES)

        self.addCleanup(self.env.handler.remove_keypairs_from_local_env,
                        self.ext_local_env)
        self.addCleanup(self.cleanup_ext)

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

    def cleanup_ext(self):
        self.ext_local_env.execute('uninstall',
                                   task_retries=40,
                                   task_retry_interval=30)
