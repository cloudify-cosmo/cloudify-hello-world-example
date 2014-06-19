# **************************************************************************
# * Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
# *
# * Licensed under the Apache License, Version 2.0 (the "License");
# * you may not use this file except in compliance with the License.
# * You may obtain a copy of the License at
# *
# *       http://www.apache.org/licenses/LICENSE-2.0
# *
# * Unless required by applicable law or agreed to in writing, software
# * distributed under the License is distributed on an "AS IS" BASIS,
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.
# ***************************************************************************/

__author__ = 'dank'


from cloudify.decorators import operation


@operation
def create(**_):
    pass


@operation
def configure(**_):
    pass


@operation
def start(**_):
    pass


@operation
def stop(**_):
    pass


@operation
def delete(**_):
    pass


@operation
def get_state(**_):
    return True


@operation
def preconfigure(**_):
    pass


@operation
def postconfigure(**_):
    pass


@operation
def establish(**_):
    pass


@operation
def unlink(**_):
    pass
