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

run_system_tests()
{
    ./controller.py
}

main()
{
    setenv
    create_virtualenv_if_needed_and_source
    run_system_tests
}

main
