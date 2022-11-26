import os, json
from datetime import date
from xml.dom import minidom

def parse(parser):
    parser.add_argument('-n', '--name',         type=str, required=True,    help="Path to project")
    parser.add_argument('-o', '--output',       type=str, required=True,    help="Output folder")
    parser.add_argument('-g', '--git',          type=str, required=False,   help="Git link to project")
    parser.add_argument('-v', '--version',      type=str, default="0.1.0",  help="Version of project to set, defaults to 0.1.0")
    parser.add_argument('-d', '--dependencies', type=str, default="",       help="List of project dependencies")
    parser.add_argument('-t', '--type',         type=str, default="Module", help="Sets project type, defaults to 'Module'", choices=["Module, TypeDModule, Exe"])

def do(args):
    projectPath = "{}/{}".format(args.output, args.name.lower())
    os.makedirs(projectPath, exist_ok=True)
    os.chdir(projectPath)

    if args.git is not None and not os.path.exists(".git"):
        os.system("git clone {} .".format(args.git))
    else:
        os.system("git init")

    if not os.path.exists("typer"):
        os.system("git submodule add https://github.com/Udrian/typer.git")
        commitAndPushMessage("Added submodule typer")


    with open(".gitignore", "a+") as f:
        f.writelines([
        "" if f.tell() == 0 else "\n",
        "# TypeO\n",
        "dependency_override"
    ])

    if not os.path.exists("dependency_override"):
        with open("dependency_override", "w") as f:
            f.write("[\n]")
    
    if not os.path.exists("product"):
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
        with open("Readme-TypeO.txt", "w") as f:
            f.write("""Please distribute this file with the TypeO runtime environment:

TypeO is available from:
http://typeo.typedeaf.com/

This library is distributed under the terms of the zlib license:
http://www.zlib.net/zlib_license.html""")

    if not os.path.exists("ReleaseNotes-{}.txt".format(args.name)):
        with open("ReleaseNotes-{}.txt".format(args.name), "w") as f:
            f.write("""*******************************
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

    os.system("dotnet new sln --name {}".format(args.name))
    os.system("dotnet new classlib --name {}".format(args.name))
    os.system("dotnet new xunit --name {}Test".format(args.name))

    os.system("dotnet sln {}.sln add {}/{}.csproj".format(args.name, args.name, args.name))
    os.system("dotnet sln {}.sln add {}Test/{}Test.csproj".format(args.name, args.name, args.name))

    os.system("py typer/typer.py dependency -p .")
    
    csProjXML = minidom.parse("{}/{}.csproj".format(args.name, args.name))
    target = csProjXML.createElement("Target")
    target.setAttribute("Name", "PreBuild")
    target.setAttribute("BeforeTargets", "PreBuildEvent")
    target.setAttribute("Condition", "'$(OS)' == 'Windows_NT'")
    exec = csProjXML.createElement("Exec")
    exec.setAttribute("Command", "cmd /c &quot;$(ProjectDir)../typer/typer.py dependency -p $(ProjectDir)../&quot;")
    target.appendChild(exec)
    csProjXML.childNodes[0].appendChild(target)

    with open("{}/{}.csproj".format(args.name, args.name), "w") as fs:
        dom_string = csProjXML.childNodes[0].toprettyxml()
        dom_string = '\n'.join([s for s in dom_string.splitlines() if s.strip()])
        fs.write(dom_string)
        fs.close()

    os.system("git add .")
    commitAndPushMessage("Initial commit")

def commitAndPushMessage(default):
    os.system("git status")
    answer = input("Do you want to commit and push?\n")
    if(answer.lower() in ("y", "yes")):
        commitmsg = input("Commit message [{}]".format(default))
        commitmsg = commitmsg or default
        os.system("git commit -m \"{}\"".format(commitmsg))
        os.system("git push")