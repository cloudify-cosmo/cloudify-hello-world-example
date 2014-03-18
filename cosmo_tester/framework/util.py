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


class YamlPatcher(object):

    def __init__(self, yaml_path):
        self.yaml_path = path(yaml_path)
        self.obj = yaml.load(self.yaml_path.text())

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.yaml_path.write_text(yaml.dump(self.obj))

    def modify_server(self, server_prop_path, new_props):
        


