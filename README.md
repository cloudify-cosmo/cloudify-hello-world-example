Cloudify System Tests
==================

* Master [![Circle CI](https://circleci.com/gh/cloudify-cosmo/cloudify-system-tests/tree/master.svg?&style=shield)](https://circleci.com/gh/cloudify-cosmo/cloudify-system-tests/tree/master)


The system tests framework uses pytest fixtures in order to create the required
resources for testing Cloudify.




## Installation

* Checkout the repository.
* cd cloudify-system-tests
* pip install -e . -r test-requirements.txt -c suites/constraints.txt


## Running tests

For tests running on an OpenStack environment, the framework assumes
a manager image is available in the environment (i.e. cloudify-manager-premium-4.0).

Before running a test, make sure that:
1. Terraform binary is available in path.
2. Source your OpenStack openrc file.

Make sure your openrc file is set to use the OpenStack v2 API.

Run:
```python
pytest -s hello_world_test.py::test_hello_world_on_centos_7
```

## Writing tests

## Test based on Cloudify manager started using an image

```python
from cosmo_tester.framework.fixtures import image_based_manager

manager = image_based_manager


def test(cfy, manager, logger):
    logger.info('Running a cfy command..')
    cfy.status()

    logger.info('Listing blueprints using rest client..')
    blueprints = manager.client.blueprints.list()

```
### Available fixtures

The framework includes the following module scoped pytest fixtures:
* logger - a simple logger to be used in tests.
* module_tmpdir - a temporary directory created per module.
* ssh_key - creates SSH private and public keys on disk.
* attributes - a dict containing the attributes listed in `attributes.yaml` which can be updated in run-time with additional attributes.
* cfy - a baked `cfy` sh command for running Cloudify CLI commands.

The fixtures above are loaded automatically since they are written in a conftest.py file automatically loaded by pytest.


### Cloudify manager fixture

The `cosmo_tester.framework.fixtures` module contains an `image_based_manager` fixtures which starts a manager using an image.
This fixture is currently built to work on OpenStack environments containing a cloudify manager image (its name can be set in the `attributes.yaml` file).
The fixture creates the required infrastructure on OpenStack (router, network etc..) using Terraform.

In a similar manner it is possible to implement a fixture for starting several managers for multi manager tests (HA, snapshots etc..).


## Command line utility

The system tests framework exposes a command line utility for creating and destroying a Cloudify manager.

```bash
# Bootstraps an image based manager
cfy-systests bootstrap

# Destroys a manager started using the cfy-systests bootstrap command
cfy-systests destroy
```

The `cfy-systests` command stores its context in the folder it was invoked from in a folder named `.cfy-systests`.
