#! /bin/bash -e

setenv()
{
    export PYTHONUNBUFFERED="true"
}

create_virtualenv_if_needed_and_source()
{
    if [[ ! -d tests_status_reporter_venv ]]; then
        virtualenv tests_status_reporter_venv
        source tests_status_reporter_venv/bin/activate
        pip install pip --upgrade
        pip install -r tests_report_requirements.txt
    else
        source tests_status_reporter_venv/bin/activate
    fi
}

main()
{
    setenv
    create_virtualenv_if_needed_and_source
    python helpers/tests_status_reporter.py
}

main
