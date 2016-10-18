########
# Copyright (c) 2016 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import argparse

import requests
import yaml


CLI_PACKAGES_URL_FORMAT = 'https://raw.githubusercontent.com/cloudify-cosmo' \
                          '/cloudify-versions/{0}/packages-urls' \
                          '/cli-packages-blueprint.yaml'


def read_jenkins_parameters(jenkins_parameters_path):
    with open(os.path.expanduser(jenkins_parameters_path)) as f:
        parameters = yaml.safe_load(f)
    return {parameter['key']: parameter['value'] for parameter in parameters}


def read_secrets(secrets_yaml_path):
    with open(secrets_yaml_path, 'r') as f:
        return yaml.load(f)


def read_cli_package_urls(cloudify_versions_branch):
    cli_packages_url = CLI_PACKAGES_URL_FORMAT.format(cloudify_versions_branch)
    cli_packages_raw_yaml = requests.get(cli_packages_url).text
    cli_packages_yaml = yaml.safe_load(cli_packages_raw_yaml) or {}
    return cli_packages_yaml.get('cli_package_urls', {})


def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument('--jenkins-parameters-path', required=True)
    parser.add_argument('--variables-output-path', required=True)
    parser.add_argument('--secrets-file-path', required=True)
    return parser.parse_args()


def main():
    args = parse_arguments()
    jenkins_vars = read_jenkins_parameters(args.jenkins_parameters_path)
    cli_packages_vars = read_cli_package_urls(
        cloudify_versions_branch=jenkins_vars.pop('versions_branch'))
    pass_vars = read_secrets(args.secrets_file_path)
    variables = jenkins_vars
    variables.update(cli_packages_vars)
    variables.update(pass_vars)
    with open(os.path.expanduser(args.variables_output_path), 'w') as f:
        f.write(yaml.safe_dump(variables))

if __name__ == '__main__':
    main()
