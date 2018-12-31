import json
import os
import time

from cloudify_rest_client.exceptions import CloudifyClientError
import pytest

from cosmo_tester.framework.fixtures import (  # noqa
    image_based_manager_without_plugins,
)
from cosmo_tester.framework.util import (
    set_client_tenant,
)


manager = image_based_manager_without_plugins

SMALL_BLUEPRINT_PATH = os.path.abspath(
    os.path.join(
        os.path.dirname(
            __file__), '..', '..', 'resources/blueprints/summary/small.yaml'))
MULTIVM_BLUEPRINT_PATH = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        '..', '..', 'resources/blueprints/summary/multivm.yaml'))
RELATIONS_BLUEPRINT_PATH = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        '..', '..', 'resources/blueprints/summary/withrelations.yaml'))
BLUEPRINTS = {
    'small': SMALL_BLUEPRINT_PATH,
    'multivm': MULTIVM_BLUEPRINT_PATH,
    'relations': RELATIONS_BLUEPRINT_PATH,
}
TENANT_DEPLOYMENT_COUNTS = {
    'default_tenant': {
        'small': 2,
        'multivm': 1,
        'relations': 3,
    },
    'test1': {
        'small': 1,
        'multivm': 3,
        'relations': 2,
    },
    'test2': {
        'small': 3,
        'multivm': 2,
        'relations': 1,
    },
}
SUPPORTED_FIELDS = {
    'blueprints': [
        'tenant_name',
        'visibility',
    ],
    'deployments': [
        'blueprint_id',
        'tenant_name',
        'visibility',
    ],
    'executions': [
        'status',
        'blueprint_id',
        'deployment_id',
        'workflow_id',
        'tenant_name',
        'visibility',
    ],
    'nodes': [
        'deployment_id',
        'tenant_name',
        'visibility',
    ],
    'node_instances': [
        'deployment_id',
        'node_id',
        'state',
        'host_id',
        'tenant_name',
        'visibility',
    ],
}


def _sort_summary(summary, sort_key):
    if isinstance(sort_key, list):
        if len(sort_key) == 1:
            this_sort_key = sort_key[0]
            sort_key = sort_key[0]
        else:
            this_sort_key = sort_key[0]
            sort_key = sort_key[1:]
    else:
        this_sort_key = sort_key

    if isinstance(summary, list):
        summary = [_sort_summary(item, sort_key) for item in summary]
        summary.sort(
            key=lambda x: x[this_sort_key] if isinstance(x, dict) else x
        )
    elif isinstance(summary, dict):
        summary = {
            key: _sort_summary(value, sort_key=sort_key)
            for key, value in summary.items()
        }
    return summary


@pytest.fixture(scope='module')
def prepared_manager(manager, cfy, logger):
    tenants = sorted(TENANT_DEPLOYMENT_COUNTS.keys())

    for tenant in tenants:
        # Sometimes rabbit isn't ready to have new tenants added immediately
        # after startup, so wait for the tenants to be successfully created
        # before we continue (to avoid it erroring when creating a deployment
        # instead)
        for attempt in xrange(30):
            try:
                if tenant != 'default_tenant':
                    manager.client.tenants.create(tenant)
            except CloudifyClientError:
                time.sleep(2)

    for tenant in tenants:
        with set_client_tenant(manager, tenant):
            for blueprint, bp_path in BLUEPRINTS.items():
                manager.client.blueprints.upload(
                    path=bp_path,
                    entity_id=blueprint,
                )

            for bp_name, count in TENANT_DEPLOYMENT_COUNTS[tenant].items():
                for i in xrange(count):
                    deployment_id = bp_name + str(i)
                    manager.client.deployments.create(
                        blueprint_id=bp_name,
                        deployment_id=deployment_id,
                    )
                manager.wait_for_all_executions()
                for i in xrange(count):
                    deployment_id = bp_name + str(i)
                    manager.client.executions.start(
                        deployment_id,
                        'install',
                    )
                manager.wait_for_all_executions()

    yield manager


