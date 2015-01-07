import os
import sys
import tempfile

import yaml
import requests
import xmltodict


def main():
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
    variables_path = tempfile.mktemp()
    with open(variables_path, 'w') as f:
        f.write(yaml.safe_dump(variables))
    sys.stdout.write(variables_path)

if __name__ == '__main__':
    main()
