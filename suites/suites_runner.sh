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

        # This is not included in requirements.txt because it requires
        # native extensions that are only installed on the quickbuild agent
        # TODO: consider create two seperate requirements files
        pip install lxml
    else
        source system_tests_controller_venv/bin/activate
    fi
}

suites_runner()
{
    variables_yaml_path=$(mktemp)
    python helpers/variables_builder.py ${variables_yaml_path}
    python suites_runner.py ${variables_yaml_path}
}

main()
{
    setenv
    create_virtualenv_if_needed_and_source
    suites_runner
}

main
