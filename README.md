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

## Running System Tests

The following example demonstrates how to run Cloudify's node cellar example system test on an OpenStack environment:

* Create a new Python 2.7 virtualenv:
```
virtualenv venv
source venv/bin/activate
```

* Install Cloudify's CLI:
```
git clone https://github.com/cloudify-cosmo/cloudify-cli.git
pip install -e cloudify-cli -r cloudify-cli/dev-requirements.txt
```

* Install Cloudify's system tests framework:
```
git clone https://github.com/cloudify-cosmo/cloudify-system-tests.git
pip install -e cloudify-system-tests
```

> ##### Note
  The System Tests installation requirements include `pyOpenSSL==0.14`.<br>
  On Trusty, it requires installing libffi-dev and libssl-dev:<br>
```
apt-get install libffi-dev  
apt-get install libssl-dev  

* Install Cloudify's OpenStack plugin:
```
git clone https://github.com/cloudify-cosmo/cloudify-openstack-plugin.git
pip install -e cloudify-openstack-plugin
```

* Clone the cloudify-manager-blueprints repository (for the framework to be able to bootstrap a Cloudify manager):
```git clone https://github.com/cloudify-cosmo/cloudify-manager-blueprints.git```

* Create an inputs file for your environment (based on cloudify-manager-blueprints/openstack/inputs.yaml.template)

* Copy the sample handler configuration to your work dir (cloudify-system-tests/suites/suites/sample-handler-configuration.yaml).

* Set values for the following keys in the handler configuration file:
  - handler
  - inputs
  - manager_blueprint
  - properties

* Run the test using `nosetests`:
```
export HANDLER_CONFIGURATION=/path/to/sample-handler-configuration.yaml
nosetests -s cosmo_tester/test_suites/test_blueprints/nodecellar_test.py:OpenStackNodeCellarTest
```
