#!/usr/bin/env bash

set -eax

cd $manager_dir
source $activate_path
cfy executions start execute_operation -d test -p operation=cloudify.interfaces.lifecycle.stop
