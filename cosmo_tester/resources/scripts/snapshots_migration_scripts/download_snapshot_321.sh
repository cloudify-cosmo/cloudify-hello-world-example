#!/usr/bin/env bash
set -eax

cd $manager_dir
source $activate_path
pip install -e $snapshot_tool_dir
cfy-snapshot32 -o $snapshot_path

