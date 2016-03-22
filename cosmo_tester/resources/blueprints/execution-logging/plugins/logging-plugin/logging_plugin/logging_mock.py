#########
# Copyright (c) 2016 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#  * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  * See the License for the specific language governing permissions and
#  * limitations under the License.

import sys

from cloudify import ctx
from cloudify import exceptions
from cloudify import utils
from cloudify.decorators import operation


@operation
def log(user_cause=False, **_):
    ctx.logger.info('INFO_MESSAGE')
    ctx.logger.debug('DEBUG_MESSAGE')
    causes = []
    if user_cause:
        try:
            raise RuntimeError('ERROR_MESSAGE')
        except RuntimeError:
            _, ex, tb = sys.exc_info()
            causes.append(utils.exception_to_error_cause(ex, tb))
    raise exceptions.NonRecoverableError('ERROR_MESSAGE',
                                         causes=causes)
