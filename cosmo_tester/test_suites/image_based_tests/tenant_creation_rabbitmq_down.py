from cloudify_rest_client.exceptions import CloudifyClientError
from cosmo_tester.framework.fixtures import (  # noqa
    image_based_manager_without_plugins,
)

manager = image_based_manager_without_plugins


def test_tenant_creation_no_rabbitmq(manager):
    with manager.ssh() as fabric:
        fabric.sudo('systemctl stop cloudify-rabbitmq')

    try:
        manager.client.tenants.create('badtenant')
        assert False, (
            'Tenant creation should have raised an exception'
        )
    except CloudifyClientError:
        pass

    with manager.ssh() as fabric:
        fabric.sudo('systemctl start cloudify-rabbitmq')

    # The tenant cannot have been properly created while rabbit was down, so
    # the tenant should not exist
    tenants = manager.client.tenants.list()
    tenant_names = [tenant['name'] for tenant in tenants.items]

    assert tenant_names == ['default_tenant']
