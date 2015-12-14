from collections import namedtuple
import os
import yaml
import requests
from requests.auth import HTTPBasicAuth
from lxml import etree
import gspread
from oauth2client.client import SignedJwtAssertionCredentials


SUITES_YAML_FILE = '../suites/suites.yaml'
QUICKBUILD_ADDRESS = 'http://192.168.9.18:8810'

GOOGLE_ACCOUNT = 'cfy_champion@gigaspaces.com'
GOOGLE_SPREADSHEET_TITLE = 'Sprint Test Summary'
GOOGLE_SCOPE = 'https://spreadsheets.google.com/feeds'

COLUMN_TITLES = [
    'Status',
    'Suite',
    'Test Group',
    'Test Name',
    'Descriptor',
    'Owner',
    'Action',
    'Constraints / Notes',
    ]

TEST_RECORD_TO_COLUMN_MAP = {
    'status': 1,
    'suite_name': 2,
    'test_group': 3,
    'test_name': 4,
    'descriptor': 5,
    'comment': 8,
    }


class QuickbuildDriver():

    def __init__(self, server_address, username, password, build_id):
        self.server_address = server_address
        self.auth = HTTPBasicAuth(username, password)
        self.tests_report_url = '{0}/rest/junit/records/tests/{1}/DEFAULT?limit=0'. \
            format(self.server_address, build_id)
        self.report_ui_url = '{0}/build/{1}/junit_report/by_test'. \
            format(QUICKBUILD_ADDRESS, build_id)
        self.report_stats_url = '{0}/rest/junit/buildstats/{1}/DEFAULT'. \
            format(self.server_address, build_id)
        self.tests_results = []
        self.populate_test_results()

    def get_report_id(self):
        test_report_html = requests.get(self.report_ui_url, auth=self.auth)
        test_report_html_as_xml = \
            test_report_html.text[test_report_html.text.find('<html'):]
        tests_report_html_root = etree.fromstring(test_report_html_as_xml)
        report_title = tests_report_html_root[0][0].text
        report_id = report_title[report_title.rfind(' - ')+3:]
        return report_id

    def get_report_success_rate(self):
        build_stats = requests.get(self.report_stats_url, auth=self.auth)
        build_stats_root = etree.fromstring(build_stats.text)
        build_stats_rows = build_stats_root.iterfind(".//row")
        build_success_rate = build_stats_rows.next().get('success_rate')
        build_success_as_percent = int((float(build_success_rate))*100)
        return build_success_as_percent

    def populate_test_results(self):
        tests_report = requests.get(self.tests_report_url, auth=self.auth)
        huge_file_parser = etree.XMLParser(huge_tree=True)
        tests_report_root = etree.fromstring(tests_report.text,
                                             huge_file_parser)
        for row in tests_report_root.iterfind(".//row"):
            # packageName might represent a module as well,
            # depends on what we set in suites.yaml
            row_data = {'test_path': row.get('packageName'),
                        'class': row.get('className'),
                        'test': row.get('testName'),
                        'status': row.get('status'),
                        'diff_status': row.get('diffStatus'),
                        }
            if row_data['status'] == 'ERROR':
                error_type_element = row.find('errorType')
                if error_type_element is not None:
                    error_type = error_type_element.text
                    row_data['error_type'] = error_type
            self.tests_results.append(row_data)

    @staticmethod
    def get_test_module_or_package(test_name):
        test_path = namedtuple('test_path', ['path_type', 'value'])
        trimmed_name = test_name[:test_name.find(' ')] \
            if ' ' in test_name else test_name
        if trimmed_name.endswith('.py'):
            path_type = 'module'
            trimmed_name = trimmed_name[:trimmed_name.rfind('.py')]
        else:
            path_type = 'package'

        trimmed_name = trimmed_name.replace('/', '.')
        return test_path(path_type, trimmed_name)

    def find_matching_results(self, searched_test, searched_suite_name):
        searched_test_path = self.get_test_module_or_package(searched_test)
        matching_test_results = []
        for test_result in self.tests_results:
            # verifying this result line is not outdated
            if test_result['diff_status'] == 'REMOVED':
                continue

            if test_result['test_path'] == 'suites_runner' and \
                    test_result['test'].startswith('TEST-SUITE: {0}'.format(
                        searched_suite_name)):
                matching_test_results.append(test_result)
            found_test_path = test_result['test_path']
            if found_test_path.startswith('<nose'):
                if test_result['class'] == 'suite':
                    # the entire suite failed:
                    found_suite_name = test_result['test'].split('@')[1]
                    if found_suite_name.strip() == searched_suite_name.strip():
                        matching_test_results.append(test_result)
                else:
                    path_parts = searched_test_path.value.split('.')
                    found_test = test_result['test']
                    if found_test.split('>:')[0] in path_parts:
                        # a group of tests failed
                        found_suite_name = test_result['test'].split('@')[1]
                        if found_suite_name.strip() == \
                                searched_suite_name.strip():
                            matching_test_results.append(test_result)
            else:
                if searched_test_path.path_type == 'package':
                    found_test_path = \
                        found_test_path[:found_test_path.rfind('.')]

                if found_test_path == searched_test_path.value:
                    found_suite_name = test_result['test'].split('@')[1]
                    if found_suite_name.strip() == searched_suite_name.strip():
                        matching_test_results.append(test_result)

        return matching_test_results