@pytest.mark.parametrize("summary_type", [
    "blueprints",
    "deployments",
    "executions",
    "nodes",
    "node_instances",
])
def test_bad_field_selected(prepared_manager, summary_type):
    """
        Confirm a helpful error message is returned if a bad field is selected
    """
    summary_endpoint = getattr(prepared_manager.client.summary, summary_type)
    try:
        summary_endpoint.get(_target_field='notafield')
        raise AssertionError(
            'Field notafield should not have been accepted by client for '
            '{endpoint}.'.format(endpoint=summary_type)
        )
    except CloudifyClientError as err:
        components = ['notafield', 'not', 'summary', 'Valid']
        components.extend(SUPPORTED_FIELDS[summary_type])
        if not all(component in str(err) for component in components):
            raise AssertionError(
                '{endpoint} did not provide a helpful error message for '
                'an invalid field. Error message should have stated '
                'which field was invalid, and given a list of fields '
                'which were valid. Expected valid fields were: {valid}. '
                'Returned message was: {message}'.format(
                    endpoint=summary_type,
                    valid=', '.join(
                        SUPPORTED_FIELDS[summary_type]
                    ),
                    message=str(err),
                )
            )


@pytest.mark.parametrize("summary_type", [
    "blueprints",
    "deployments",
    "executions",
    "nodes",
    "node_instances",
])
def test_bad_subfield_selected(prepared_manager, summary_type):
    """
        Confirm a helpful error message is returned if a bad subfield is
        selected
    """
    summary_endpoint = getattr(prepared_manager.client.summary, summary_type)
    try:
        summary_endpoint.get(_target_field='tenant_name',
                             _sub_field='notafield')
        raise AssertionError(
            'Field notafield should not have been accepted by client for '
            '{endpoint}.'.format(endpoint=summary_type)
        )
    except CloudifyClientError as err:
        components = ['notafield', 'not', 'summary', 'Valid']
        components.extend(SUPPORTED_FIELDS[summary_type])
        if not all(component in str(err) for component in components):
            raise AssertionError(
                '{endpoint} did not provide a helpful error message for '
                'an invalid field. Error message should have stated '
                'which field was invalid, and given a list of fields '
                'which were valid. Expected valid fields were: {valid}. '
                'Returned message was: {message}'.format(
                    endpoint=summary_type,
                    valid=', '.join(
                        SUPPORTED_FIELDS[summary_type]
                    ),
                    message=str(err),
                )
            )


def test_basic_summary_blueprints(prepared_manager):
    results = _sort_summary(prepared_manager.client.summary.blueprints.get(
        _target_field='tenant_name',
        _all_tenants=True,
    ).items, sort_key='tenant_name')

    expected = _sort_summary([
        {u'blueprints': 3, u'tenant_name': u'test1'},
        {u'blueprints': 3, u'tenant_name': u'test2'},
        {u'blueprints': 3, u'tenant_name': u'default_tenant'},
    ], sort_key='tenant_name')

    assert results == expected, (
        '{0} != {1}'.format(results, expected)
    )


def test_basic_summary_deployments(prepared_manager):
    results = _sort_summary(prepared_manager.client.summary.deployments.get(
        _target_field='blueprint_id',
    ).items, sort_key='blueprint_id')

    expected = _sort_summary([
        {u'blueprint_id': u'relations', u'deployments': 3},
        {u'blueprint_id': u'small', u'deployments': 2},
        {u'blueprint_id': u'multivm', u'deployments': 1},
    ], sort_key='blueprint_id')

    assert results == expected, (
        '{0} != {1}'.format(results, expected)
    )


def test_basic_summary_executions(prepared_manager):
    results = _sort_summary(prepared_manager.client.summary.executions.get(
        _target_field='status',
    ).items, sort_key='status')

    expected = _sort_summary([
        {u'executions': 12, u'status': u'terminated'},
    ], sort_key='status')

    assert results == expected, (
        '{0} != {1}'.format(results, expected)
    )


def test_basic_summary_nodes(prepared_manager):
    results = _sort_summary(prepared_manager.client.summary.nodes.get(
        _target_field='deployment_id',
    ).items, sort_key='deployment_id')

    expected = _sort_summary([
        {u'deployment_id': u'multivm0', u'nodes': 2},
        {u'deployment_id': u'relations0', u'nodes': 5},
        {u'deployment_id': u'relations1', u'nodes': 5},
        {u'deployment_id': u'relations2', u'nodes': 5},
        {u'deployment_id': u'small0', u'nodes': 1},
        {u'deployment_id': u'small1', u'nodes': 1}
    ], sort_key='deployment_id')

    assert results == expected, (
        '{0} != {1}'.format(results, expected)
    )


