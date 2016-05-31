#!/usr/bin/env bash
set -eax

cd $manager_dir
source $activate_path
cfy snapshots create -s s
cfy snapshots download -s s -o $snapshot_path