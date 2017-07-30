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

import base64
import json
import logging
import os
import re
import shutil
import socket
import sys
import tempfile
import time
import urllib
import subprocess

import jinja2
import requests
import retrying
import sh
import yaml

from openstack import connection as openstack_connection
from path import path, Path

from cloudify_cli import env as cli_env
from cloudify_rest_client import CloudifyClient

import cosmo_tester
from cosmo_tester import resources


class AttributesDict(dict):
    __getattr__ = dict.__getitem__


def get_attributes(logger=logging, resources_dir=None):
    attributes_file = get_resource_path('attributes.yaml', resources_dir)
    logger.info('Loading attributes from: %s', attributes_file)
    with open(attributes_file, 'r') as f:
        attrs = AttributesDict(yaml.load(f))
        return attrs


def get_cli_version():
    return cli_env.get_version_data()['version']


def download_file(url, destination=''):

    if not destination:
        fd, destination = tempfile.mkstemp(suffix=url.split('/')[-1])
        os.remove(destination)
        os.close(fd)

    final_url = urllib.urlopen(url).geturl()
    f = urllib.URLopener()
    f.retrieve(final_url, destination)
    return destination


def get_openstack_server_password(server_id, private_key_path=None):
    """Since openstacksdk does not contain this functionality and adding
    python-novaclient as a dependency creates a dependencies hell, it is
    easier to just call the relevant OpenStack REST API call for retrieving
    the server's password."""

    conn = create_openstack_client()
    compute_endpoint = conn.session.get_endpoint(service_type='compute')
    url = '{}/servers/{}/os-server-password'.format(
            compute_endpoint, server_id)
    headers = conn.session.get_auth_headers()
    headers['Content-Type'] = 'application/json'
    r = requests.get(url, headers=headers)
    if r.status_code != 200:
        raise RuntimeError(
                'OpenStack get password response status (%d) != 200: {}'
                .format(r.status_code, r.text))
    password = r.json()['password']
    if private_key_path:
        return _decrypt_password(password, private_key_path)
    else:
        return password


def _decrypt_password(password, private_key_path):
    """Base64 decodes password and unencrypts it with private key.

    Requires openssl binary available in the path.
    """
    unencoded = base64.b64decode(password)
    cmd = ['openssl', 'rsautl', '-decrypt', '-inkey', private_key_path]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    out, err = proc.communicate(unencoded)
    proc.stdin.close()
    if proc.returncode:
        raise RuntimeError(err)
    return out


def create_openstack_client():
    conn = openstack_connection.Connection(
            auth_url=os.environ['OS_AUTH_URL'],
            project_name=os.environ['OS_PROJECT_NAME'],
            username=os.environ['OS_USERNAME'],
            password=os.environ['OS_PASSWORD'])
    return conn


def process_variables(suites_yaml, unprocessed_dict):
    template_variables = suites_yaml.get('variables', {})
    result = {}
    for key, unprocessed_value in unprocessed_dict.items():
        if not isinstance(unprocessed_value, basestring):
            value = unprocessed_value
        else:
            value = jinja2.Template(unprocessed_value).render(
                **template_variables)
        result[key] = value
    return result


def generate_unique_configurations(
        workdir,
        original_inputs_path,
        original_manager_blueprint_path,
        manager_blueprint_dir_name='manager-blueprint'):
    inputs_path = path(os.path.join(workdir, 'inputs.yaml'))
    shutil.copy(original_inputs_path, inputs_path)
    manager_blueprint_base = os.path.basename(
        original_manager_blueprint_path)
    source_manager_blueprint_dir = os.path.dirname(
        original_manager_blueprint_path)
    target_manager_blueprint_dir = os.path.join(
        workdir, manager_blueprint_dir_name)

    def ignore(src, names):
        return names if os.path.basename(src) == '.git' else set()
    shutil.copytree(source_manager_blueprint_dir,
                    target_manager_blueprint_dir,
                    ignore=ignore)
    manager_blueprint_path = path(
        os.path.join(target_manager_blueprint_dir,
                     manager_blueprint_base))
    return inputs_path, manager_blueprint_path


def sh_bake(command):
    """Make the command also print its stderr and stdout to our stdout/err."""
    # we need to pass the received lines back to the process._stdout/._stderr
    # so that they're not only printed out, but also saved as .stderr/.sdtout
    # on the return value or on the exception.
    return command.bake(_out=pass_stdout, _err=pass_stderr)