def test_basic_summary_node_instances(prepared_manager):
    # Note that this should use host_id to make sure at least one test
    # involves some entries that are NULL in the database, because if the
    # query is changed it could start counting all NULL entries as 1 again
    results = _sort_summary(prepared_manager.client.summary.node_instances.get(
        _target_field='host_id',
    ).items, sort_key='host_id')

    assert results[0] == {u'host_id': None, u'node_instances': 6}

    results_counts = _sort_summary([item['node_instances']
                                    for item in results], sort_key=None)
    expected_counts = _sort_summary([6, 1, 1, 1, 1, 2, 2, 2, 1, 2, 1, 2, 1, 2],
                                    sort_key=None)
    assert expected_counts == results_counts, (
        'Results: {0}\n'
        'Expected host_id None to have 6 results.\n'
        'Expected counts: {1}\n'
        'Instance counts: {2}'.format(results,
                                      expected_counts,
                                      results_counts)
    )


def test_subfield_summary_blueprints(prepared_manager):
    results = _sort_summary(prepared_manager.client.summary.blueprints.get(
        _target_field='tenant_name',
        _sub_field='visibility',
        _all_tenants=True,
    ).items, sort_key=['tenant_name', 'visibility'])

    expected = _sort_summary([
        {
            u'tenant_name': u'default_tenant',
            u'blueprints': 3,
            u'by visibility': [
                {u'blueprints': 3, u'visibility': u'tenant'}
            ]
        },
        {
            u'tenant_name': u'test1',
            u'blueprints': 3,
            u'by visibility': [
                {u'blueprints': 3, u'visibility': u'tenant'}
            ]
        },
        {
            u'tenant_name': u'test2',
            u'blueprints': 3,
            u'by visibility': [
                {u'blueprints': 3, u'visibility': u'tenant'}
            ]
        }
    ], sort_key=['tenant_name', 'visibility'])

    assert results == expected, (
        '{0} != {1}'.format(results, expected)
    )


def test_subfield_summary_deployments(prepared_manager):
    results = _sort_summary(prepared_manager.client.summary.deployments.get(
        _target_field='tenant_name',
        _sub_field='blueprint_id',
        _all_tenants=True,
    ).items, sort_key=['tenant_name', 'blueprint_id'])

    expected = _sort_summary([
        {
            u'by blueprint_id': [
                {u'blueprint_id': u'multivm', u'deployments': 1},
                {u'blueprint_id': u'relations', u'deployments': 3},
                {u'blueprint_id': u'small', u'deployments': 2}
            ],
            u'deployments': 6,
            u'tenant_name': u'default_tenant'
        },
        {
            u'by blueprint_id': [
                {u'blueprint_id': u'multivm', u'deployments': 2},
                {u'blueprint_id': u'relations', u'deployments': 1},
                {u'blueprint_id': u'small', u'deployments': 3}
            ],
            u'deployments': 6,
            u'tenant_name': u'test2'
        },
        {
            u'by blueprint_id': [
                {u'blueprint_id': u'multivm', u'deployments': 3},
                {u'blueprint_id': u'small', u'deployments': 1},
                {u'blueprint_id': u'relations', u'deployments': 2}
            ],
            u'deployments': 6,
            u'tenant_name': u'test1'
        }
    ], sort_key=['tenant_name', 'blueprint_id'])

    assert results == expected, (
        '{0} != {1}'.format(results, expected)
    )


def test_subfield_summary_executions(prepared_manager):
    results = _sort_summary(prepared_manager.client.summary.executions.get(
        _target_field='deployment_id',
        _sub_field='workflow_id',
    ).items, sort_key=['deployment_id', 'workflow_id'])

    expected = _sort_summary([
        {
            u'by workflow_id': [
                {
                    u'executions': 1,
                    u'workflow_id': u'create_deployment_environment'
                },
                {u'executions': 1, u'workflow_id': u'install'}
            ],
            u'deployment_id': u'multivm0',
            u'executions': 2
        },
        {
            u'by workflow_id': [
                {
                    u'executions': 1,
                    u'workflow_id': u'create_deployment_environment'
                },
                {u'executions': 1, u'workflow_id': u'install'}
            ],
            u'deployment_id': u'relations0',
            u'executions': 2
        },
        {
            u'by workflow_id': [
                {
                    u'executions': 1,
                    u'workflow_id': u'create_deployment_environment'
                },
                {u'executions': 1, u'workflow_id': u'install'}
            ],
            u'deployment_id': u'relations1',
            u'executions': 2
        },
        {
            u'by workflow_id': [
                {
                    u'executions': 1,
                    u'workflow_id': u'create_deployment_environment'
                },
                {u'executions': 1, u'workflow_id': u'install'}
            ],
            u'deployment_id': u'relations2',
            u'executions': 2
        },
        {
            u'by workflow_id': [
                {
                    u'executions': 1,
                    u'workflow_id': u'create_deployment_environment'
                },
                {u'executions': 1, u'workflow_id': u'install'}
            ],
            u'deployment_id': u'small0',
            u'executions': 2
        },
        {
            u'by workflow_id': [
                {
                    u'executions': 1,
                    u'workflow_id': u'create_deployment_environment'
                },
                {u'executions': 1, u'workflow_id': u'install'}
            ],
            u'deployment_id': u'small1',
            u'executions': 2
        }
    ], sort_key=['deployment_id', 'workflow_id'])

    assert results == expected, (
        '{0} != {1}'.format(results, expected)
    )


