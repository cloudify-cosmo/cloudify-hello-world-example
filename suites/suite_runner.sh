#!/bin/bash -e

setenv()
{
	export PYTHONUNBUFFERED="true"
	export BASE_HOST_DIR="/vagrant"
	export WORK_DIR="${PWD}/env"
}

create_activate_and_cd_virtualenv()
{
	echo "### Creating virtualenv"
	virtualenv env
	source env/bin/activate
	pip install -r ${BASE_HOST_DIR}/requirements.txt
	pip install --no-index --find-links=/wheels -r ${BASE_HOST_DIR}/wheel-requirements.txt
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
