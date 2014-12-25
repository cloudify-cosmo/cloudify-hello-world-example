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
import json

from path import path
import yaml

from cosmo_tester import resources


def sh_bake(command):
    return command.bake(_out=lambda line: sys.stdout.write(line),
                        _err=lambda line: sys.stderr.write(line))


def get_blueprint_path(blueprint_name):
    resources_dir = os.path.dirname(resources.__file__)
    return os.path.join(resources_dir, 'blueprints', blueprint_name)


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
    if env.is_provider_bootstrap:
        # providers also use resources_prefix on the private key file
        keypath = fix_keypath(env, keypath)
    keypath = path(os.path.expanduser(keypath)).abspath()
    if not keypath.exists():
        if raise_on_missing:
            raise RuntimeError("key file {0} does not exist".format(keypath))
        else:
            return None
    return keypath


class YamlPatcher(object):

    pattern = re.compile("(.+)\[(\d+)\]")

    def __init__(self, yaml_path, is_json=False):
        self.yaml_path = path(yaml_path)
        self.obj = yaml.load(self.yaml_path.text())
        self.is_json = is_json

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if not exc_type:
            output = json.dumps(self.obj) if self.is_json else yaml.safe_dump(
                self.obj)
            self.yaml_path.write_text(output)

    def merge_obj(self, obj_prop_path, merged_props):
        obj = self._get_object_by_path(obj_prop_path)
        for key, value in merged_props.items():
            obj[key] = value

    def set_value(self, prop_path, new_value):
        obj, prop_name = self._get_parent_obj_prop_name_by_path(prop_path)
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
