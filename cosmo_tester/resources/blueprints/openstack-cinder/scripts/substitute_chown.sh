#!/bin/bash

backed_up_genuine_chown_path=/bin/backed_up_chown
chown_failing_once=/tmp/chown_failing_once

function append_chown_failing_once {
    echo $1 >> ${chown_failing_once}
}

append_chown_failing_once '#!/bin/bash'
append_chown_failing_once ''
append_chown_failing_once 'if [[ "$*" == *'${mount_point}'* ]]; then'  # mount_point is inserted as a value from the blueprint
append_chown_failing_once   'exit $(sudo cp '${backed_up_genuine_chown_path}' /bin/chown && false)'
append_chown_failing_once 'else'
append_chown_failing_once    ${backed_up_genuine_chown_path}' $@'
append_chown_failing_once 'fi'

sudo mv /bin/chown ${backed_up_genuine_chown_path}
sudo cp ${chown_failing_once} /bin/chown
sudo chmod +x /bin/chown
rm ${chown_failing_once}
