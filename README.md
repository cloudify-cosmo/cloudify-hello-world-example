Cloudify System Tests
==================

* Master [![Circle CI](https://circleci.com/gh/cloudify-cosmo/cloudify-system-tests/tree/master.svg?&style=shield)](https://circleci.com/gh/cloudify-cosmo/cloudify-system-tests/tree/master)


The system tests framework uses pytest fixtures in order to create the required
resources for testing Cloudify.


## Installation

### Install system tests framework

* Checkout the repository.
* cd cloudify-system-tests
* pip install -e . -r test-requirements.txt -c suites/constraints.txt

### Install Terraform

Download terraform version 0.9.11 from [here](https://releases.hashicorp.com/terraform/0.9.11), and follow the installation instructions [here](https://www.terraform.io/intro/getting-started/install.html).


## Running tests

For tests running on an OpenStack environment, the framework assumes
a manager image is available in the environment (i.e. cloudify-manager-premium-4.0).

Before running a test, make sure to source your OpenStack openrc file.
The openrc file contains the authentication details for your OpenStack account.
Information about downloading it from an OpenStack environment can be found [here](https://docs.openstack.org/user-guide/common/cli-set-environment-variables-using-openstack-rc.html).

OpenStack openrc file example (my-openrc.sh):
```bash
#!/bin/bash

export OS_AUTH_URL=https://rackspace-api.cloudify.co:5000/v2.0
export OS_TENANT_NAME="idan-tenant"
export OS_PROJECT_NAME="idan-tenant"
export OS_USERNAME="idan"
export OS_PASSWORD="GUESS-ME"
export OS_REGION_NAME="RegionOne"
export OS_IDENTITY_API_VERSION=2
```

Make sure your openrc file is set to use the OpenStack v2 API in both `OS_AUTH_URL` and `OS_IDENTITY_API_VERSION` environment variables.

Source the openrc file:
```bash
source my-openrc.sh
```

Run:
```python
pytest -s cosmo_tester/test_suites/image_based_tests/hello_world_test.py::test_hello_world
```

**Please note it is important to run tests with the `-s` flag as the framework uses `Fabric` which is known to have problems with pytest's output capturing (https://github.com/pytest-dev/pytest/issues/1585).**

### Saving the Cloudify Manager's logs
In order to save the logs of tests, specify the path via an environment variable as follows:

`export CFY_LOGS_PATH_LOCAL=<YOUR-PATH-HERE>`

For example you may use:
```bash
export CFY_LOGS_PATH_LOCAL=~/cfy_logs/
```
which will save the logs to `~/cfy/_logs/` of only the failed tests.
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
