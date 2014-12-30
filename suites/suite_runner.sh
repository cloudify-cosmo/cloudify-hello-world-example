#!/bin/bash -e

setenv()
{
	# So that we get to see output faster from docker-logs
	export PYTHONUNBUFFERED="true"

	export BRANCH_NAME_CORE=${BRANCH_NAME_CORE='3.2m1'}
	export BRANCH_NAME_PLUGINS=${BRANCH_NAME_PLUGINS='1.2m1'}

	BRANCH_NAME_CLI=${BRANCH_NAME_CLI=${BRANCH_NAME_CORE}}
	BRANCH_NAME_MANAGER_BLUEPRINTS=${BRANCH_NAME_MANAGER_BLUEPRINTS=${BRANCH_NAME_CORE}}
	BRANCH_NAME_SYSTEM_TESTS=${BRANCH_NAME_SYSTEM_TESTS=${BRANCH_NAME_CORE}}

	# vagrant synched folder
	TEST_SUITE_NAME=${TEST_SUITE_NAME='default-suite'}
	BASE_HOST_DIR="/vagrant"
	BASE_CONFIG_DIR="${BASE_HOST_DIR}/configurations"
	REPORT_FILE="${BASE_HOST_DIR}/xunit-reports/${TEST_SUITE_NAME}-report.xml"

	# base dir is the virtualenv directory
	BASE_DIR=$PWD
	SYSTEM_TESTS_DIR="${BASE_DIR}/cloudify-system-tests"

	# export system tests related variables
	export CLOUDIFY_TEST_CONFIG_PATH=${GENERATED_CLOUDIFY_TEST_CONFIG_PATH}
	export CLOUDIFY_TEST_HANDLER_MODULE=${CLOUDIFY_TEST_HANDLER_MODULE='cosmo_tester.framework.handlers.openstack'}
	export BOOTSTRAP_USING_PROVIDERS=${BOOTSTRAP_USING_PROVIDERS}
	export BOOTSTRAP_USING_DOCKER=${BOOTSTRAP_USING_DOCKER=false}

	export WORKFLOW_TASK_RETRIES=${WORKFLOW_TASK_RETRIES=20}
	export CLOUDIFY_AUTOMATION_TOKEN=${CLOUDIFY_AUTOMATION_TOKEN}
	# If handler is vsphere set the manager dir to the plugin's directory
	if [[ "${CLOUDIFY_TEST_HANDLER_MODULE}" = "cosmo_tester.framework.handlers.vsphere" ]]; then
		export MANAGER_BLUEPRINTS_DIR="${BASE_DIR}/cloudify-vsphere-plugin"
    	else
		export MANAGER_BLUEPRINTS_DIR="${BASE_DIR}/cloudify-manager-blueprints"
	fi
}

create_activate_and_cd_virtualenv()
{
	echo "### Creating virtualenv"
	virtualenv env
	source env/bin/activate
	pip install -r ${BASE_HOST_DIR}/requirements.txt
	cd env
}


clone_and_install_system_tests()
{
	echo "### Cloning system tests repository and dependencies"
	clone_and_checkout cloudify-system-tests ${BRANCH_NAME_SYSTEM_TESTS}
	clone_and_checkout cloudify-cli ${BRANCH_NAME_CLI}
	clone_and_checkout cloudify-manager-blueprints ${BRANCH_NAME_MANAGER_BLUEPRINTS}

	clone_and_checkout cloudify-openstack-provider ${BRANCH_NAME_OPENSTACK_PROVIDER}
	clone_and_checkout cloudify-libcloud-provider ${BRANCH_NAME_LIBCLOUD_PROVIDER}
	clone_and_checkout cloudify-vsphere-plugin ${BRANCH_NAME_VSPHERE_PLUGIN} Gigaspaces private

	echo "### Installing system tests dependencies"
	pip install ./cloudify-cli -r cloudify-cli/dev-requirements.txt
	pip install -e ./cloudify-system-tests

	pip install ./cloudify-openstack-provider
	pip install ./cloudify-libcloud-provider
	pip install ./cloudify-vsphere-plugin
}

clone_and_checkout()
{
	local repo_name=$1
	local branch_name=$2
	local organization="cloudify-cosmo"
	local custom_organization=$3
	if [[ -n "$3" ]]
	then
		organization=${custom_organization}
	fi
	echo "### Cloning '${repo_name}' and checking out '${branch_name}' branch from organization '${organization}'"
	if [ "$4" = "private" ]; then
		git clone "https://opencm:${OPENCM_GIT_PWD}@github.com/${organization}/${repo_name}" --depth 1
	else
		git clone "https://github.com/${organization}/${repo_name}" --depth 1
	fi
	pushd ${repo_name}
	# We checkout the branch explicitly and not using the -b flag during clone,
	# because if the branch is missing, it only issues a warning and exits with exit code 0,
	# which is not what we want
	git checkout ${branch_name}
	popd
}

generate_config()
{
	echo "### Generating config file for test suite"
	cp ${ORIGINAL_CLOUDIFY_TEST_CONFIG_PATH} ${GENERATED_CLOUDIFY_TEST_CONFIG_PATH}
	"${BASE_HOST_DIR}/helpers/update_config.py" ${GENERATED_CLOUDIFY_TEST_CONFIG_PATH}
}

run_nose()
{
	echo "### Running nosetests: ${NOSETESTS_TO_RUN}"
	pushd ${SYSTEM_TESTS_DIR}
	set +e
	nosetests ${NOSETESTS_TO_RUN} --verbose --nocapture --nologcapture --with-xunit --xunit-file=${REPORT_FILE}
	NOSE_EXIT_CODE=$?
	if [ ${NOSE_EXIT_CODE} -ne 0 ]; then
		echo "### nose failed [exit_code=${NOSE_EXIT_CODE}]"
		exit ${NOSE_EXIT_CODE}
	fi
	set -e
	popd
}

suite_runner()
{
	echo "### Executing suites_runner.py"
	python "${BASE_HOST_DIR}/suite_runner.py"
}

main()
{
	echo "### Preparing And running Cloudify system tests environment"
	setenv
	create_activate_and_cd_virtualenv
	suite_runner

	clone_and_install_system_tests
	generate_config
	run_nose
}

main
