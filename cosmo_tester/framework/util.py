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
import tempfile
import shutil

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


# conceptually taken from the builtin python3 class
class TemporaryDirectory(object):

    def __init__(self, suffix="", prefix='cosmo', dir=None):
        self.name = tempfile.mkdtemp(suffix, prefix, dir)

    def __enter__(self):
        return self.name

    def __exit__(self, exc, value, tb):
        shutil.rmtree(self.name)
