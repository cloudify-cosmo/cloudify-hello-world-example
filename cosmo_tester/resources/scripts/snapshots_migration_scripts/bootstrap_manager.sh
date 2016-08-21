#!/usr/bin/env bash
set -eax

cd $manager_dir
virtualenv $venv_dir
source $activate_path

pip install -r $cli_requirements_path
pip install -e $cli_repo_dir
cfy init -r
cfy bootstrap --install-plugins $blueprint_path -i $inputs_path
