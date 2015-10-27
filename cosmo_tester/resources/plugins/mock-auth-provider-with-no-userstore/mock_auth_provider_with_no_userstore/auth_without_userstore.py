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

from flask import request
from flask_securest.authentication_providers.abstract_authentication_provider\
    import AbstractAuthenticationProvider
from flask_securest.models import User

AUTH_HEADER_NAME = 'Authorization'
BASIC_AUTH_PREFIX = 'Basic'


class AuthorizeUserMyUsername(AbstractAuthenticationProvider):

    def __init__(self):
        self.request_user_id = None

    def _retrieve_request_credentials(self):
        auth_header = request.headers.get(AUTH_HEADER_NAME)
        if not auth_header:
            raise RuntimeError('Request authentication header "{0}" is empty '
                               'or missing'.format(AUTH_HEADER_NAME))

        auth_header = auth_header.replace(BASIC_AUTH_PREFIX + ' ', '', 1)
        try:
            from itsdangerous import base64_decode
            api_key = base64_decode(auth_header)
        except TypeError:
            pass
        else:
            api_key_parts = api_key.split(':')
            self.request_user_id = api_key_parts[0]
            self.request_password = api_key_parts[1]
            if not self.request_user_id or not self.request_password:
                raise RuntimeError('username or password not found on request')

    def authenticate(self, userstore):
        self._retrieve_request_credentials()
        if self.request_user_id != 'my_username':
            raise Exception('authentication of {0} failed'.
                            format(self.request_user_id))

        return User('mockuser', 'mockpass', 'mockemail@mock.com', [],
                    active=True)
