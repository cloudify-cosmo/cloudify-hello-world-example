# Cloudify Hello World Example

[![Circle CI](https://circleci.com/gh/cloudify-cosmo/cloudify-hello-world-example/tree/master.svg?&style=shield)](https://circleci.com/gh/cloudify-cosmo/cloudify-hello-world-example/tree/master)

This repository contains Hello World example blueprints, for OpenStack, AWS and existing hosts.

All blueprints start an HTTP server on a VM:

* [ec2-blueprint.yaml](ec2-blueprint.yaml) creates a Linux VM on AWS
* [ec2-windows-blueprint.yaml](ec2-windows-blueprint.yaml) creates a Windows VM on AWS
* [openstack-blueprint.yaml](openstack-blueprint.yaml) creates a Linux VM on OpenStack
* [openstack-windows-blueprint.yaml](openstack-windows-blueprint.yaml) creates a Windows VM on OpenStack
* [openstack-windows-winrm-blueprint.yaml](openstack-windows-winrm-blueprint.yaml) creates a Windows VM on OpenStack
* [singlehost-blueprint.yaml](singlehost-blueprint.yaml) creates no infrastructure (installs the app on an existing VM)
* [no-monitoring-singlehost-blueprint.yaml](no-monitoring-singlehost-blueprint.yaml) similar to `singlehost-blueprint.yaml`,
  however does not include monitoring configuration

If you're only now starting to work with Cloudify see our [Getting Started Guide](http://docs.getcloudify.org/latest/intro/getting-started/).
