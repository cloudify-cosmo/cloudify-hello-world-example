#!/usr/bin/env bash
set -eax

cd $manager_dir
source $activate_path
cfy snapshots create s
cfy snapshots download s -o $snapshot_path