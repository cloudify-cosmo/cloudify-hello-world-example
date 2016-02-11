import os
import argparse

import requests
import yaml

import password_store

SYSTEM_TESTS_PASSWORD_STORE_REPO = 'system_tests_password_store_repo'
CLI_PACKAGES_URL_FORMAT = 'https://raw.githubusercontent.com/cloudify-cosmo' \
                          '/cloudify-packager/{0}/common' \
                          '/cli-packages-blueprint.yaml'


def read_jenkins_parameters(jenkins_parameters_path):
    with open(os.path.expanduser(jenkins_parameters_path)) as f:
        parameters = yaml.safe_load(f)
    return {parameter['key']: parameter['value'] for parameter in parameters}


def read_cli_package_urls(cloudify_packager_branch):
    cli_packages_url = CLI_PACKAGES_URL_FORMAT.format(cloudify_packager_branch)
    cli_packages_raw_yaml = requests.get(cli_packages_url).text
    cli_packages_yaml = yaml.safe_load(cli_packages_raw_yaml) or {}
    return cli_packages_yaml.get('cli_package_urls', {})


def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument('--gpg-secret-key-path', required=True)
    parser.add_argument('--jenkins-parameters-path', required=True)
    parser.add_argument('--variables-output-path', required=True)
    return parser.parse_args()


def main():
    args = parse_arguments()
    jenkins_vars = read_jenkins_parameters(args.jenkins_parameters_path)
    cli_packages_vars = read_cli_package_urls(
        cloudify_packager_branch=jenkins_vars.pop('packager_branch'))
    pass_vars = password_store.read_pass(
        gpg_secret_key_path=args.gpg_secret_key_path,
        password_store_repo=jenkins_vars.pop(SYSTEM_TESTS_PASSWORD_STORE_REPO))
    variables = jenkins_vars
    variables.update(cli_packages_vars)
    variables.update(pass_vars)
    with open(os.path.expanduser(args.variables_output_path), 'w') as f:
        f.write(yaml.safe_dump(variables))


if __name__ == '__main__':
    main()
