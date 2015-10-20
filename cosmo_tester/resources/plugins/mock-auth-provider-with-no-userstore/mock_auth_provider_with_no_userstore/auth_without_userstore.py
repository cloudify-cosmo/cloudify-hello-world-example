#########
# Copyright (c) 2015 GigaSpaces Technologies Ltd. All rights reserved
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


from flask_securest.authentication_providers.abstract_authentication_provider\
    import AbstractAuthenticationProvider
from flask_securest.models import User


class AuthorizeUser1(AbstractAuthenticationProvider):

    def __init__(self, dummy_param):
        self._dummy_param = dummy_param

    def authenticate(self, auth_info, userstore):
        if not self._dummy_param:
            return ValueError('dummy_param is missing or empty')

        if userstore:
            raise ValueError("userstore specified, but I don't want it")

        if auth_info.user_id != 'admin':
            raise Exception('invalid username, only admin is valid')

        return User('mockuser1', 'mockpass1', 'mockuser1@mock.com', [],
                    active=True)
