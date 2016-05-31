#!/usr/bin/env bash
set -eax

cd $manager_dir
source $activate_path
cfy blueprints upload -b test -p $hello_blueprint_path
cfy deployments create -b test -d test -i $inputs_path
cfy executions start -w install -d test
