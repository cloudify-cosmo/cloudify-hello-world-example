#!/bin/bash

set -e

TEMP_DIR="/tmp"
PYTHON_FILE_SERVER_ROOT=${TEMP_DIR}/python-simple-http-webserver

ctx logger info "Shutting down 'python -m SimpleHTTPServer' process"
pkill -9 -f 'python -m SimpleHTTPServer'

ctx logger info "Deleting file server root directory (${PYTHON_FILE_SERVER_ROOT})"
rm -rf ${PYTHON_FILE_SERVER_ROOT}