def get_cfy():
    return sh.cfy.bake(
        _err_to_out=True,
        _out=lambda l: sys.stdout.write(l),
        _tee=True
    )


def pass_stdout(line, input_queue, process):
    output = line.encode(process.call_args['encoding'])
    process._stdout.append(output)
    sys.stdout.write(output)


def pass_stderr(line, input_queue, process):
    output = line.encode(process.call_args['encoding'])
    process._stderr.append(output)
    sys.stderr.write(output)


def get_blueprint_path(blueprint_name, blueprints_dir=None):
    resources_dir = os.path.dirname(resources.__file__)
    blueprints_dir = blueprints_dir or os.path.join(resources_dir,
                                                    'blueprints')
    return os.path.join(blueprints_dir, blueprint_name)


def get_resource_path(resource, resources_dir=None):
    resources_dir = resources_dir or os.path.dirname(resources.__file__)
    return os.path.join(resources_dir, resource)


def get_cloudify_config(name):
    reference_dir = resources.__file__
    for _ in range(3):
        reference_dir = os.path.dirname(reference_dir)
    config_path = os.path.join(reference_dir,
                               'suites',
                               'configurations',
                               name)
    return yaml.load(path(config_path).text())


def get_yaml_as_dict(yaml_path):
    return yaml.load(path(yaml_path).text())


def fix_keypath(env, keypath):
    p = list(os.path.split(keypath))
    base, ext = os.path.splitext(p[-1])
    base = '{}{}'.format(env.resources_prefix, base)
    p[-1] = base + ext
    return os.path.join(*p)


def get_actual_keypath(env, keypath, raise_on_missing=True):
    keypath = path(os.path.expanduser(keypath)).abspath()
    if not keypath.exists():
        if raise_on_missing:
            raise RuntimeError("key file {0} does not exist".format(keypath))
        else:
            return None
    return keypath


def render_template_to_file(template_path, file_path=None, **values):
    rendered = render_template(template_path=template_path, **values)
    return content_to_file(rendered, file_path)


def render_template(template_path, **values):
    with open(template_path) as f:
        template = f.read()
    rendered = jinja2.Template(template).render(**values)
    return rendered


def content_to_file(content, file_path=None):
    if not file_path:
        file_path = tempfile.NamedTemporaryFile(mode='w', delete=False).name
    with open(file_path, 'w') as f:
        f.write(content)
        f.write(os.linesep)
    return file_path


def wait_for_open_port(ip, port, timeout):
    timeout = time.time() + timeout
    is_open = False
    while not is_open:
        if time.time() > timeout:
            break
        time.sleep(1)
        is_open = check_port(ip, port)
    return is_open


