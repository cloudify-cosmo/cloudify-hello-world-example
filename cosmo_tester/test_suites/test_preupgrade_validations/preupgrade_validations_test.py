########
# Copyright (c) 2016 GigaSpaces Technologies Ltd. All rights reserved
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
"""Manager pre-upgrade validation tests.

Test the validations that run before a manager upgrade.
These tests use the environment manager, don't bootstrap a new one on a
test-by-test basis.
The test procedures can be destructive (changing properties, renaming
directories), but care is taken to restore the manager to its original state.
"""


from contextlib import contextmanager
from cStringIO import StringIO
from fabric.context_managers import quiet
import json
import os
import re
import sh
import shutil

from cosmo_tester.framework.testenv import TestCase
from cosmo_tester.framework.git_helper import clone
from cosmo_tester.framework.util import YamlPatcher


UPGRADE_REPO_URL = 'https://github.com/cloudify-cosmo/' \
                   'cloudify-manager-blueprints.git'
UPGRADE_BRANCH = 'master'


class TestManagerPreupgradeValidations(TestCase):
    def test_default_validations(self):
        """Simply run the validations to check that they pass."""
        inputs = self.get_upgrade_inputs()
        with self.maintenance_mode():
            self.cfy.upgrade(
                self.get_simple_blueprint(),
                inputs=inputs,
                validate_only=True)

    def test_elasticsearch_up(self):
        """Validation breaks when elasticsearch is down.

        We won't actually be bringing ES down, instead we'll just change
        the port number the validation is checking.
        """
        inputs = self.get_upgrade_inputs()
        with self.change_es_port(), self.maintenance_mode():
            try:
                self.cfy.upgrade(
                    self.get_simple_blueprint(),
                    inputs=inputs,
                    validate_only=True)
            except sh.ErrorReturnCode as e:
                self.assertIn(
                    'error when getting the provider context',
                    e.stdout.lower())
            else:
                self.fail('ES validation should have failed')

    def test_elasticsearch_memory(self):
        """It is invalid to pass a lower ES heap size than original."""
        blueprint_path = self.get_simple_blueprint()
        self.use_existing_on_update(blueprint_path, 'elasticsearch', False)

        # set a heap size lower than what's currently used: just pass 1MB,
        # which surely must be lower than whatever the manager is
        # currently using!
        inputs = self.get_upgrade_inputs(elasticsearch_heap_size='1m')
        with self.maintenance_mode():
            try:
                self.cfy.upgrade(
                    blueprint_path,
                    inputs=inputs,
                    validate_only=True)
            except sh.ErrorReturnCode as e:
                self.assertIn(
                    'elasticsearch heap size lower',
                    e.stdout.lower())
            else:
                self.fail('ES validation should have failed')

    def test_service_alive_checks(self):
        """Validation uses checks that the required services are running.

        Bring down each service, check that validation breaks when it notices
        the service isn't running, then bring it up again.
        """
        blueprint_path = self.get_simple_blueprint()
        inputs = self.get_upgrade_inputs()

        with self.maintenance_mode():
            # we can't test nginx or the restservice this way, because if we
            # turn them off, we won't be able to execute the upgrade :)
            for service_name, display_name in [
                ('cloudify-mgmtworker', 'mgmtworker'),
                ('logstash', 'logstash'),
                ('elasticsearch', 'elasticsearch'),
                ('cloudify-amqpinflux', 'amqpinflux'),
                ('cloudify-riemann', 'riemann'),
                ('cloudify-amqpinflux', 'amqpinflux'),
                ('cloudify-influxdb', 'influxdb')
            ]:
                with self.disable_service(service_name):
                    try:
                        self.cfy.upgrade(
                            blueprint_path,
                            inputs=inputs,
                            validate_only=True)
                    except sh.ErrorReturnCode as e:
                        self.assertIn(
                            '{0} is not running'.format(display_name),
                            e.stdout.lower())
                    else:
                        self.fail('Validation for {0} succeeded but it should '
                                  'have failed - the service was not running'
                                  .format(display_name))

    def test_node_directories(self):
        """Validation checks that the required directory structure exists.

        Rename the node_properties and resources directories, check that
        validation breaks when it notices they're missing, then restore their
        original names.
        """
        blueprint_path = self.get_simple_blueprint()
        inputs = self.get_upgrade_inputs()

        with self.maintenance_mode():
            for node_name in [
                'influxdb',
                'rabbitmq',
                'elasticsearch',
                'amqpinflux',
                'logstash',
                'restservice',
                'nginx',
                'riemann',
                'mgmtworker',
            ]:
                with self.move_upgrade_dirs(node_name):
                    try:
                        self.cfy.upgrade(
                            blueprint_path,
                            inputs=inputs,
                            validate_only=True)
                    except sh.ErrorReturnCode as e:
                        self.assertIn(
                            'service {0} has no properties file'.format(
                                node_name),
                            e.stdout.lower())
                    else:
                        self.fail('Upgrade directories validation for {0} '
                                  'succeeded, but it should have failed - '
                                  'node properties and rollback directories '
                                  'are missing'.format(node_name))

    def test_rabbit_properties_changed(self):
        """Validation doesn't allow changing rabbitmq credentials.

        Try upgrading with a changed rabbitmq password, check that validation
        breaks.
        """
        blueprint_path = self.get_simple_blueprint()
        self.use_existing_on_update(blueprint_path, 'rabbitmq', False)
        changed_properties = self.get_changed_rabbit_properties()
        inputs = self.get_upgrade_inputs(**changed_properties)

        with self.maintenance_mode():
            try:
                self.cfy.upgrade(
                    blueprint_path,
                    inputs=inputs,
                    validate_only=True)
            except sh.ErrorReturnCode as e:
                self.assertIn('rabbitmq properties must not change',
                              e.stdout.lower())

                # parse out the error message - it says which properties
                # changed, but musn't
                changed_names = re.findall('Changed properties: (.*)',
                                           e.stdout)[0]

                for property_name in changed_properties:
                    self.assertIn(
                        property_name, changed_names,
                        'Property changed but validation did not break: {0}'
                        .format(property_name))
            else:
                self.fail('rabbitmq validation should have failed')

    def test_manager_security_settings_changed(self):
        """Validation doesn't allow changing manager security settings.

        Try several sets of inputs, each changing some other properties,
        check that all fail the preupgrade validation.
        """
        blueprint_path = self.get_simple_blueprint()
        self.use_existing_on_update(blueprint_path, 'manager_configuration',
                                    False)
        properties = self.get_node_properties('manager-config')
        security = properties['security']

        # several separate sets of inputs, each will be tried separately
        failing_inputs = [
            self.get_upgrade_inputs(
                security_enabled=not security['enabled']),
            self.get_upgrade_inputs(
                ssl_enabled=not security['ssl']['enabled']),
            self.get_upgrade_inputs(
                admin_username=security.get('admin_username', '') + '-changed'
            ),
            self.get_upgrade_inputs(
                admin_password=security.get('admin_password', '') + '-changed'
            ),
        ]

        with self.maintenance_mode():
            for inputs in failing_inputs:
                try:
                    self.cfy.upgrade(
                        blueprint_path,
                        inputs=inputs,
                        validate_only=True)
                except sh.ErrorReturnCode as e:
                    self.assertIn('manager-config properties must not change',
                                  e.stdout.lower())
                else:
                    self.fail('manager config validation should have failed: '
                              'security settings changed')

    def test_manager_ssh_user_changed(self):
        """Validation doesn't allow changing the ssh_user.

        Changing ssh_user isn't really common, because the new value is also
        used to ssh into the machine! So it would have to be a valid user
        that can ssh in.
        It is still possible that the manager machine has multiple users that
        can ssh into it - in this case, only the user that bootstrapped the
        manager can upgrade it.

        We test it by changing the stored properties, to say the manager was
        bootstrapped with a nonexistent user, rather than creating a new user
        and trying to upgrade using it (because that would have been much
        harder to clean up reliably after).
        """
        blueprint_path = self.get_simple_blueprint()
        self.use_existing_on_update(blueprint_path, 'manager_configuration',
                                    False)

        with self.maintenance_mode(), self.change_ssh_user():
            try:
                self.cfy.upgrade(
                    blueprint_path,
                    inputs=self.get_upgrade_inputs(),
                    validate_only=True)

            except sh.ErrorReturnCode as e:
                self.assertIn('manager-config properties must not change',
                              e.stdout.lower())
            else:
                self.fail('manager config validation should have failed: '
                          'security settings changed')

    def get_simple_blueprint(self):
        """Blueprint to run the upgrade with.

        We use the simple blueprint for upgrading the manager, no matter
        which blueprint was originally used for bootstrapping.
        """
        blueprint_dir = clone(UPGRADE_REPO_URL, self.workdir,
                              branch=UPGRADE_BRANCH)
        blueprint_path = (blueprint_dir /
                          'simple-manager-blueprint.yaml')
        self.addCleanup(shutil.rmtree, blueprint_dir)
        return blueprint_path

    def get_upgrade_inputs(self, **override):
        """Default inputs that can be used for upgrading."""
        inputs = {
            'private_ip': self.get_manager_ip(),
            'public_ip': self.get_manager_ip(),
            'ssh_key_filename': self.env.management_key_path,
            'ssh_user': self.env.management_user_name,
            'ssh_port': 22
        }
        inputs.update(override)
        return self.get_inputs_in_temp_file(inputs, 'upgrade')

    def get_node_properties_path(self, node_name):
        """Path to the node's properties.json file"""
        return os.path.join('/opt/cloudify', node_name,
                            'node_properties/properties.json')

    def get_node_properties(self, node_name):
        """Fetch the stored node properties from the manager."""
        fetched_properties = StringIO()
        properties_path = self.get_node_properties_path(node_name)
        with self.manager_env_fabric() as fabric:
            fabric.get(properties_path, fetched_properties)
        fetched_properties.seek(0)
        return json.load(fetched_properties)

    def put_node_properties(self, node_name, properties):
        """Overwrite node properties in manager's storage"""
        properties_path = self.get_node_properties_path(node_name)
        with self.manager_env_fabric() as fabric:
            fabric.put(StringIO(json.dumps(properties)), properties_path)

    def use_existing_on_update(self, blueprint_path, node_name,
                               use_existing=False):
        """Mark the node with use_existing_on_upgrade in the blueprint."""
        with YamlPatcher(blueprint_path) as yamlpatch:
            yamlpatch.set_value(
                ('node_templates.{0}.properties'
                 '.use_existing_on_upgrade').format(node_name),
                use_existing)
        return blueprint_path

    @contextmanager
    def change_es_port(self):
        """Change the elasticsearch port saved in node properties.

        In the check that verifies if elasticsearch is up, we can't actually
        bring elasticsearch down, because then we won't be able to communicate
        with the manager.

        Instead, let's change the stored port number, so that the check
        is tricked into examining that one.
        """
        properties = self.get_node_properties('elasticsearch')
        original_port = properties['es_endpoint_port']
        properties['es_endpoint_port'] = original_port - 1
        self.put_node_properties('elasticsearch', properties)

        try:
            yield
        finally:
            properties['es_endpoint_port'] = original_port
            self.put_node_properties('elasticsearch', properties)

    @contextmanager
    def change_ssh_user(self):
        properties = self.get_node_properties('manager-config')
        original_user = properties['ssh_user']
        properties['ssh_user'] = original_user + '-changed'
        self.put_node_properties('manager-config', properties)

        try:
            yield
        finally:
            properties['ssh_user'] = original_user
            self.put_node_properties('manager-config', properties)

    def get_changed_rabbit_properties(self):
        properties = self.get_node_properties('rabbitmq')
        changed_properties = {
            name: properties[name] + '-changed'
            for name in [
                'rabbitmq_username', 'rabbitmq_password',
                'rabbitmq_cert_public', 'rabbitmq_cert_private'
            ]
        }
        changed_properties['rabbitmq_ssl_enabled'] = \
            not properties['rabbitmq_ssl_enabled']

        # couldn't possibly have been the original ip
        changed_properties['rabbitmq_endpoint_ip'] = '255.255.255.255'
        return changed_properties

    @contextmanager
    def disable_service(self, service_name):
        """Temporarily disable a service using systemd."""
        with self.manager_env_fabric() as fabric:
            fabric.sudo('systemctl stop {0}'.format(service_name))

        try:
            yield
        finally:
            with self.manager_env_fabric() as fabric, quiet():
                fabric.sudo('systemctl start {0}'.format(service_name))

    @contextmanager
    def move_upgrade_dirs(self, node_name):
        """Rename the node_properties and resources directories."""
        base = os.path.join('/opt/cloudify', node_name)
        properties_dir = os.path.join(base, 'node_properties')
        properties_dir_backup = os.path.join(base, 'node_properties_backup')
        resources_dir = os.path.join(base, 'resources')
        resources_dir_backup = os.path.join(base, 'resources_backup')

        with self.manager_env_fabric() as fabric:
            fabric.sudo('mv {0} {1}'.format(properties_dir,
                                            properties_dir_backup))
            fabric.sudo('mv {0} {1}'.format(resources_dir,
                                            resources_dir_backup))

        try:
            yield
        finally:
            with self.manager_env_fabric() as fabric:
                fabric.sudo('mv {0} {1}'.format(properties_dir_backup,
                                                properties_dir))
                fabric.sudo('mv {0} {1}'.format(resources_dir_backup,
                                                resources_dir))
