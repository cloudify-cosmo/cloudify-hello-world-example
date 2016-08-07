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

import json as _json
import sys
import shutil

import fabric
import fabric.network
import fabric.api as ssh
import fabric.context_managers
from path import path

from cosmo_tester.framework import util
from cosmo_tester.framework.testenv import bootstrap, teardown, TestCase


def setUp():
    bootstrap()
    _dockercompute_manager_setup()


def tearDown():
    teardown()


def _dockercompute_manager_setup():
    _install_docker_and_configure_image()
    _upload_dockercompute_plugin()


def _install_docker_and_configure_image():
    from cosmo_tester.framework.testenv import test_environment
    username = test_environment.management_user_name
    with fabric.context_managers.settings(
            host_string=test_environment.management_ip,
            user=username,
            key_filename=test_environment.management_key_path):
        try:
            images = ssh.run('docker images --format "{{.Repository}}"')
            if 'cloudify/centos' not in images:
                raise RuntimeError
        except:
            workdir = '/root/dockercompute'
            commands = [
                'mkdir -p {0}'.format(workdir),
                'cd {0}'.format(workdir),
                'curl -fsSL -o get-docker.sh https://get.docker.com',
                'bash ./get-docker.sh',
                'usermod -aG docker {0}'.format(username),
                'systemctl start docker',
                'systemctl enable docker',
                'systemctl status docker',
            ]
            ssh.sudo(' && '.join(commands))
            # Need to reset the connection so subsequent docker calls don't
            # need sudo
            fabric.network.disconnect_all()
            with fabric.context_managers.cd(workdir):
                ssh.put(util.get_resource_path('dockercompute/Dockerfile'),
                        'Dockerfile', use_sudo=True)
                ssh.sudo('docker build -t cloudify/centos:7 .')
            _restart_management_worker_workaround()


def _restart_management_worker_workaround():
    # This works around an issue that should be fixed in which
    # Initial invocations running concurrently (i.e. two operations happening
    # at the same time, specifically, starting at the same time so dispatched
    # to the celery process pool very closely) seem to mess up celery process
    # pool. the gatekeeper component may have something to do with this but i'm
    # not sure. # For some reason, it also seems that after manually restarting
    # the management worker, future scenarios of concurrent executions will
    # cause no trouble what so ever.
    ssh.sudo('systemctl restart cloudify-mgmtworker')


def _upload_dockercompute_plugin():
    from cosmo_tester.framework.testenv import test_environment
    client = test_environment.rest_client
    docker_compute_plugin = client.plugins.list(
        package_name='cloudify-dockercompute-plugin',
        _include=['id']).items
    if docker_compute_plugin:
        return
    wagon_path = util.create_wagon(
        source_dir=util.get_resource_path('dockercompute/plugin'),
        target_dir=test_environment._workdir)
    client.plugins.upload(wagon_path)


class DockerComputeTestCase(TestCase):

    def setUp(self):
        super(DockerComputeTestCase, self).setUp()

        def cleanup():
            with self.manager_env_fabric(warn_only=True) as api:
                api.run('docker rm -f $(docker ps -aq)')
        self.addCleanup(cleanup)

    def request(self, url, method='GET', json=False, connect_timeout=10):
        command = "curl -X {0} --connect-timeout {1} '{2}'".format(
            method, connect_timeout, url)
        try:
            with self.manager_env_fabric() as api:
                result = api.run(command)
            if json:
                result = _json.loads(result)
            return result
        except:
            tpe, value, tb = sys.exc_info()
            raise RuntimeError, RuntimeError(str(value)), tb

    def ip(self, node_id, deployment_id=None):
        return self._instance(
            node_id,
            deployment_id=deployment_id).runtime_properties['ip']

    def key_path(self, node_id, deployment_id=None):
        return self._instance(
            node_id,
            deployment_id=deployment_id).runtime_properties[
            'cloudify_agent']['key']

    def kill_container(self, node_id, deployment_id=None):
        container_id = self._instance(
            node_id,
            deployment_id=deployment_id).runtime_properties['container_id']
        with self.manager_env_fabric() as api:
            api.run('docker rm -f {0}'.format(container_id))

    def _instance(self, node_id, deployment_id):
        deployment_id = deployment_id or self.test_id
        return self.client.node_instances.list(
            node_id=node_id, deployment_id=deployment_id)[0]

    @staticmethod
    def blueprint_resource_path(resource_path):
        return util.get_resource_path('dockercompute/blueprints/{0}'.format(
            resource_path))

    def add_plugin_yaml_to_blueprint(self, blueprint_yaml=None):
        blueprint_yaml = blueprint_yaml or self.blueprint_yaml
        blueprint_yaml = path(blueprint_yaml)
        target_plugin_yaml_name = 'dockercompute-plugin.yaml'
        with util.YamlPatcher(blueprint_yaml) as patcher:
            patcher.obj['imports'].append(target_plugin_yaml_name)
        shutil.copy(util.get_resource_path('dockercompute/plugin.yaml'),
                    blueprint_yaml.dirname() / target_plugin_yaml_name)
