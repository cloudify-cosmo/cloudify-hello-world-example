# Cloudify Hello World Example

[![Circle CI](https://circleci.com/gh/cloudify-cosmo/cloudify-hello-world-example/tree/master.svg?&style=shield)](https://circleci.com/gh/cloudify-cosmo/cloudify-hello-world-example/tree/master)

This repository contains several Hello World Application Examples.

If you're only now starting to work with Cloudify see our [Getting Started Guide](http://docs.getcloudify.org/latest/intro/getting-started/).

## Beginner's Example

These files are beginner's examples:

  * aws.yaml
  * azure.yaml
  * gcp.yaml
  * openstack.yaml

These examples require no pre-configuration (aside from setting up your cloud credentials as secrets).

Run the examples:

For **AWS**:

```shell
cfy install aws.yaml -i aws_region_name=eu-central-1
```

For **Azure**:

```shell
cfy install azure.yaml -i location=eastus -i agent_password=OpenS3sVm3
```

For **GCP**:

```shell
cfy install gcp.yaml region=europe-west1
```

For **Openstack**:

```shell
cfy install openstack.yaml \
    -i region=RegionOne
    -i external_network=external_network \
    -i image=05bb3a46-ca32-4032-bedd-8d7ebd5c8100 \
    -i flavor=4d798e17-3439-42e1-ad22-fb956ec22b54
```

Another **Openstack** example:

```shell
cfy install openstack.yaml \
     -i region=RegionOne \
     -i external_network_name=GATEWAY_NET \
     -i image=e41430f7-9131-495b-927f-e7dc4b8994c8 \
     -i flavor=2
```
