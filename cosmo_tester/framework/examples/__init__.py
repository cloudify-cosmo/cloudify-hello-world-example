########
# Copyright (c) 2017 GigaSpaces Technologies Ltd. All rights reserved
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

import json
import os
from abc import ABCMeta

import pytest
import testtools

from cosmo_tester.framework import git_helper
from cosmo_tester.framework.util import set_client_tenant


class AbstractExample(testtools.TestCase):

    __metaclass__ = ABCMeta

    REPOSITORY_URL = None

    def __init__(self, cfy, manager, attributes, ssh_key, logger, tmpdir,
                 branch=None, tenant='default_tenant', suffix=''):
        self.attributes = attributes
        self.logger = logger
        self.manager = manager
        self.cfy = cfy
        self.tmpdir = tmpdir
        self.branch = branch
        self._ssh_key = ssh_key
        self._cleanup_required = False
        self._blueprint_file = None
        self._inputs = None
        self._cloned_to = None
        self.blueprint_id = 'hello-{suffix}'.format(suffix=suffix)
        self.deployment_id = self.blueprint_id
        self.verify_metrics = True
        self.skip_plugins_validation = False
        self.tenant = tenant
        self.suffix = suffix

    @property
    def blueprint_file(self):
        if not self._blueprint_file:
            raise ValueError('blueprint_file not set')
        return self._blueprint_file

    @blueprint_file.setter
    def blueprint_file(self, value):
        self._blueprint_file = value

    @property
    def blueprint_path(self):
        if not self._cloned_to:
            raise RuntimeError('_cloned_to is not set')
        return self._cloned_to / self.blueprint_file

    @property
    def cleanup_required(self):
        return self._cleanup_required

    @property
    def outputs(self):
        with set_client_tenant(self.manager, self.tenant):
            outputs = self.manager.client.deployments.outputs.get(
                self.deployment_id,
            )['outputs']
        self.logger.info('Deployment outputs: %s%s',
                         os.linesep, json.dumps(outputs, indent=2))
        return outputs

    def verify_all(self):
        self.upload_blueprint()
        self.create_deployment()
        self.install()
        self.verify_installation()
        self.uninstall()
        self.delete_deployment()

    def verify_installation(self):
        self.assert_deployment_events_exist()
        if self.verify_metrics:
            self.assert_deployment_metrics_exist()

    def upload_and_verify_install(self):
        self.upload_blueprint()
        self.create_deployment()
        self.install()
        self.verify_installation()

    def delete_deployment(self):
        self.logger.info('Deleting deployment...')
        with set_client_tenant(self.manager, self.tenant):
            self.manager.client.deployments.delete(
                self.deployment_id,
            )

    def uninstall(self):
        self.logger.info('Uninstalling deployment...')
        self.cfy.executions.start.uninstall(['-d', self.deployment_id,
                                             '-t', self.tenant])
        self._cleanup_required = False

    def _patch_blueprint(self):
        """ A method that add the ability to patch the blueprint if needed """
        pass

    def upload_blueprint(self):
        self.clone_example()
        blueprint_file = self._cloned_to / self.blueprint_file
        self._patch_blueprint()

        self.logger.info('Uploading blueprint: %s [id=%s]',
                         blueprint_file,
                         self.blueprint_id)
        with set_client_tenant(self.manager, self.tenant):
            self.manager.client.blueprints.upload(
                blueprint_file, self.blueprint_id)

    def create_deployment(self):
        self.logger.info(
                'Creating deployment [id=%s] with the following inputs:%s%s',
                self.deployment_id,
                os.linesep,
                json.dumps(self.inputs, indent=2))
        with set_client_tenant(self.manager, self.tenant):
            self.manager.client.deployments.create(
                    self.deployment_id, self.blueprint_id, inputs=self.inputs,
                    skip_plugins_validation=self.skip_plugins_validation)
        self.cfy.deployments.list(tenant_name=self.tenant)

    def install(self):
        self.logger.info('Installing deployment...')
        self._cleanup_required = True
        try:
            self.cfy.executions.start.install(['-d', self.deployment_id,
                                               '-t', self.tenant])
        except Exception as e:
            if 'if there is a running system-wide' in e.message:
                self.logger.error('Error on deployment execution: %s', e)
                self.logger.info('Listing executions..')
                self.cfy.executions.list(['-d', self.deployment_id])
                self.cfy.executions.list(['--include-system-workflows'])
            raise

    def clone_example(self):
        if not self._cloned_to:
            # Destination will be e.g.
            # /tmp/pytest_generated_tempdir_for_test_1/examples/bootstrap_ssl/
            destination = os.path.join(
                str(self.tmpdir), 'examples', self.suffix,
            )
            self._cloned_to = git_helper.clone(self.REPOSITORY_URL,
                                               destination,
                                               branch=self.branch)

    def cleanup(self):
        if self._cleanup_required:
            self.logger.info('Performing hello world cleanup..')
            self.cfy.executions.start.uninstall(
                    ['-d', self.deployment_id, '-p',
                     'ignore_failure=true', '-f',
                     '-t', self.tenant])

    def assert_deployment_metrics_exist(self):
        self.logger.info('Verifying deployment metrics...')
        # This query finds all the time series that begin with the
        # deployment ID (which should be all the series created by diamond)
        # and have values in the last 5 seconds
        with self.manager.ssh() as fabric:
            result = fabric.run(
                'curl -G "{url}" --data-urlencode '
                '"q=select * from /^{dep}\./i '
                'where time > now() - 5s"'.format(
                    url=self.manager.influxdb_url,
                    dep=self.deployment_id
                ), quiet=True
            )
            if result == '[]':
                pytest.fail(
                    'Monitoring events list for deployment with ID `{0}` '
                    'were not found on influxDB'.format(self.deployment_id))

    def assert_deployment_events_exist(self):
        self.logger.info('Verifying deployment events..')
        with set_client_tenant(self.manager, self.tenant):
            executions = self.manager.client.executions.list(
                deployment_id=self.deployment_id,
            )
            events, total_events = self.manager.client.events.get(
                executions[0].id,
            )
        self.assertGreater(len(events), 0,
                           'There are no events for deployment: {0}'.format(
                                   self.deployment_id))
