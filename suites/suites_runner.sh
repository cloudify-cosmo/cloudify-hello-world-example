#! /bin/bash -e

setenv()
{
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

suites_runner()
{
    python suites_runner.py $(python helpers/inputs_builder.py)
}

main()
{
    setenv
    create_virtualenv_if_needed_and_source
    suites_runner
}

main
