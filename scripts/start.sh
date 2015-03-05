#!/bin/bash

set -e

TEMP_DIR="/tmp"
PYTHON_FILE_SERVER_ROOT=${TEMP_DIR}/python-simple-http-webserver
PID_FILE="server.pid"

ctx logger info "Starting HTTP server from ${PYTHON_FILE_SERVER_ROOT}"

port=$(ctx node properties port)

cd ${PYTHON_FILE_SERVER_ROOT}
ctx logger info "Starting SimpleHTTPServer"
nohup python -m SimpleHTTPServer ${port} > /dev/null 2>&1 &
echo $! > ${PID_FILE}

ctx logger info "Waiting for server to launch"

STARTED=false
for i in $(seq 1 15)
do
	if wget http://localhost:${port} 2>/dev/null ; then
		ctx logger info "Server is up."
		STARTED=true
    	break
	else
		ctx logger info "Server not up. waiting 1 second."
		sleep 1
	fi	
done
if [ ${STARTED} = false ]; then
	ctx logger error "Failed starting web server in 15 seconds."
	exit 1
fi
