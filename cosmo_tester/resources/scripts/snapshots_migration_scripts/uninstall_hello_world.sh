#!/usr/bin/env bash
set -eax

cd $manager_dir
source $activate_path
cfy executions start uninstall -d test
