@echo off
pushd "%~dp0"

git pull
pip install -q -r requirements.txt
py .\typer.py %*

popd