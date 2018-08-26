#!/bin/bash

set -e

TEMP_DIR="/tmp"
port=$(ctx node properties port)
PYTHON_FILE_SERVER_ROOT=${TEMP_DIR}/cloudify-hello-world.$port
PID_FILE="server.pid"

PID=`cat ${PYTHON_FILE_SERVER_ROOT}/${PID_FILE}`

ctx logger info "Shutting down file server. pid = ${PID}"
kill -9 ${PID} || true

ctx logger info "Deleting file server root directory (${PYTHON_FILE_SERVER_ROOT})"
rm -rf ${PYTHON_FILE_SERVER_ROOT}
