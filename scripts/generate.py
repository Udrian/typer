import os
from scripts import product, xmler

def parse(parser):
    parser.add_argument('-p', '--projectPath', type=str, required=True,       help="Path to project")
    parser.add_argument(       '--xUnit',                action='store_true', help="Add XUnit Test project")

def createProjectAndSolution(name, args):
    os.system("dotnet new sln --name {}".format(name))
    os.system("dotnet new classlib --name {}".format(name))
    if os.path.exists("{}/Class1.cs".format(name)):
        os.remove("{}/Class1.cs".format(name))
    if args.xUnit:
        os.system("dotnet new xunit --name {}Test".format(name))

    os.system("dotnet sln {}.sln add {}/{}.csproj".format(name, name, name))
    if args.xUnit:
        os.system("dotnet sln {}.sln add {}Test/{}Test.csproj".format(name, name, name))

def addPreBuildEvents(csProjXML):
    target = xmler.getOrCreateElementWithAttributes(csProjXML, csProjXML, "Target",[
        {"name": "Name",          "value": "PreBuild"},
        {"name": "BeforeTargets", "value": "PreBuildEvent"},
        {"name": "Condition",     "value": "'$(OS)' == 'Windows_NT'"}
    ])
    xmler.getOrCreateElementWithAttribute(csProjXML, target, "Exec", "Command", "cmd /c &quot;$(ProjectDir)../typer/typer.py dependency -p $(ProjectDir)../&quot;")
    xmler.add(csProjXML, target)

def do(args):
    name = product.getName(args.projectPath)
    csPath = "{}/{}/{}.csproj".format(args.projectPath, name, name)
    os.chdir(args.projectPath)
    createProjectAndSolution(name, args)

    csProjXML = xmler.load(csPath)
    addPreBuildEvents(csProjXML)
    xmler.save(csProjXML, csPath)