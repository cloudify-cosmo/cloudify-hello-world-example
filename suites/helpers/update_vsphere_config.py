#! /usr/bin/env python
# flake8: NOQA

import sys
import os


def replace_string_in_file(file_name, old_string, new_string):
    with open(file_name, 'r') as f:
        newlines = []
        for line in f.readlines():
            newlines.append(line.replace(old_string, new_string))
    with open(file_name, 'w') as f:
        for line in newlines:
            f.write(line)


def main():
    base_dir = sys.argv[1]
    cloudify_automation_token_place_holder = '{CLOUDIFY_AUTOMATION_TOKEN}'
    cloudify_automation_token = os.environ.get('CLOUDIFY_AUTOMATION_TOKEN')
    vsphere_plugin_token_place_holder = '{VSPHERE_PLUGIN_TOKEN}'
    vsphere_plugin_token = os.environ.get('VSPHERE_PLUGIN_TOKEN')
    plugin_path = base_dir + '/plugin.yaml'
    manager_path = base_dir + '/manager_blueprint/vsphere.yaml'
    replace_string_in_file(plugin_path,
                           cloudify_automation_token_place_holder, cloudify_automation_token)
    replace_string_in_file(manager_path,
                           vsphere_plugin_token_place_holder, vsphere_plugin_token)


if __name__ == '__main__':
    main()
