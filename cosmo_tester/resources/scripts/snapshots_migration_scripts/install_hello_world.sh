#!/usr/bin/env bash
set -eax

cd $manager_dir
source $activate_path
cfy blueprints upload -b test $hello_blueprint_path
cfy deployments create -b test test -i $inputs_path
cfy executions start install -d test
