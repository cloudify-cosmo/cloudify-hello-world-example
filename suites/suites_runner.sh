#! /bin/bash -e

setenv()
{
    echo "Setup environment"
    export PYTHONUNBUFFERED="true"
}

create_virtualenv_if_needed_and_source()
{
    if [[ ! -d ~/system-tests-env ]]; then
        echo "Creating virtualenv"
        virtualenv-2.7 ~/system-tests-env
        source ~/system-tests-env/bin/activate
        pip install -r requirements.txt
        pip install -r wheel-requirements.txt
    else
        echo "Activating virtualenv"
        source ~/system-tests-env/bin/activate
    fi
}

suites_runner()
{
    local variables_yaml_path="$(mktemp -t vars-XXXXXXXX)"
    echo "Writing variables to ${variables_yaml_path}"
    python helpers/variables_builder.py \
        --variables-output-path="${variables_yaml_path}" \
        --jenkins-parameters-path="${EXPORT_PARAMS_FILE}" \
        --secrets-file-path="${SYSTEM_TESTS_SECRETS}" \
        --packages-urls-file-path="${SYSTEM_TESTS_PACKAGES}"
    exec python suites_runner.py "${variables_yaml_path}" "${SYSTEM_TESTS_DESCRIPTOR}"
}

main()
{
    setenv
    create_virtualenv_if_needed_and_source
    suites_runner
}

main