def test_subfield_summary_nodes(prepared_manager):
    results = _sort_summary(prepared_manager.client.summary.nodes.get(
        _target_field='tenant_name',
        _sub_field='deployment_id',
        _all_tenants=True,
    ).items, sort_key=['tenant_name', 'deployment_id'])

    expected = _sort_summary([
        {
            u'by deployment_id': [
                {u'deployment_id': u'multivm0', u'nodes': 2},
                {u'deployment_id': u'multivm1', u'nodes': 2},
                {u'deployment_id': u'multivm2', u'nodes': 2},
                {u'deployment_id': u'relations0', u'nodes': 5},
                {u'deployment_id': u'relations1', u'nodes': 5},
                {u'deployment_id': u'small0', u'nodes': 1}
            ],
            u'nodes': 17,
            u'tenant_name': u'test1'
        },
        {
            u'by deployment_id': [
                {u'deployment_id': u'multivm0', u'nodes': 2},
                {u'deployment_id': u'multivm1', u'nodes': 2},
                {u'deployment_id': u'relations0', u'nodes': 5},
                {u'deployment_id': u'small0', u'nodes': 1},
                {u'deployment_id': u'small1', u'nodes': 1},
                {u'deployment_id': u'small2', u'nodes': 1}
            ],
            u'nodes': 12,
            u'tenant_name': u'test2'
        },
        {
            u'by deployment_id': [
                {u'deployment_id': u'multivm0', u'nodes': 2},
                {u'deployment_id': u'relations0', u'nodes': 5},
                {u'deployment_id': u'relations1', u'nodes': 5},
                {u'deployment_id': u'relations2', u'nodes': 5},
                {u'deployment_id': u'small0', u'nodes': 1},
                {u'deployment_id': u'small1', u'nodes': 1}
            ],
            u'nodes': 19,
            u'tenant_name': u'default_tenant'
        }
    ], sort_key=['tenant_name', 'deployment_id'])

    assert results == expected, (
        '{0} != {1}'.format(results, expected)
    )


def test_subfield_summary_node_instances(prepared_manager):
    results = _sort_summary(prepared_manager.client.summary.node_instances.get(
        _target_field='node_id',
        _sub_field='state',
    ).items, sort_key=['node_id', 'state'])

    expected = _sort_summary([
        {
            u'by state': [
                {u'node_instances': 3, u'state': u'started'}
            ],
            u'node_id': u'fakeappconfig1',
            u'node_instances': 3
        },
        {
            u'by state': [
                {u'node_instances': 3, u'state': u'started'}
            ],
            u'node_id': u'fakeplatformthing1',
            u'node_instances': 3},
        {
            u'by state': [
                {u'node_instances': 4, u'state': u'started'}
            ],
            u'node_id': u'fakevm2',
            u'node_instances': 4
        },
        {
            u'by state': [
                {u'node_instances': 6, u'state': u'started'}
            ],
            u'node_id': u'fakeapp1',
            u'node_instances': 6
        },
        {
            u'by state': [
                {u'node_instances': 9, u'state': u'started'}
            ],
            u'node_id': u'fakevm',
            u'node_instances': 9
        }
    ], sort_key=['node_id', 'state'])

    assert results == expected, (
        '{0} != {1}'.format(results, expected)
    )


