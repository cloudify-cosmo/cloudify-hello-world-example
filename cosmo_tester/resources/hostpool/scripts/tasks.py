from fabric.api import put
from cloudify import ctx


def copy_key(key_path, save_file_to):
    # this task is run in the hostpool service <-> hostpool service host
    # relationship; `source` is the service, `target` is the service host
    # (which is not interesting here).
    # Note that this runs on the manager, and copies the key from the manager
    # to the service host
    put(key_path, save_file_to)
    ctx.logger.info(
        'copied key from manager {0} to target {1}'
        .format(key_path, save_file_to)
    )
    ctx.source.instance.runtime_properties['key_path'] = save_file_to
