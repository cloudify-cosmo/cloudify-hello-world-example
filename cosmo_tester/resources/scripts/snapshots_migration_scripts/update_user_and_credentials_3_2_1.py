import sys

from cloudify_cli import utils
from cloudify_cli.bootstrap import bootstrap as bs
from cloudify_cli.bootstrap import tasks as bstasks


with utils.update_wd_settings() as settings:
    settings.set_management_key(sys.argv[1])
    print 'Manager key set to path: ' + sys.argv[1]
    provider_context = settings.get_provider_context()
    bs.read_manager_deployment_dump_if_needed(
        provider_context.get('cloudify', {}).get('manager_deployment')
    )
    env = bs.load_env('manager')
    storage = env.storage
    for instance in storage.get_node_instances():
        manager_user = instance.runtime_properties.get(
            bstasks.MANAGER_USER_RUNTIME_PROPERTY
        )
        if manager_user:
            settings.set_management_user(manager_user)
            print 'Manager user set to: ' + manager_user
            break
