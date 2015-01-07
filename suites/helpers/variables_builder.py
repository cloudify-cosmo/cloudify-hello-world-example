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
    os.environ['QUICK_BUILD_USER'] = 'dank'
    os.environ['QUICK_BUILD_PASSWORD'] = 'dan1324'
    os.environ['QUICK_BUILD_URL'] = 'http://192.168.9.18:8810'
    os.environ['QUICK_BUILD_BUILD_ID'] = '68463'
    os.environ['QUICK_BUILD_CONFIGURATION_ID'] = '26227'
    variables_path = sys.argv[1]
    username = os.environ['QUICK_BUILD_USER']
    password = os.environ['QUICK_BUILD_PASSWORD']
    auth = (username, password)
    qb_url = os.environ['QUICK_BUILD_URL']
    build_id = os.environ['QUICK_BUILD_BUILD_ID']
    configuration_id = os.environ['QUICK_BUILD_CONFIGURATION_ID']

    top_level_configuration_id = '1'
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

    print variables
    yaml_dump = yaml.safe_dump(variables)
    with open(variables_path, 'w') as f:
        f.write(yaml_dump)

    logger.info('Extracted QuickBuild variables:\n{0}'
                .format(yaml_dump))


def _get_parent_configuration_id(configuration_id, qb_url, auth):
    parent_endpoint = ('{0}/rest/configurations/{1}/parent'
                       .format(qb_url, configuration_id))
    return requests.get(parent_endpoint, auth=auth).text.strip()


def _read_configuration_variables(configuration_id, qb_url, auth):
    configuration_endpoint = ('{0}/rest/configurations/{1}'
                              .format(qb_url, configuration_id))
    xml_configuration = requests.get(configuration_endpoint, auth=auth).text
    configuration = xmltodict.parse(xml_configuration) or {}
    configuration = configuration.get(
        'com.pmease.quickbuild.model.Configuration', {}) or {}
    configuration = configuration.get('variables', {}) or {}
    configuration = configuration.get(
        'com.pmease.quickbuild.variable.Variable', {}) or {}
    if not configuration:
        return {}
    return {e['name']: e['valueProvider']['value'] for e in configuration
            if ('name' in e and
                'valueProvider' in e and
                'value' in e['valueProvider'] and
                isinstance(e['valueProvider']['value'], basestring) and
                'vars.get' not in e['valueProvider']['value'])}


def _read_build_variables(build_id, qb_url, auth):
    build_endpoint = '{0}/rest/builds/{1}'.format(qb_url, build_id)
    xml_build = requests.get(build_endpoint, auth=auth).text
    build = xmltodict.parse(xml_build) or {}
    build = build.get('com.pmease.quickbuild.model.Build', {}) or {}
    build = build.get('variableValues', {}) or {}
    build = build.get('entry', {}) or {}
    if not build:
        return {}
    return {e['string'][0]: e['string'][1] for e in build
            if all(['string' in e, len(e['string']) >= 2])}


if __name__ == '__main__':
    main()
