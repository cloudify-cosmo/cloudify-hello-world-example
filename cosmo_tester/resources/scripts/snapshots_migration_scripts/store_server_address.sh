#!/usr/bin/env bash

set -eax

cd $manager_dir
source $activate_path

server_url=`cfy deployments outputs test | grep Value | sed 's/.*Value: //'`
echo $server_url > $server_url_file_path
