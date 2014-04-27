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


__author__ = 'dan'

import sys
import os
import re

from path import path
import yaml

from cosmo_tester import resources


def sh_bake(command):
    return command.bake(_out=lambda line: sys.stdout.write(line),
                        _err=lambda line: sys.stderr.write(line))


def get_resource_path(resource_name):
    resources_dir = os.path.dirname(resources.__file__)
    return os.path.join(resources_dir, resource_name)


def get_blueprint_path(blueprint_name):
    resources_dir = os.path.dirname(resources.__file__)
    return os.path.join(resources_dir, 'blueprints', blueprint_name)


def get_yaml_as_dict(yaml_path):
    return yaml.load(path(yaml_path).text())


class YamlPatcher(object):

    pattern = re.compile("(.+)\[(\d+)\]")

    def __init__(self, yaml_path):
        self.yaml_path = path(yaml_path)
        self.obj = yaml.load(self.yaml_path.text())

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if not exc_type:
            self.yaml_path.write_text(yaml.dump(self.obj))

    def merge_obj(self, obj_prop_path, merged_props):
        obj = self._get_object_by_path(obj_prop_path)
        for key, value in merged_props.items():
            obj[key] = value

    def set_value(self, prop_path, new_value):
        obj, prop_name = self._get_parent_obj_prop_name_by_path(prop_path)
        obj[prop_name] = new_value

    def _get_object_by_path(self, prop_path):
        current = self.obj
        for prop_segment in prop_path.split('.'):
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

    def _get_parent_obj_prop_name_by_path(self, prop_path):
        split = prop_path.split('.')
        parent_path = '.'.join(split[:-1])
        parent_obj = self._get_object_by_path(parent_path)
        prop_name = split[-1]
        return parent_obj, prop_name

    def _raise_illegal(self, prop_path):
        raise RuntimeError('illegal path: {0}'.format(prop_path))


class Singleton(type):

    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = \
                super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class CloudifyConfigReader(object):

    def __init__(self, cloudify_config):
        self.config = cloudify_config

    @property
    def management_server_name(self):
        return self.config['compute']['management_server']['instance']['name']

    @property
    def management_server_floating_ip(self):
        return self.config['compute']['management_server']['floating_ip']

    @property
    def management_network_name(self):
        return self.config['networking']['int_network']['name']

    @property
    def management_sub_network_name(self):
        return self.config['networking']['subnet']['name']

    @property
    def management_router_name(self):
        return self.config['networking']['router']['name']

    @property
    def agent_key_path(self):
        return self.config['compute']['agent_servers']['agents_keypair'][
            'auto_generated']['private_key_target_path']

    @property
    def managment_user_name(self):
        return self.config['compute']['management_server'][
            'user_on_management']

    @property
    def management_key_path(self):
        return self.config['compute']['management_server'][
            'management_keypair']['auto_generated']['private_key_target_path']

    @property
    def agent_keypair_name(self):
        return self.config['compute']['agent_servers']['agents_keypair'][
            'name']

    @property
    def management_keypair_name(self):
        return self.config['compute']['management_server'][
            'management_keypair']['name']

    @property
    def external_network_name(self):
        return self.config['networking']['ext_network']['name']

    @property
    def agents_security_group(self):
        return self.config['networking']['agents_security_group']['name']

    @property
    def management_security_group(self):
        return self.config['networking']['management_security_group']['name']
