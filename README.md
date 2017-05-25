[![CircleCI](https://circleci.com/gh/cloudify-examples/cloudify-hello-world-example.svg?style=svg)](https://circleci.com/gh/cloudify-examples/cloudify-hello-world-example)

# Cloudify Hello World Example

This blueprint deploys a python webserver that says "hello world", with a cute Cloudify logo.

## prerequisites

You will need a *Cloudify Manager* running in either AWS, Azure, or Openstack.

If you have not already, set up the [example Cloudify environment](https://github.com/cloudify-examples/cloudify-environment-setup). Installing that blueprint and following all of the configuration instructions will ensure you have all of the prerequisites, including keys, plugins, and secrets.


### Step 1: Install the demo application

In this step, you will run a *Cloudify CLI* command, which uploads the demo application blueprint to the manager, creates a deployment, and starts an install workflow.

When it is finished, you will be able to play with the wine store application.


#### For AWS run:

```shell
$ cfy install \
    https://github.com/cloudify-examples/cloudify-hello-world-example/archive/4.0.1-pre.zip \
    -b hello-world \
    -n aws-blueprint.yaml
```


#### For Azure run:

```shell
$ cfy install \
    https://github.com/cloudify-examples/cloudify-hello-world-example/archive/4.0.1-pre.zip \
    -b hello-world \
    -n azure-blueprint.yaml
```


#### For Openstack run:

```shell
$ cfy install \
    https://github.com/cloudify-examples/cloudify-hello-world-example/archive/4.0.1-pre.zip \
    -b hello-world \
    -n openstack-blueprint.yaml
```


### Step 2: Verify the demo installed and started.

Once the workflow execution is complete, we can view the application endpoint by running: <br>

```shell
$ cfy deployments outputs hello-world
```

You should see an output like this:

```shell
Retrieving outputs for deployment hello-world...
 - "endpoint":
     Description: Web application endpoint
     Value: http://10.239.0.18:8080/
```

Use the URL from the endpoint output and visit that URL in a browser.


### Step 4: Uninstall the demo application

Now run the `uninstall` workflow. This will uninstall the application,
as well as delete all related resources. <br>

```shell
$ cfy uninstall --allow-custom-parameters -p ignore_failure=true hello-world
```
