#!/bin/bash

path="$(dirname "$0")"

cd $path && git pull && cd -

python3 -m venv $path/.venv
$path/.venv/bin/pip install -q -r $path/requirements.txt
$path/.venv/bin/python $path/typer.py "$@"