class GoogleSheetsDriver():

    def __init__(self, google_client_email, google_client_pem):
        with open(google_client_pem, 'r') as pem_file:
            private_key = pem_file.read()

        credentials = SignedJwtAssertionCredentials(
            google_client_email,
            private_key,
            GOOGLE_SCOPE,
            sub=GOOGLE_ACCOUNT)
        gc = gspread.authorize(credentials)
        self.spreadsheet = gc.open(GOOGLE_SPREADSHEET_TITLE)
        self.worksheet = None

    def create_report_worksheet(self, cfy_sprint, report_id, qb_report_ui_url,
                                success_rate):
        new_sheet_name = '{0} {1}'.format(cfy_sprint, report_id)
        try:
            self.worksheet = self.spreadsheet.add_worksheet(
                title=new_sheet_name, rows="100", cols="20")
        except Exception:
            raise Exception('Failed to add worksheet "{0}" to spreadsheet {1}'.
                            format(new_sheet_name, GOOGLE_SPREADSHEET_TITLE))
        summary_status_line = [
            '',
            'quickbuild report: {0}'.format(report_id),
            qb_report_ui_url,
            'success rate: {0}'.format(success_rate)
        ]
        self.worksheet.insert_row(index=1, values=summary_status_line)
        self.worksheet.insert_row(index=2, values=COLUMN_TITLES)

    def populate_report_worksheet(self, analyzed_results):
        row_index = 3
        for record in analyzed_results:
            self.worksheet.insert_row(index=row_index, values=record)
            row_index += 1


class CloudifyTestSuites():
    def __init__(self, suites_yaml_file):
        with open(suites_yaml_file, 'r') as stream:
            self.suites_yaml = yaml.load(stream)

    @staticmethod
    def get_test_status(matching_results):
        test_status = ''
        for result in matching_results:
            if result['status'] in ['ERROR', 'FAILURE']:
                if result.get('error_type') == 'TestSuiteTimeout':
                    test_status = 'Timed out'
                else:
                    test_status = 'Failed'
                break
            elif result['status'] == 'PASS':
                test_status = 'Passed'
            else:
                test_status = "unknown"
        return test_status

    @staticmethod
    def get_descriptor(suite_details, test_group_name, test_name, is_external):
        if 'requires' in suite_details:
            at_value = ','.join(suite_details['requires'])
        else:
            at_value = suite_details['handler_configuration']

        # if external - must run the entire test group again
        if is_external:
            descriptor = '{0}@{1}'.format(test_group_name, at_value)
        else:
            descriptor = '{0}@{1}'.format(test_name, at_value)

        return descriptor


def print_missing(missing):
    print ('\n-------------------------------------------------------\n')
    print 'there are {0} missing tests:\n'.format(len(missing))
    for t in missing:
        print t


def analyze_results(quickbuild_driver, cloudify_test_suites):
    analyzed_results = []
    missing_results = []
    all_test_groups = cloudify_test_suites.suites_yaml['tests']

    for suite in cloudify_test_suites.suites_yaml['test_suites'].iteritems():
        suite_name = suite[0]
        suite_details = suite[1]
        for test_group_name in suite_details['tests']:
            if test_group_name in all_test_groups:
                test_group = all_test_groups[test_group_name]
                for test_name in test_group['tests']:
                    is_external = 'external' in test_group

                    matching_results = quickbuild_driver.find_matching_results(
                        test_name, suite_name)
                    if not matching_results:
                        missing_results.append('test {0} in suite {1}'.format(
                            test_name, suite_name))
                        status = ''
                    else:
                        status = cloudify_test_suites.get_test_status(
                            matching_results)

                    descriptor = cloudify_test_suites.get_descriptor(
                        suite_details, test_group_name, test_name, is_external)

                    test_summary = [
                        status,
                        suite_name,
                        test_group_name,
                        test_name,
                        descriptor,
                        '',
                        '',
                        ''
                    ]
                    analyzed_results.append(test_summary)
            else:
                raise Exception('wrong configuration in suites yaml, '
                                'definition of test group {0} not found'.
                                format(test_group))

    print_missing(missing_results)
    return analyzed_results


def get_mandatory_env_var(env_var_name):
    env_var_value = os.environ.get(env_var_name)
    if not env_var_value:
        raise ValueError('{0} environment variable not set'.
                         format(env_var_name))
    return env_var_value


def main():
    quickbuild_username = get_mandatory_env_var('QUICK_BUILD_USER')
    quickbuild_password = get_mandatory_env_var('QUICK_BUILD_PASSWORD')
    build_id = get_mandatory_env_var('QUICK_BUILD_BUILD_ID')
    cfy_sprint = get_mandatory_env_var('CFY_SPRINT')
    google_client_email = get_mandatory_env_var('GOOGLE_CLIENT_EMAIL')
    google_client_pem = get_mandatory_env_var('GOOGLE_CLIENT_PEM')

    quickbuild_driver = QuickbuildDriver(
        QUICKBUILD_ADDRESS, quickbuild_username, quickbuild_password, build_id)
    success_rate = quickbuild_driver.get_report_success_rate()
    cloudify_test_suites = CloudifyTestSuites(SUITES_YAML_FILE)
    analyzed_results = analyze_results(quickbuild_driver, cloudify_test_suites)
    report_id = quickbuild_driver.get_report_id()
    spreadsheet_driver = GoogleSheetsDriver(google_client_email,
                                            google_client_pem)
    spreadsheet_driver.create_report_worksheet(
        cfy_sprint, report_id, quickbuild_driver.report_ui_url,
        success_rate)
    spreadsheet_driver.populate_report_worksheet(analyzed_results)

if __name__ == '__main__':
    main()
