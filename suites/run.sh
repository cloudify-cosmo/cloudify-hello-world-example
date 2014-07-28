#! /bin/bash -e

setenv()
{
    # So that we get to see output faster from docker-logs
    export PYTHONUNBUFFERED="true"
}

create_virtualenv_if_needed_and_source()
{
    if [[ ! -d system_tests_controller_venv ]]; then
        virtualenv system_tests_controller_venv
        source system_tests_controller_venv/bin/activate
        pip install pip --upgrade
        pip install -r requirements.txt
    else
        source system_tests_controller_venv/bin/activate
    fi
}

builds_suites_json()
{
    local suites_json_path=$(./suites_builder.py)
    export TEST_SUITES_PATH=$suites_json_path
}

run_system_tests()
{
    ./suites_runner.py
}

main()
{
    setenv
    create_virtualenv_if_needed_and_source
    builds_suites_json
    run_system_tests
}

main
