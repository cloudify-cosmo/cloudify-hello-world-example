#!/bin/bash -e

create_activate_and_cd_virtualenv()
{
	echo "### Creating virtualenv"
	virtualenv env
	source env/bin/activate
	cd env
}

setenv()
{
	# injected by quickbuild
	BRANCH_NAME=${BRANCH_NAME='develop'}
	BRANCH_NAME_OPENSTACK_PROVIDER=${BRANCH_NAME_OPENSTACK_PROVIDER=$BRANCH_NAME}
	BRANCH_NAME_CLI=${BRANCH_NAME_CLI=$BRANCH_NAME}
	BRANCH_NAME_SYSTEM_TESTS=${BRANCH_NAME_SYSTEM_TESTS=$BRANCH_NAME}
	NOSETESTS_TO_RUN=${NOSETESTS_TO_RUN='cosmo_tester/test_suites'}

	# for documentation purposes, injected by quickbuild, used by `update_config.py`
	# KEYSTONE_PASSWORD=
    # KEYSTONE_USERNAME=
    # KEYSTONE_TENTANT=
   	# KEYSTONE_AUTH_URL=
	# RESOURCE_PREFIX=
	# COMPONENTS_PACKAGE_URL=
	# CORE_PACKAGE_URL=
	# UBUNTU_PACKAGE_URL=
	# CENTOS_PACKAGE_URL=
	# WINDOWS_PACKAGE_URL=
	# UI_PACKAGE_URL=

	# vagrant synched folder
	BASE_HOST_DIR="/vagrant"
	REPORT_FILE="${BASE_HOST_DIR}/xunit-reports/${RESOURCE_PREFIX}report.xml"
	BASE_CLOUDIFY_CONFIG="${BASE_HOST_DIR}/cloudify-config-hp-paid-system-tests-tenant.yaml"

	# for documenation purposes, these are set by `run_flake8` and `run_nose`
	FLAKE8_EXIT_CODE=
	NOSE_EXIT_CODE=

	# base dir is the virtualenv directory
	BASE_DIR=$PWD
	SYSTEM_TESTS_DIR="${BASE_DIR}/cloudify-system-tests"
	GENERATED_CLOUDIFY_CONFIG="${BASE_DIR}/generated-cloudify-config-hp-paid-system-tests-tenant.yaml"

	# So that we get to see output faster from docker-logs
	export PYTHONUNBUFFERED="true"

	# export config location for system tests
	export CLOUDIFY_TEST_CONFIG_PATH=$GENERATED_CLOUDIFY_CONFIG
}

clone_and_install_system_tests()
{
	echo "### Cloning system tests repository and dependencies"
	clone_and_checkout cloudify-system-tests $BRANCH_NAME_SYSTEM_TESTS
	clone_and_checkout cloudify-cli $BRANCH_NAME_CLI
	clone_and_checkout cloudify-openstack-provider $BRANCH_NAME_OPENSTACK_PROVIDER

	echo "### Installing system tests dependencies"
	pip install ./cloudify-cli -r cloudify-cli/dev-requirements.txt
	pip install ./cloudify-openstack-provider
	pip install -e ./cloudify-system-tests
	pip install flake8
}

clone_and_checkout()
{
	local repo_name=$1
	local branch_name=$2
	echo "### Cloning '${repo_name}' and checking out '${branch_name}' branch"
	git clone "https://github.com/cloudify-cosmo/${repo_name}" --depth 1
	pushd $repo_name
	# We checkout the branch explicitly and not using the -b flag during clone,
	# because if the branch is missing, it only issues a warning and exits with exit code 0,
	# which is not what we want
	git checkout $branch_name
	popd
}

generate_config()
{
	echo "### Generating config file for test suite"
	cp $BASE_CLOUDIFY_CONFIG $GENERATED_CLOUDIFY_CONFIG
	/vagrant/update_config.py $GENERATED_CLOUDIFY_CONFIG
}

run_flake8()
{
	echo "### Running flake8"
	set +e
	flake8 $SYSTEM_TESTS_DIR
	FLAKE8_EXIT_CODE=$?
	set -e
}

run_nose()
{
	echo "### Running nosetests: ${NOSETESTS_TO_RUN}"
	pushd $SYSTEM_TESTS_DIR
	set +e
	nosetests $NOSETESTS_TO_RUN --verbose --nocapture --nologcapture --with-xunit --xunit-file=$REPORT_FILE
	NOSE_EXIT_CODE=$?
	set -e
	popd
}

check_results()
{
	if [ $NOSE_EXIT_CODE -ne 0 ]; then
		echo "### nose failed [exit_code=${NOSE_EXIT_CODE}]"
		exit $NOSE_EXIT_CODE
	elif [ $FLAKE8_EXIT_CODE -ne 0 ]; then
		echo "### flake8 failed [exit_code=${FLAKE8_EXIT_CODE}]"
		exit $FLAKE8_EXIT_CODE
	fi
}

main()
{
	echo "### Preparing And running Cloudify system tests environment"
	create_activate_and_cd_virtualenv
	setenv
	clone_and_install_system_tests
	generate_config
	run_flake8
	run_nose
	check_results
}

main