def test_basic_summary_paged(prepared_manager):
    results = prepared_manager.client.summary.blueprints.get(
        _target_field='tenant_name',
        _all_tenants=True,
        _size=2,
        _offset=0,
    ).items

    expected = [
        {u'blueprints': 3, u'tenant_name': u'test1'},
        {u'blueprints': 3, u'tenant_name': u'default_tenant'},
    ]

    assert results == expected, (
        '{0} != {1}'.format(results, expected)
    )

    # And the second page, please
    results = prepared_manager.client.summary.blueprints.get(
        _target_field='tenant_name',
        _all_tenants=True,
        _size=2,
        _offset=2,
        _sort='blueprint_id',
    ).items

    expected = [
        {u'blueprints': 3, u'tenant_name': u'test2'},
    ]
    assert results == expected, (
        '{0} != {1}'.format(results, expected)
    )


def _assert_cli_results(results, expected, sort_key):
    assert _sort_summary(
        results, sort_key=sort_key) == _sort_summary(
        expected, sort_key=sort_key)


def test_cli_blueprints_summary(prepared_manager, cfy):
    prepared_manager.use()
    results = json.loads(
        cfy.blueprints.summary('visibility', '--json').stdout
    )
    expected = [{"blueprints": 3, "visibility": "tenant"}]
    _assert_cli_results(results, expected, 'visibility')


def test_cli_blueprints_summary_subfield(prepared_manager, cfy):
    prepared_manager.use()
    results = json.loads(
        cfy.blueprints.summary(
            'tenant_name', 'visibility', '--json', '--all-tenants',
        ).stdout
    )
    # None values are totals
    expected = [
        {u'tenant_name': u'test1', u'blueprints': 3,
         u'visibility': u'tenant'},
        {u'tenant_name': u'test1', u'blueprints': 3,
         u'visibility': None},
        {u'tenant_name': u'test2', u'blueprints': 3,
         u'visibility': u'tenant'},
        {u'tenant_name': u'test2', u'blueprints': 3,
         u'visibility': None},
        {u'tenant_name': u'default_tenant', u'blueprints': 3,
         u'visibility': u'tenant'},
        {u'tenant_name': u'default_tenant', u'blueprints': 3,
         u'visibility': None}
    ]
    _assert_cli_results(results, expected, 'tenant_name')


def test_cli_blueprints_summary_subfield_non_json(prepared_manager, cfy):
    """
        Ensure that 'TOTAL' appears in non-json output (this should be in
        place of the None used in the json output).
    """
    prepared_manager.use()
    results = cfy.blueprints.summary(
        'tenant_name', 'visibility', '--all-tenants',
    ).stdout
    assert 'TOTAL' in results


def test_cli_deployments_summary(prepared_manager, cfy):
    prepared_manager.use()
    results = json.loads(
        cfy.deployments.summary('blueprint_id', '--json').stdout
    )
    expected = [
        {"deployments": 2, "blueprint_id": "small"},
        {"deployments": 1, "blueprint_id": "multivm"},
        {"deployments": 3, "blueprint_id": "relations"}
    ]
    _assert_cli_results(results, expected, 'blueprint_id')


def test_cli_deployments_summary_subfield(prepared_manager, cfy):
    prepared_manager.use()
    results = json.loads(
        cfy.deployments.summary(
            'tenant_name', 'blueprint_id', '--json', '--all-tenants',
        ).stdout
    )
    # None values are totals
    expected = [
        {"tenant_name": "test1", "deployments": 3,
         "blueprint_id": "multivm"},
        {"tenant_name": "test1", "deployments": 1,
         "blueprint_id": "small"},
        {"tenant_name": "test1", "deployments": 2,
         "blueprint_id": "relations"},
        {"tenant_name": "test1", "deployments": 6,
         "blueprint_id": None},
        {"tenant_name": "test2", "deployments": 2,
         "blueprint_id": "multivm"},
        {"tenant_name": "test2", "deployments": 1,
         "blueprint_id": "relations"},
        {"tenant_name": "test2", "deployments": 3,
         "blueprint_id": "small"},
        {"tenant_name": "test2", "deployments": 6,
         "blueprint_id": None},
        {"tenant_name": "default_tenant", "deployments": 1,
         "blueprint_id": "multivm"},
        {"tenant_name": "default_tenant", "deployments": 3,
         "blueprint_id": "relations"},
        {"tenant_name": "default_tenant", "deployments": 2,
         "blueprint_id": "small"},
        {"tenant_name": "default_tenant", "deployments": 6,
         "blueprint_id": None}
    ]
    _assert_cli_results(results, expected, 'blueprint_id')


