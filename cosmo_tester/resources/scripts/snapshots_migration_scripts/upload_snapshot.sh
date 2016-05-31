#!/usr/bin/env bash
set -eax

cd $manager_dir
source $activate_path
cfy snapshots upload -s s -p $snapshot_path
