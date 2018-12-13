
import pytest

from .test_hosts import TestHosts, BootstrapBasedCloudifyManagers


@pytest.fixture(scope='module')
def image_based_manager(
        request, cfy, ssh_key, module_tmpdir, attributes, logger):
    """Creates a cloudify manager from an image in rackspace OpenStack."""
    hosts = TestHosts(
            cfy, ssh_key, module_tmpdir, attributes, logger, request=request)
    try:
        hosts.create()
        hosts.instances[0].use()
        yield hosts.instances[0]
    finally:
        hosts.destroy()


@pytest.fixture(scope='module')
def image_based_manager_without_plugins(
        request, cfy, ssh_key, module_tmpdir, attributes, logger):
    """Creates a cloudify manager from an image in rackspace OpenStack."""
    """Creates a cloudify manager from an image in rackspace OpenStack."""
    hosts = TestHosts(
            cfy, ssh_key, module_tmpdir, attributes, logger, request=request,
            upload_plugins=False)
    try:
        hosts.create()
        hosts.instances[0].use()
        yield hosts.instances[0]
    finally:
        hosts.destroy()


@pytest.fixture(scope='module')
def bootstrap_based_manager(
        request, cfy, ssh_key, module_tmpdir, attributes, logger):
    """Bootstraps a cloudify manager on a VM in rackspace OpenStack."""
    hosts = BootstrapBasedCloudifyManagers(
            cfy, ssh_key, module_tmpdir, attributes, logger)
    try:
        hosts.create()
        hosts.instances[0].use()
        yield hosts.instances[0]
    finally:
        hosts.destroy()