def test_cli_deployments_summary_subfield_non_json(prepared_manager, cfy):
    """
        Ensure that 'TOTAL' appears in non-json output (this should be in
        place of the None used in the json output).
    """
    prepared_manager.use()
    results = cfy.deployments.summary(
        'tenant_name', 'blueprint_id', '--all-tenants',
    ).stdout
    assert 'TOTAL' in results


def test_cli_executions_summary(prepared_manager, cfy):
    prepared_manager.use()
    results = json.loads(
        cfy.executions.summary('workflow_id', '--json').stdout
    )
    expected = [
        {"workflow_id": "create_deployment_environment", "executions": 6},
        {"workflow_id": "install", "executions": 6}
    ]
    _assert_cli_results(results, expected, 'workflow_id')


def test_cli_executions_summary_subfield(prepared_manager, cfy):
    prepared_manager.use()
    results = json.loads(
        cfy.executions.summary(
            'tenant_name', 'workflow_id', '--json', '--all-tenants',
        ).stdout
    )
    # None values are totals
    expected = [
        {"tenant_name": "test1",
         "workflow_id": "create_deployment_environment", "executions": 6},
        {"tenant_name": "test1",
         "workflow_id": "install", "executions": 6},
        {"tenant_name": "test1",
         "workflow_id": None, "executions": 12},
        {"tenant_name": "test2",
         "workflow_id": "create_deployment_environment", "executions": 6},
        {"tenant_name": "test2",
         "workflow_id": "install", "executions": 6},
        {"tenant_name": "test2",
         "workflow_id": None, "executions": 12},
        {"tenant_name": "default_tenant",
         "workflow_id": "create_deployment_environment", "executions": 6},
        {"tenant_name": "default_tenant",
         "workflow_id": "install", "executions": 6},
        {"tenant_name": "default_tenant",
         "workflow_id": None, "executions": 12}
    ]
    _assert_cli_results(results, expected, 'workflow_id')


def test_cli_executions_summary_subfield_non_json(prepared_manager, cfy):
    """
        Ensure that 'TOTAL' appears in non-json output (this should be in
        place of the None used in the json output).
    """
    prepared_manager.use()
    results = cfy.executions.summary(
        'tenant_name', 'workflow_id', '--all-tenants',
    ).stdout
    assert 'TOTAL' in results


def test_cli_nodes_summary(prepared_manager, cfy):
    prepared_manager.use()
    results = json.loads(
        cfy.nodes.summary('deployment_id', '--json').stdout
    )
    expected = [
        {"deployment_id": "small1", "nodes": 1},
        {"deployment_id": "small0", "nodes": 1},
        {"deployment_id": "relations2", "nodes": 5},
        {"deployment_id": "relations1", "nodes": 5},
        {"deployment_id": "relations0", "nodes": 5},
        {"deployment_id": "multivm0", "nodes": 2}
    ]
    _assert_cli_results(results, expected, 'deployment_id')


def test_cli_nodes_summary_subfield(prepared_manager, cfy):
    prepared_manager.use()
    results = json.loads(
        cfy.nodes.summary(
            'tenant_name', 'deployment_id', '--json', '--all-tenants',
        ).stdout
    )
    # None values are totals
    expected = [
        {"tenant_name": "test1", "deployment_id": "relations1",
         "nodes": 5},
        {"tenant_name": "test1", "deployment_id": "multivm0",
         "nodes": 2},
        {"tenant_name": "test1", "deployment_id": "multivm2",
         "nodes": 2},
        {"tenant_name": "test1", "deployment_id": "multivm1",
         "nodes": 2},
        {"tenant_name": "test1", "deployment_id": "relations0",
         "nodes": 5},
        {"tenant_name": "test1", "deployment_id": "small0",
         "nodes": 1},
        {"tenant_name": "test1", "deployment_id": None,
         "nodes": 17},
        {"tenant_name": "test2", "deployment_id": "small0",
         "nodes": 1},
        {"tenant_name": "test2", "deployment_id": "small1",
         "nodes": 1},
        {"tenant_name": "test2", "deployment_id": "relations0",
         "nodes": 5},
        {"tenant_name": "test2", "deployment_id": "multivm0",
         "nodes": 2},
        {"tenant_name": "test2", "deployment_id": "small2",
         "nodes": 1},
        {"tenant_name": "test2", "deployment_id": "multivm1",
         "nodes": 2},
        {"tenant_name": "test2", "deployment_id": None,
         "nodes": 12},
        {"tenant_name": "default_tenant", "deployment_id": "multivm0",
         "nodes": 2},
        {"tenant_name": "default_tenant", "deployment_id": "relations1",
         "nodes": 5},
        {"tenant_name": "default_tenant", "deployment_id": "small1",
         "nodes": 1},
        {"tenant_name": "default_tenant", "deployment_id": "relations2",
         "nodes": 5},
        {"tenant_name": "default_tenant", "deployment_id": "small0",
         "nodes": 1},
        {"tenant_name": "default_tenant", "deployment_id": "relations0",
         "nodes": 5},
        {"tenant_name": "default_tenant", "deployment_id": None,
         "nodes": 19}
    ]
    _assert_cli_results(results, expected, 'deployment_id')


