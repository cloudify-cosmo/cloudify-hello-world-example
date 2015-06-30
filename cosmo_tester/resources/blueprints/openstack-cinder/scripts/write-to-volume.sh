#!/bin/bash -e

# injected by blueprint
mount_point=${mount_point}

ctx logger info "Attempting to write a file in ${mount_point}"
echo "touched" > ${mount_point}/test.txt
ctx logger info "Successfully wrote a file in ${mount_point}"
