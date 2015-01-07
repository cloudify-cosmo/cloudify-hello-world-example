import os
import sys
import logging

import yaml
import requests
import xmltodict


logging.basicConfig()

logger = logging.getLogger('variables_builder')
logger.setLevel(logging.INFO)


def main():
    variables_path = sys.argv[1]
    username = os.environ['QUICK_BUILD_USER']
    password = os.environ['QUICK_BUILD_PASSWORD']
    auth = (username, password)
    qb_url = os.environ['QUICK_BUILD_URL']
    build_id = os.environ['QUICK_BUILD_BUILD_ID']
    configuration_id = os.environ['QUICK_BUILD_CONFIGURATION_ID']

    top_level_configuration_id = 1
    configuration_ids = [configuration_id]
    while configuration_id != top_level_configuration_id:
        configuration_id = _get_parent_configuration_id(
            configuration_id, qb_url, auth)
        configuration_ids.insert(0, configuration_id)

    variables = {}
    for configuration_id in configuration_ids:
        variables.update(_read_configuration_variables(
            configuration_id, qb_url, auth))
    variables.update(_read_build_variables(build_id, qb_url, auth))

    yaml_dump = yaml.safe_dump(variables)
    with open(variables_path, 'w') as f:
        f.write(yaml_dump)

    logger.info('Extracted QuickBuild variables:\n{0}'
                .format(yaml_dump))


def _get_parent_configuration_id(configuration_id, qb_url, auth):
    parent_endpoint = ('{0}/rest/configurations/{1}/parent'
                       .format(qb_url, configuration_id))
    return requests.get(parent_endpoint, auth=auth).text


def _read_configuration_variables(configuration_id, qb_url, auth):
    configuration_endpoint = ('{0}/rest/configurations/{1}'
                              .format(qb_url, configuration_id))
    xml_configuration = requests.get(configuration_endpoint, auth=auth).text
    configuration = xmltodict.parse(xml_configuration)
    configuration_variables = configuration[
        'com.pmease.quickbuild.model.Configuration']['variables'][
        'com.pmease.quickbuild.variable.Variable']
    return {e['name']: e['valueProvider']['value']
            for e in configuration_variables}


def _read_build_variables(build_id, qb_url, auth):
    build_endpoint = '{0}/rest/builds/{1}'.format(qb_url, build_id)
    xml_build = requests.get(build_endpoint, auth=auth).text
    build = xmltodict.parse(xml_build)
    build_variables = build['com.pmease.quickbuild.model.Build'][
        'variableValues']['entry']
    return {e['string'][0]: e['string'][1] for e in build_variables}


if __name__ == '__main__':
    main()
