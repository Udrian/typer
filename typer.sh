#!/bin/bash
cd "$(dirname "$0")"

git pull

python3 -m venv ./.venv
./.venv/bin/pip install -q -r requirements.txt
./.venv/bin/python ./typer.py "$@"