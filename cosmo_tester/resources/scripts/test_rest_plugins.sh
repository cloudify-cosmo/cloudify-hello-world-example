#!/bin/bash -e
set -e
source /opt/manager/env/bin/activate
python -c "import plugin.tasks; print 'imported_plugin_tasks'"
python -c "import mock_wagon_plugin; print mock_wagon_plugin.mock_attribute"
