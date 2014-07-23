#! /bin/bash

test_exit_code()
{
    local container_name=$1
    docker wait $container_name
}

test_kill()
{
    local container_name=$1
    docker rm -f $container_name > /dev/null
}

test_logs()
{
    vagrant docker-logs -f
}

test_start()
{
    __mkdir_if_not_exists $REPORTS_DIR
    __clean_reports_dir
    vagrant up
}

test_run()
{
    local container_name=$1
    test_start
    test_logs
    echo "wait for exit status code"
    local exit_code=$(test_exit_code $container_name)
    echo "removing container"
    test_kill $container_name
    echo "exit_code: $exit_code"
    exit $exit_code
}

setenv()
{
    REPORTS_DIR="xunit-reports"

    # suites
    __add_env_var NOSETESTS_TO_RUN
    __add_suite "cosmo_tester/test_suites/test_blueprints/hello_world_bash_test.py:HelloWorldBashTest.test_hello_world_on_ubuntu"
    #__add_suite 'cosmo_tester/test_suites/test_blueprints/stub_test.py'

    __add_env_var CLOUDIFY_TEST_CONFIG "cloudify-config-simple-provider-on-hp.yaml"
    __add_env_var CLOUDIFY_TEST_HANDLER_MODULE "cosmo_tester.framework.handlers.simple_on_openstack"

    # keystone
    __add_env_var KEYSTONE_PASSWORD
    __add_env_var KEYSTONE_USERNAME
    __add_env_var KEYSTONE_TENANT
    __add_env_var KEYSTONE_AUTH_URL

    # branch names
    __add_env_var BRANCH_NAME "develop"
    __add_env_var BRANCH_NAME_OPENSTACK_PROVIDER "feature/CFY-948-agent-keypair-file-resource-prefix"
    __add_env_var BRANCH_NAME_SYSTEM_TESTS "feature/CFY-959-provider-abstraction"
    __add_env_var BRANCH_NAME_CLI

    # packages
    __add_env_var COMPONENTS_PACKAGE_URL
    __add_env_var CORE_PACKAGE_URL
    __add_env_var UBUNTU_PACKAGE_URL
    __add_env_var CENTOS_PACKAGE_URL
    __add_env_var WINDOWS_PACKAGE_URL
    __add_env_var UI_PACKAGE_URL
}

__add_suite()
{
    local suite=$1
    if [[ -z $NOSETESTS_TO_RUN ]]; then
        export NOSETESTS_TO_RUN=$suite
    else
        export NOSETESTS_TO_RUN="${NOSETESTS_TO_RUN},${suite}"
    fi
}

__add_env_var()
{
    local env_var_name=$1
    local env_var_value=$2
    [[ ! -z $env_var_value ]] && export $env_var_name="$env_var_value"
    export CLOUDIFY_ENVIRONMENT_VARIABLE_NAMES="${CLOUDIFY_ENVIRONMENT_VARIABLE_NAMES}:${env_var_name}"
}

__mkdir_if_not_exists()
{
    local dir_name=$1
    [[ ! -d $dir_name ]] && mkdir $dir_name
}

__clean_reports_dir()
{
    rm -f "${REPORTS_DIR}/*"
}


main()
{
    setenv
    local cmd=$1
    local container_name=$2
    case $cmd in
        kill)
            test_kill $container_name;;
        start)
            test_start;;
        run)
            test_run $container_name;;
        wait)
            test_exit_code $container_name;;
        logs)
            test_logs;;
        *)
            echo "commands.sh: bad command: ${cmd}"; exit 1;;
    esac
}

main $@
