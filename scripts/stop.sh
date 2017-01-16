#!/bin/bash

set -e

TEMP_DIR="/tmp"
PYTHON_FILE_SERVER_ROOT=${TEMP_DIR}/python-simple-http-webserver

ctx logger info "Shutting down 'python -m SimpleHTTPServer' process"
pkill -9 -f 'python -m SimpleHTTPServer'

ctx logger info "Deleting all files from hte server "

pushd /tmp
    shopt -s extglob
    rm -rf  -- !(task-*|*.socket)
popd
