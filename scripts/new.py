import os, json
from datetime import date

def parse(parser):
    parser.add_argument('-n',  '--name',         type=str,  required=True,       help="New project name")
    parser.add_argument('-o',  '--output',       type=str,  required=True,       help="Output folder")
    parser.add_argument('-g',  '--git',          type=str,                       help="Existing git link to project")
    parser.add_argument(       '--disableGit',              action='store_true', help="Disables the use of git")
    parser.add_argument(       '--noCommit',                action='store_true', help="Do not ask for git commit input")
    parser.add_argument('-v',  '--version',      type=str,  default="0.1.0",     help="Version of project to set, defaults to 0.1.0")
    parser.add_argument('-d',  '--dependencies', type=str,  default="",          help="List of project dependencies")
    parser.add_argument('-t',  '--type',         type=str,  default="Module",    help="Sets project type, defaults to 'Module'", choices=["Module, Exe"])
    parser.add_argument(       '--xUnit',                action='store_true', help="Add XUnit Test project")

def cloneTyper(args):
    if not args.disableGit:
        if args.git is not None and not os.path.exists(".git"):
            os.system("git clone {} .".format(args.git))
        else:
            os.system("git init")

        if not os.path.exists("typer"):
            os.system("git submodule add https://github.com/Udrian/typer.git")
            commitAndPushMessage("Added submodule typer", args)
    else:
        if not os.path.exists("typer"):
            os.system("git clone https://github.com/Udrian/typer.git")

def addExtraFiles(args):
    if not args.disableGit:
        if not os.path.exists(".gitignore"):
            os.system("dotnet new gitignore")
        else:
            print("Appending to .gitignore")
        with open(".gitignore", "a+") as f:
            f.readlines
            f.writelines([
            "" if f.tell() == 0 else "\n",
            "# TypeO\n",
            "dependency_override\n",
            "*.sln\n",
            "*.csproj"
        ])

    if not os.path.exists("dependency_override"):
        print("Creating dependency_override")
        with open("dependency_override", "w") as f:
            f.write("[\n]")
    
    if not os.path.exists("product"):
        print("Creating product")
        product = {
            "name": args.name,
            "version": args.version,
            "externals": [],
            "dependencies": args.dependencies.split(),
            "type" : args.type
        }
        with open("product", "w") as f:
            json.dump(product, f, ensure_ascii=False, indent=4)

    if not os.path.exists("Readme-TypeO.txt"):
        print("Creating Readme-TypeO.txt")
        with open("Readme-TypeO.txt", "w") as f:
            f.write("""Please distribute this file with the TypeO runtime environment:

TypeO is available from:
http://typeo.typedeaf.com/

This library is distributed under the terms of the zlib license:
http://www.zlib.net/zlib_license.html""")

    if not os.path.exists("ReleaseNotes-{}.txt".format(args.name)):
        print("Creating ReleaseNotes-{}.txt".format(args.name))
        with open("ReleaseNotes-{}.txt".format(args.name), "w") as f:
            f.write(
"""*******************************
******** RELEASE NOTES ********
*******************************

**************************
**** {} - {}/{}-{} ****
**************************

******************
**** Features ****
******************


******************
***** Fixes ******
******************


******************
** Improvements **
******************

""".format(args.version, date.today().day, date.today().month, str(date.today().year)[0:2]))
    
    if not os.path.exists("create_project_files.bat"):
        batLine = "py typer/typer.py generate -p ."
        if args.xUnit:
            batLine = "{} --xUnit".format(batLine)

        print("Creating create_project_files.bat")
        with open("create_project_files.bat", "w") as f:
            f.write(
"""@ECHO OFF
{}""".format(batLine))

def do(args):
    projectPath = "{}/{}".format(args.output, args.name.lower())
    os.makedirs(projectPath, exist_ok=True)
    os.chdir(projectPath)

    cloneTyper(args)
    addExtraFiles(args)

    if not args.disableGit:
        os.system("git add .")
        commitAndPushMessage("Initial commit", args)

    os.system("./create_project_files.bat")
    os.system("py typer/typer.py dependency -p .")

def commitAndPushMessage(default, args):
    if args.noCommit:
        return
    os.system("git status")
    answer = input("Do you want to commit and push?\n")
    if(answer.lower() in ("y", "yes")):
        commitmsg = input("Commit message [{}]".format(default))
        commitmsg = commitmsg or default
        os.system("git commit -m \"{}\"".format(commitmsg))
        os.system("git push")