def test_cli_nodes_summary_subfield_non_json(prepared_manager, cfy):
    """
        Ensure that 'TOTAL' appears in non-json output (this should be in
        place of the None used in the json output).
    """
    prepared_manager.use()
    results = cfy.nodes.summary(
        'tenant_name', 'deployment_id', '--all-tenants',
    ).stdout
    assert 'TOTAL' in results


def test_cli_node_instances_summary(prepared_manager, cfy):
    prepared_manager.use()
    results = json.loads(
        cfy.node_instances.summary('node_id', '--json').stdout
    )
    expected = [
        {"node_id": "fakeapp1", "node_instances": 6},
        {"node_id": "fakevm2", "node_instances": 4},
        {"node_id": "fakeplatformthing1", "node_instances": 3},
        {"node_id": "fakevm", "node_instances": 9},
        {"node_id": "fakeappconfig1", "node_instances": 3}
    ]
    _assert_cli_results(results, expected, 'node_id')


def test_cli_node_instances_summary_subfield(prepared_manager, cfy):
    prepared_manager.use()
    results = json.loads(
        cfy.node_instances.summary(
            'tenant_name', 'node_id', '--json', '--all-tenants',
        ).stdout
    )
    # None values are totals
    expected = [
        {"tenant_name": "test1", "node_id": "fakeapp1",
         "node_instances": 4},
        {"tenant_name": "test1", "node_id": "fakeappconfig1",
         "node_instances": 2},
        {"tenant_name": "test1", "node_id": "fakeplatformthing1",
         "node_instances": 2},
        {"tenant_name": "test1", "node_id": "fakevm",
         "node_instances": 8},
        {"tenant_name": "test1", "node_id": "fakevm2",
         "node_instances": 5},
        {"tenant_name": "test1", "node_id": None,
         "node_instances": 21},
        {"tenant_name": "test2", "node_id": "fakeapp1",
         "node_instances": 2},
        {"tenant_name": "test2", "node_id": "fakeappconfig1",
         "node_instances": 1},
        {"tenant_name": "test2", "node_id": "fakeplatformthing1",
         "node_instances": 1},
        {"tenant_name": "test2", "node_id": "fakevm",
         "node_instances": 7},
        {"tenant_name": "test2", "node_id": "fakevm2",
         "node_instances": 3},
        {"tenant_name": "test2", "node_id": None,
         "node_instances": 14},
        {"tenant_name": "default_tenant", "node_id": "fakeapp1",
         "node_instances": 6},
        {"tenant_name": "default_tenant", "node_id": "fakeappconfig1",
         "node_instances": 3},
        {"tenant_name": "default_tenant", "node_id": "fakeplatformthing1",
         "node_instances": 3},
        {"tenant_name": "default_tenant", "node_id": "fakevm",
         "node_instances": 9},
        {"tenant_name": "default_tenant", "node_id": "fakevm2",
         "node_instances": 4},
        {"tenant_name": "default_tenant", "node_id": None,
         "node_instances": 25}
    ]
    _assert_cli_results(results, expected, 'node_id')


def test_cli_node_instances_summary_subfield_non_json(prepared_manager, cfy):
    """
        Ensure that 'TOTAL' appears in non-json output (this should be in
        place of the None used in the json output).
    """
    prepared_manager.use()
    results = cfy.node_instances.summary(
        'tenant_name', 'node_id', '--all-tenants',
    ).stdout
    assert 'TOTAL' in results