def check_port(ip, port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex((ip, port))
    try:
        sock.shutdown(socket.SHUT_RDWR)
        sock.close()
    except socket.error:
        pass
    return result == 0


def create_rest_client(
        manager_ip,
        username=None,
        password=None,
        tenant=None,
        **kwargs):
    return CloudifyClient(
        host=manager_ip,
        username=username or cli_env.get_username(),
        password=password or cli_env.get_password(),
        tenant=tenant or cli_env.get_tenant_name(),
        **kwargs)


def get_plugin_wagon_urls():
    """Get plugin wagon urls from the cloudify-versions repository."""
    plugin_urls_location = (
        'https://raw.githubusercontent.com/cloudify-cosmo/'
        'cloudify-versions/{branch}/packages-urls/plugin-urls.yaml'.format(
                branch=os.environ.get('BRANCH_NAME_CORE', 'master'),
        )
    )
    return yaml.load(requests.get(plugin_urls_location).text)['plugins']


def get_cli_package_urls():
    return yaml.load(_get_package_url('cli-premium-packages.yaml'))


def get_manager_resources_package_url():
    return _get_package_url('manager-single-tar.yaml').strip(os.linesep)


def _get_package_url(filename):
    """Gets the package URL(s) from either GitHub (if GITHUB_USERNAME
    and GITHUB_PASSWORD exists in env) or locally if the cloudify-premium
    repository is checked out under the same folder the cloudify-system-tests
    repo is checked out."""
    branch = os.environ.get('BRANCH_NAME_CORE', 'master')
    auth = None
    if 'GITHUB_USERNAME' in os.environ:
        auth = (os.environ['GITHUB_USERNAME'], os.environ['GITHUB_PASSWORD'])
    if auth:
        url = 'https://raw.githubusercontent.com/cloudify-cosmo/cloudify-premium/{0}/packages-urls/{1}'.format(branch, filename)  # noqa
        r = requests.get(url, auth=auth)
        if r.status_code != 200:
            raise RuntimeError(
                'Error getting {0} URL from {1} '
                '[status_code={2}]: {3}'.format(
                    filename, url, r.status_code, r.text))
        return r.text
    else:
        package_url_file = Path(
            os.path.abspath(os.path.join(
                os.path.dirname(cosmo_tester.__file__),
                '../..',
                os.path.join('cloudify-premium/packages-urls', filename))))
        if not package_url_file.exists():
            raise IOError('File containing {0} URL not '
                          'found: {1}'.format(filename, package_url_file))
        return package_url_file.text()


class YamlPatcher(object):

    pattern = re.compile("(.+)\[(\d+)\]")
    set_pattern = re.compile("(.+)\[(\d+|append)\]")

    def __init__(self, yaml_path, is_json=False, default_flow_style=True):
        self.yaml_path = path(yaml_path)
        self.obj = yaml.load(self.yaml_path.text()) or {}
        self.is_json = is_json
        self.default_flow_style = default_flow_style

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if not exc_type:
            output = json.dumps(self.obj) if self.is_json else yaml.safe_dump(
                self.obj, default_flow_style=self.default_flow_style)
            self.yaml_path.write_text(output)

    def merge_obj(self, obj_prop_path, merged_props):
        obj = self._get_object_by_path(obj_prop_path)
        for key, value in merged_props.items():
            obj[key] = value

    def set_value(self, prop_path, new_value):
        obj, prop_name = self._get_parent_obj_prop_name_by_path(prop_path)
        list_item_match = self.set_pattern.match(prop_name)
        if list_item_match:
            prop_name = list_item_match.group(1)
            obj = obj[prop_name]
            if not isinstance(obj, list):
                raise AssertionError('Cannot set list value for not list item '
                                     'in {0}'.format(prop_path))
            raw_index = list_item_match.group(2)
            if raw_index == 'append':
                obj.append(new_value)
            else:
                obj[int(raw_index)] = new_value
        else:
            obj[prop_name] = new_value

    def append_value(self, prop_path, value):
        obj, prop_name = self._get_parent_obj_prop_name_by_path(prop_path)
        obj[prop_name] = obj[prop_name] + value

    def _split_path(self, path):
        # allow escaping '.' with '\.'
        parts = re.split('(?<![^\\\\]\\\\)\.', path)
        return [p.replace('\.', '.').replace('\\\\', '\\') for p in parts]

    def _get_object_by_path(self, prop_path):
        current = self.obj
        for prop_segment in self._split_path(prop_path):
            match = self.pattern.match(prop_segment)
            if match:
                index = int(match.group(2))
                property_name = match.group(1)
                if property_name not in current:
                    self._raise_illegal(prop_path)
                if type(current[property_name]) != list:
                    self._raise_illegal(prop_path)
                current = current[property_name][index]
            else:
                if prop_segment not in current:
                    current[prop_segment] = {}
                current = current[prop_segment]
        return current

    def delete_property(self, prop_path, raise_if_missing=True):
        obj, prop_name = self._get_parent_obj_prop_name_by_path(prop_path)
        if prop_name in obj:
            obj.pop(prop_name)
        elif raise_if_missing:
            raise KeyError('cannot delete property {0} as its not a key in '
                           'object {1}'.format(prop_name, obj))

    def _get_parent_obj_prop_name_by_path(self, prop_path):
        split = self._split_path(prop_path)
        if len(split) == 1:
            return self.obj, prop_path
        parent_path = '.'.join(p.replace('.', '\.') for p in split[:-1])
        parent_obj = self._get_object_by_path(parent_path)
        prop_name = split[-1]
        return parent_obj, prop_name

    @staticmethod
    def _raise_illegal(prop_path):
        raise RuntimeError('illegal path: {0}'.format(prop_path))


@retrying.retry(stop_max_attempt_number=10, wait_fixed=5000)
def assert_snapshot_created(manager, snapshot_id, attributes):
    url = 'http://{ip}/api/{version}/snapshots/{id}'.format(
        ip=manager.ip_address,
        version=manager.api_version,
        id=snapshot_id)
    headers = {'tenant': attributes.cloudify_tenant}
    auth = (attributes.cloudify_username, attributes.cloudify_password)
    r = requests.get(url, auth=auth, headers=headers)
    assert r.status_code == 200
    snapshot = AttributesDict(r.json())
    assert snapshot.status == 'created', 'Snapshot not in created status'
