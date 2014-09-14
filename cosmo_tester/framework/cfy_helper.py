########
# Copyright (c) 2014 GigaSpaces Technologies Ltd. All rights reserved
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
import shutil
import json

import sh
from path import path

from cloudify_cli.utils import load_cloudify_working_dir_settings
from cosmo_tester.framework.util import sh_bake


cfy = sh_bake(sh.cfy)


DEFAULT_EXECUTE_TIMEOUT = 1800


class CfyHelper(object):

    def __init__(self,
                 cfy_workdir=None,
                 management_ip=None):
        self._cfy_workdir = cfy_workdir
        self.tmpdir = False
        if cfy_workdir is None:
            self.tmpdir = True
            self._cfy_workdir = tempfile.mkdtemp(prefix='cfy-')
        self.workdir = path(self._cfy_workdir)
        if management_ip is not None:
            self.use(management_ip)

    def bootstrap(self,
                  cloud_config_path,
                  provider,
                  keep_up_on_failure=False,
                  verbose=False,
                  dev_mode=False):
        with self.workdir:
            cfy.init(
                provider=provider,
                verbosity=verbose).wait()
            cfy.bootstrap(
                config_file=cloud_config_path,
                keep_up_on_failure=keep_up_on_failure,
                dev_mode=dev_mode,
                verbosity=verbose).wait()

    def teardown(self,
                 cloud_config_path,
                 ignore_deployments=True,
                 ignore_validation=False,
                 verbose=False):
        with self.workdir:
            cfy.teardown(
                config_file=cloud_config_path,
                ignore_deployments=ignore_deployments,
                ignore_validation=ignore_validation,
                force=True,
                verbosity=verbose).wait()

    def upload_deploy_and_execute_install(
            self,
            blueprint_path,
            blueprint_id,
            deployment_id,
            verbose=False,
            include_logs=True,
            execute_timeout=DEFAULT_EXECUTE_TIMEOUT,
            inputs=None):
        with self.workdir:
            self.upload_blueprint(
                blueprint_path=blueprint_path,
                blueprint_id=blueprint_id,
                verbose=verbose)
            self.create_deployment(
                blueprint_id=blueprint_id,
                deployment_id=deployment_id,
                verbose=verbose,
                inputs=inputs)
            self.execute_install(
                deployment_id=deployment_id,
                execute_timeout=execute_timeout,
                verbose=verbose,
                include_logs=include_logs)

    def create_deployment(self,
                          blueprint_id,
                          deployment_id,
                          verbose=False,
                          inputs=None):
        with self.workdir:
            inputs = inputs or {}
            inputs_file = tempfile.mktemp(prefix=deployment_id,
                                          suffix='-inputs.json',
                                          dir=self.workdir)
            with open(inputs_file, 'w') as f:
                f.write(json.dumps(inputs))
            cfy.deployments.create(
                blueprint_id=blueprint_id,
                deployment_id=deployment_id,
                verbosity=verbose,
                inputs=inputs_file).wait()

    def execute_install(self,
                        deployment_id,
                        verbose=False,
                        include_logs=True,
                        execute_timeout=DEFAULT_EXECUTE_TIMEOUT):
        self._execute_workflow(
            workflow='install',
            deployment_id=deployment_id,
            execute_timeout=execute_timeout,
            verbose=verbose,
            include_logs=include_logs)

    def execute_uninstall(self,
                          deployment_id,
                          verbose=False,
                          include_logs=True,
                          execute_timeout=DEFAULT_EXECUTE_TIMEOUT):
        self._execute_workflow(
            workflow='uninstall',
            deployment_id=deployment_id,
            execute_timeout=execute_timeout,
            verbose=verbose,
            include_logs=include_logs)

    def upload_blueprint(self,
                         blueprint_id,
                         blueprint_path,
                         verbose=False):
        with self.workdir:
            cfy.blueprints.upload(
                blueprint_path=blueprint_path,
                blueprint_id=blueprint_id,
                verbosity=verbose).wait()

    def download_blueprint(self, blueprint_id):
        with self.workdir:
            cfy.blueprints.download(blueprint_id=blueprint_id).wait()

    def use(self, management_ip):
        with self.workdir:
            cfy.use(
                management_ip=management_ip
            ).wait()

    def get_management_ip(self):
        with self.workdir:
            settings = load_cloudify_working_dir_settings()
            return settings.get_management_server()

    def get_provider_context(self):
        with self.workdir:
            settings = load_cloudify_working_dir_settings()
            return settings.get_provider_context()

    def close(self):
        if self.tmpdir:
            shutil.rmtree(self._cfy_workdir)

    def _execute_workflow(self,
                          workflow,
                          deployment_id,
                          verbose=False,
                          include_logs=True,
                          execute_timeout=DEFAULT_EXECUTE_TIMEOUT):
        with self.workdir:
            cfy.executions.start(
                workflow=workflow,
                deployment_id=deployment_id,
                timeout=execute_timeout,
                verbosity=verbose,
                include_logs=include_logs).wait()
