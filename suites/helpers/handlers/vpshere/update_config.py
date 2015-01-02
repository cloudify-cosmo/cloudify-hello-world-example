import os


def replace_string_in_file(file_name, old_string, new_string):
    with open(file_name, 'r') as f:
        newlines = []
        for line in f.readlines():
            newlines.append(line.replace(old_string, new_string))
    with open(file_name, 'w') as f:
        for line in newlines:
            f.write(line)


def update_config(manager_blueprints_dir):
    cloudify_automation_token_place_holder = '{CLOUDIFY_AUTOMATION_TOKEN}'
    cloudify_automation_token = os.environ.get('CLOUDIFY_AUTOMATION_TOKEN')
    plugin_path = manager_blueprints_dir + '/plugin.yaml'
    replace_string_in_file(plugin_path,
                           cloudify_automation_token_place_holder,
                           cloudify_automation_token)
