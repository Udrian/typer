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
    parser.add_argument(       '--xUnit',                   action='store_true', help="Add XUnit Test project")
    parser.add_argument(       '--clean',                   action='store_true', help="Creates a clean project with no code file template")
    parser.add_argument(       '--dev',                     action='store_true', help="Also create a TypeD Dev module")

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

    CreateFile("dependency_override", "[\n]")
    
    dependencies = args.dependencies.split()
    if len(dependencies) == 0:
        dependencies.append("TypeOCore-0.1.0")
        if args.dev:
            dependencies.append("TypeD-0.1.0;dev")
    
    product = {
        "name": args.name,
        "version": args.version,
        "externals": [],
        "dependencies": dependencies,
        "type" : args.type
    }
    CreateFile("product", json.dumps(product, ensure_ascii=False, indent=4))

    CreateFile("Readme-TypeO.txt",
"""Please distribute this file with the TypeO runtime environment:

TypeO is available from:
http://typeo.typedeaf.com/

This library is distributed under the terms of the zlib license:
http://www.zlib.net/zlib_license.html""")

    CreateFile("ReleaseNotes-{}.txt".format(args.name),
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
    
    batLine = "py typer/typer.py generate -p ."
    if args.xUnit:
        batLine = "{} --xUnit".format(batLine)
    if args.dev:
        batLine = "{} --dev".format(batLine)
    CreateFile("create_project_files.bat",
"""@ECHO OFF
{}""".format(batLine))

def createCodeFiles(args):
    CreateFile("{}/{}Module.cs".format(args.name, args.name),
"""using TypeOEngine.Typedeaf.Core.Engine;
namespace {};

/// <summary>
/// </summary>
public class {}Module : Module<{}ModuleOption>
{{
    /// <inheritdoc/>
    protected override void Initialize() {{ }}

    /// <inheritdoc/>
    protected override void Cleanup() {{ }}

    /// <inheritdoc/>
    protected override void LoadExtensions(TypeO typeO) {{ }}
}}""".format(args.name, args.name, args.name))

    CreateFile("{}/{}ModuleOption.cs".format(args.name, args.name),
"""using TypeOEngine.Typedeaf.Core.Engine;
namespace {};

/// <summary>
/// </summary>
public class {}ModuleOption : ModuleOption
{{
}}""".format(args.name, args.name))

def createCodeTestFiles(args):
    testName = "{}Test".format(args.name)
    CreateFile("{}/{}ModuleTest.cs".format(testName, args.name),
"""using System.Linq;
using TypeOEngine.Typedeaf.Core;
using TypeOEngine.Typedeaf.Core.Engine;
using {};

namespace {};

public class TestGame : Game
{{
    public static string GameName {{ get; set; }} = "test";
    public override void Initialize() {{}}
    public override void Update(double dt) {{ Exit(); }}
    public override void Draw() {{ }}
    public override void Cleanup() {{ }}
}}

public class {}
{{
    [Fact]
    public void StartTest()
    {{
        var typeO = TypeO.Create<TestGame>(TestGame.GameName)
                .LoadModule<{}Module>() as TypeO;
        Assert.NotNull(typeO);
        typeO.Start();
        var module = typeO.Context.Modules.FirstOrDefault(m => m.GetType() == typeof({}Module)) as {}Module;
        Assert.NotNull(module);
        Assert.IsType<{}Module>(module);
        Assert.NotEmpty(typeO.Context.Modules);
    }}
}}""".format(args.name, testName, testName, args.name, args.name, args.name, args.name))

    CreateFile("{}/Usings.cs".format(testName), "global using Xunit;")

def CreateFile(file, content):
    if not os.path.exists(file):
        print("Creating {}".format(file))
        with open(file, "w") as f:
            f.write(content)

def do(args):
    projectPath = "{}/{}".format(args.output, args.name.lower())
    os.makedirs(projectPath, exist_ok=True)
    os.chdir(projectPath)

    cloneTyper(args)
    addExtraFiles(args)

    os.system("create_project_files.bat")
    os.system("py typer/typer.py dependency -p .")

    if not args.clean:
        createCodeFiles(args)
        if args.xUnit:
            createCodeTestFiles(args)

    if not args.disableGit:
        os.system("git add .")
        commitAndPushMessage("Initial commit", args)

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