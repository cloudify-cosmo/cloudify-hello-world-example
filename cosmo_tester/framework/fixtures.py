
import pytest

from .cluster import BootstrapBasedCloudifyCluster, ImageBasedCloudifyCluster


@pytest.fixture(scope='module')
def image_based_manager(
        request, cfy, ssh_key, module_tmpdir, attributes, logger):
    """Creates a cloudify manager from an image in rackspace OpenStack."""
    cluster = ImageBasedCloudifyCluster(cfy, ssh_key, module_tmpdir,
                                        attributes, logger)
    try:
        cluster.create()
        cluster.managers[0].use()
        yield cluster.managers[0]
    finally:
        cluster.destroy()


@pytest.fixture(scope='module')
def bootstrap_based_manager(
        request, cfy, ssh_key, module_tmpdir, attributes, logger):
    """Bootstraps a cloudify manager on a VM in rackspace OpenStack."""
    cluster = BootstrapBasedCloudifyCluster(cfy, ssh_key, module_tmpdir,
                                            attributes, logger)
    try:
        cluster.create()
        cluster.managers[0].use()
        yield cluster.managers[0]
    finally:
        cluster.destroy()
