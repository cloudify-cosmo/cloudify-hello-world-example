#!/bin/bash -e

# injected by blueprint
fs_mount_path=${MOUNT_POINT}

ctx logger info "Attempting to write a file in ${fs_mount_path}"
echo "touched" > ${fs_mount_path}/test.txt
ctx logger info "Sccesfully wrote a file in ${fs_mount_path}"