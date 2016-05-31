#!/usr/bin/env bash

set -ax

curl -I `cat $server_url`

if [ $? -ne 0  ]; then
    exit 0
else
    exit 1
fi

