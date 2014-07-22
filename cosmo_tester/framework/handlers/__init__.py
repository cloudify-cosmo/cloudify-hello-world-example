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


import logging


class BaseCleanupContext(object):

    logger = logging.getLogger('CleanupContext')
    logger.setLevel(logging.DEBUG)

    def __init__(self, context_name, cloudify_config):
        self.context_name = context_name
        self.cloudify_config = cloudify_config

    def cleanup(self):
        pass


class BaseCloudifyConfigReader(object):

    def __init__(self, cloudify_config):
        self.config = cloudify_config


class BaseHandler(object):

    provider = 'base'
    CleanupContext = BaseCleanupContext
    CloudifyConfigReader = BaseCloudifyConfigReader

    @staticmethod
    def make_unique_configuration(patch):
        pass

handler = BaseHandler
