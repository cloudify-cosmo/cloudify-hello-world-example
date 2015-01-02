#!/bin/bash -e

setenv()
{
	# So that we get to see output faster from docker-logs
	export PYTHONUNBUFFERED="true"

	export BASE_HOST_DIR="/vagrant"
	export WORK_DIR=$PWD

	export BRANCH_NAME_CORE=${BRANCH_NAME_CORE='3.2m1'}
	export BRANCH_NAME_PLUGINS=${BRANCH_NAME_PLUGINS='1.2m1'}
	export BRANCH_NAME_SYSTEM_TESTS=${BRANCH_NAME_SYSTEM_TESTS=${BRANCH_NAME_CORE}}
}

create_activate_and_cd_virtualenv()
{
	echo "### Creating virtualenv"
	virtualenv env
	source env/bin/activate
	pip install -r ${BASE_HOST_DIR}/requirements.txt
	cd env
}

suite_runner()
{
	echo "### Executing suites_runner.py"
	PYTHONPATH=${BASE_HOST_DIR} python "${BASE_HOST_DIR}/suite_runner.py"
}

main()
{
	echo "### Preparing And running Cloudify system tests environment"
	setenv
	create_activate_and_cd_virtualenv
	suite_runner
}

main
