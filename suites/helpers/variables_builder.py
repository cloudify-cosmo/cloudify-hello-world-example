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
    qb_url = os.environ['QUICK_BUILD_URL']
    endpoint = '{0}/rest/builds/{1}'.format(qb_url, build_id)
    xml_build = requests.get(endpoint, auth=(username, password)).text
    build = xmltodict.parse(xml_build)
    variables = build['com.pmease.quickbuild.model.Build']['variableValues'][
        'entry']
    variables = {e['string'][0]: e['string'][1]
                 for e in variables}
    yaml_dump = yaml.safe_dump(variables)
    with open(variables_path, 'w') as f:
        f.write(yaml_dump)
    logger.info('Extracted QuickBuild variables:\n{0}'
                .format(yaml_dump))


if __name__ == '__main__':
    main()
