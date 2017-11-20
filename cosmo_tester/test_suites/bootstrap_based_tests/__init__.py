import pytest

from cosmo_tester.framework.examples.hello_world import centos_hello_world
from cosmo_tester.framework.util import (
    is_community,
    prepare_and_get_test_tenant,
)

# Importing here so that we fail fast if the required plugin is not available
# rather than waiting for VMs to be deployed first.
try:
    import fabric_plugin  # noqa
except ImportError:
    raise ImportError('cloudify-fabric-plugin must be installed for '
                      'bootstrap tests.')


@pytest.fixture(scope='function')
def hello_worlds(cfy, manager, attributes, ssh_key, tmpdir,
                 logger):
    hellos = get_hello_worlds(cfy, manager, attributes, ssh_key, tmpdir,
                              logger)
    yield hellos
    for hello in hellos:
        hello.cleanup()


def get_hello_worlds(cfy, manager, attributes, ssh_key, tmpdir, logger):
    if is_community():
        tenants = ['default_tenant']
    else:
        tenants = [
            prepare_and_get_test_tenant(name, manager, cfy)
            for name in ('hello1', 'hello2')
        ]
    hellos = []
    for tenant in tenants:
        hello = centos_hello_world(cfy, manager, attributes, ssh_key,
                                   tmpdir, logger, tenant, suffix=tenant)
        hellos.append(hello)
    return hellos
