@echo off
pushd "%~dp0"

git pull
pip install -r requirements.txt
py .\typer.py %*

popd