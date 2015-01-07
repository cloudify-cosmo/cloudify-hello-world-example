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
    build_id = os.environ['QUICK_BUILD_BUILD_ID']
    configuration_id = os.environ['QUICK_BUILD_CONFIGURATION_ID']
    qb_url = os.environ['QUICK_BUILD_URL']
    build_endpoint = '{0}/rest/builds/{1}'.format(qb_url, build_id)
    configuration_endpoint = '{0}/rest/configurations/{1}'\
                             .format(qb_url, configuration_id)
    xml_build = requests.get(build_endpoint, auth=(username, password)).text
    xml_configuration = requests.get(configuration_endpoint,
                                     auth=(username, password)).text
    build = xmltodict.parse(xml_build)
    configuration = xmltodict.parse(xml_configuration)

    configuration_variables = configuration[
        'com.pmease.quickbuild.model.Configuration']['variables'][
        'com.pmease.quickbuild.variable.Variable']
    configuration_variables = {e['name']: e['valueProvider']['value']
                               for e in configuration_variables}

    build_variables = build['com.pmease.quickbuild.model.Build'][
        'variableValues']['entry']
    build_variables = {e['string'][0]: e['string'][1]
                       for e in build_variables}

    variables = configuration_variables
    variables.update(build_variables)

    yaml_dump = yaml.safe_dump(variables)
    with open(variables_path, 'w') as f:
        f.write(yaml_dump)

    logger.info('{0}'.format(build))
    logger.info('{0}'.format(configuration))
    logger.info('Extracted QuickBuild variables:\n{0}'
                .format(yaml_dump))


if __name__ == '__main__':
    main()
