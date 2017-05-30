
import pytest

from .cluster import CloudifyCluster


@pytest.fixture(scope='module')
def image_based_manager(
        request, cfy, ssh_key, module_tmpdir, attributes, logger):
    """Creates a cloudify manager from an image in rackspace OpenStack."""
    cluster = CloudifyCluster.create_image_based(
            cfy, ssh_key, module_tmpdir, attributes, logger)
    cluster.managers[0].use()

    yield cluster.managers[0]

    cluster.destroy()


@pytest.fixture(scope='module')
def bootstrap_based_manager(
        request, cfy, ssh_key, module_tmpdir, attributes, logger):
    """Bootstraps a cloudify manager on a VM in rackspace OpenStack."""
    cluster = CloudifyCluster.create_bootstrap_based(
            cfy, ssh_key, module_tmpdir, attributes, logger)
    cluster.managers[0].use()

    yield cluster.managers[0]

    cluster.destroy()
