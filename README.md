Cloudify System Tests
==================

This repository contains Cloudify's system tests which in most cases mean that the entire flow of:

1. Bootstrap using CLI.
2. CLI interaction with the Cloudify manager.
2. Blueprint uploading.
3. Deployment creation.
4. Workflows execution.
5. Manager teardown.

In addition, plugins functionality is tested and Cloudify's examples.

# Running System Tests

System tests are written as standard Python unit tests and should be ran using nose.

The following environment variables should be set before running a system test:

```
# Path to a bootstrap configuration file (mandatory)
export CLOUDIFY_TEST_CONFIG_PATH="/some_path/cloudify-config.yaml"

# Cloudify manager IP address (should be usage if test should run with an existing manager)
export CLOUDIFY_TEST_MANAGEMENT_IP="10.0.0.1"

# Specifies whether to cleanup cloud resources on test termination (if set)
export CLOUDIFY_TEST_NO_CLEANUP

# Cloud handler for the test (default: openstack)
export CLOUDIFY_TEST_HANDLER_MODULE="CLOUDIFY_TEST_HANDLER_MODULE"

```

Running a test:

```
# Make sure you have nose installed
pip install nose

# Run a test
nosetests -s <path-to-test-file>
```

