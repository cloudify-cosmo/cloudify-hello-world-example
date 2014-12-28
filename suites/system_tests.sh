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
	export BRANCH_NAME_CORE=${BRANCH_NAME_CORE='3.2m1'}
	export BRANCH_NAME_PLUGINS=${BRANCH_NAME_PLUGINS='1.2m1'}
	BRANCH_NAME_OPENSTACK_PROVIDER=${BRANCH_NAME_OPENSTACK_PROVIDER=${BRANCH_NAME_PLUGINS}}
	BRANCH_NAME_LIBCLOUD_PROVIDER=${BRANCH_NAME_LIBCLOUD_PROVIDER=${BRANCH_NAME_PLUGINS}}
	BRANCH_NAME_VSPHERE_PLUGIN=${BRANCH_NAME_VSPHERE_PLUGIN=${BRANCH_NAME_PLUGINS}}
	BRANCH_NAME_CLI=${BRANCH_NAME_CLI=${BRANCH_NAME_CORE}}
	BRANCH_NAME_MANAGER_BLUEPRINTS=${BRANCH_NAME_MANAGER_BLUEPRINTS=${BRANCH_NAME_CORE}}

	# injected by quickbuild
	BRANCH_NAME_SYSTEM_TESTS=${BRANCH_NAME_SYSTEM_TESTS=${BRANCH_NAME_CORE}}
	NOSETESTS_TO_RUN=${NOSETESTS_TO_RUN='cosmo_tester/test_suites'}
	OPENCM_GIT_PWD=${OPENCM_GIT_PWD}

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
	
	BOOTSTRAP_USING_PROVIDERS=${BOOTSTRAP_USING_PROVIDERS=false}
	CLOUDIFY_CONFIG_SUFFIX=$([ "${BOOTSTRAP_USING_PROVIDERS}" == "false" ] && echo "json" || echo "yaml")

	# vagrant synched folder
	SUITE_NAME=${SUITE_NAME='default-suite'}
	BASE_HOST_DIR="/vagrant"
	BASE_CONFIG_DIR="${BASE_HOST_DIR}/configurations"
	REPORT_FILE="${BASE_HOST_DIR}/xunit-reports/${SUITE_NAME}-report.xml"
	CLOUDIFY_TEST_CONFIG=${CLOUDIFY_TEST_CONFIG='cloudify-config-openstack-on-hp.yaml'}
	ORIGINAL_CLOUDIFY_TEST_CONFIG_PATH="${BASE_CONFIG_DIR}/${CLOUDIFY_TEST_CONFIG}"

	# base dir is the virtualenv directory
	BASE_DIR=$PWD
	SYSTEM_TESTS_DIR="${BASE_DIR}/cloudify-system-tests"
	GENERATED_CLOUDIFY_TEST_CONFIG_PATH="${BASE_DIR}/generated-cloudify-config.${CLOUDIFY_CONFIG_SUFFIX}"

	# So that we get to see output faster from docker-logs
	export PYTHONUNBUFFERED="true"

	# export system tests related variables
	export CLOUDIFY_TEST_CONFIG_PATH=${GENERATED_CLOUDIFY_TEST_CONFIG_PATH}
	export CLOUDIFY_TEST_HANDLER_MODULE=${CLOUDIFY_TEST_HANDLER_MODULE='cosmo_tester.framework.handlers.openstack'}
	export BOOTSTRAP_USING_PROVIDERS=${BOOTSTRAP_USING_PROVIDERS}
	export WORKFLOW_TASK_RETRIES=${WORKFLOW_TASK_RETRIES=20}
	export CLOUDIFY_AUTOMATION_TOKEN=${CLOUDIFY_AUTOMATION_TOKEN}
	# If handler is vsphere set the manager dir to the plugin's directory
	if [[ "${CLOUDIFY_TEST_HANDLER_MODULE}" = "cosmo_tester.framework.handlers.vsphere" ]]; then
		export MANAGER_BLUEPRINTS_DIR="${BASE_DIR}/cloudify-vsphere-plugin"
    	else
		export MANAGER_BLUEPRINTS_DIR="${BASE_DIR}/cloudify-manager-blueprints"
	fi
}

clone_and_install_system_tests()
{
	echo "### Cloning system tests repository and dependencies"
	clone_and_checkout cloudify-system-tests ${BRANCH_NAME_SYSTEM_TESTS}
	clone_and_checkout cloudify-cli ${BRANCH_NAME_CLI}
	clone_and_checkout cloudify-openstack-provider ${BRANCH_NAME_OPENSTACK_PROVIDER}
	clone_and_checkout cloudify-libcloud-provider ${BRANCH_NAME_LIBCLOUD_PROVIDER}
	clone_and_checkout cloudify-manager-blueprints ${BRANCH_NAME_MANAGER_BLUEPRINTS}
	clone_and_checkout cloudify-vsphere-plugin ${BRANCH_NAME_VSPHERE_PLUGIN} Gigaspaces private

	echo "### Installing system tests dependencies"
	pip install ./cloudify-cli -r cloudify-cli/dev-requirements.txt
	pip install ./cloudify-openstack-provider
	pip install ./cloudify-libcloud-provider
	pip install ./cloudify-vsphere-plugin
	pip install -e ./cloudify-system-tests
}

clone_and_checkout()
{
	local repo_name=$1
	local branch_name=$2
	local base_repo_url="https://github.com/"
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
		git clone "${base_repo_url}${organization}/${repo_name}" --depth 1
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
	# replace place holders in vsphere repo in order to access private resources
	if [[ "${CLOUDIFY_TEST_HANDLER_MODULE}" = "cosmo_tester.framework.handlers.vsphere" ]]; then
		"${BASE_HOST_DIR}/helpers/update_vsphere_config.py" ${MANAGER_BLUEPRINTS_DIR}
	fi
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

main()
{
	echo "### Preparing And running Cloudify system tests environment"
	create_activate_and_cd_virtualenv
	setenv
	clone_and_install_system_tests
	generate_config
	run_nose
}

main
