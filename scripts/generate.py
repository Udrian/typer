import os
from scripts import product, xmler

def parse(parser):
    parser.add_argument('-p', '--projectPath', type=str, required=True,       help="Path to project")
    parser.add_argument(       '--xUnit',                action='store_true', help="Add XUnit Test project")

def createProjectAndSolution(name, args):
    testName = "{}Test".format(name)
    csProjFile = "{}/{}.csproj".format(name, name)
    csTestProjFile = "{}/{}.csproj".format(testName, testName)
    slnFile = "{}.sln".format(name)

    os.system("dotnet new sln --name {}".format(name))
    os.system("dotnet new classlib --name {}".format(name))
    if os.path.exists("{}/Class1.cs".format(name)):
        os.remove("{}/Class1.cs".format(name))
    if args.xUnit:
        testFile = "{}/UnitTest1.cs".format(testName)
        testUsingFile = "{}/Usings.cs".format(testName)
        testUsingFileTemp = "{}_temp".format(testUsingFile)
        testUsingFileExisted = False
        testFileFound = False
        if os.path.exists(testFile):
            testFileFound = True
        if os.path.exists(testUsingFile):
            testUsingFileExisted = True
            os.rename(testUsingFile, testUsingFileTemp)
        os.system("dotnet new xunit --name {}".format(testName))
        os.system("dotnet add {} reference {}".format(csTestProjFile, csProjFile))
        os.remove(testUsingFile)
        if testUsingFileExisted:
            os.rename(testUsingFileTemp, testUsingFile)
        if not testFileFound:
            os.remove(testFile)

        csProjTestXML = xmler.load(csTestProjFile)
        itemGroupTypeOModulesEl = xmler.getOrCreateElementWithAttribute(csProjTestXML, csProjTestXML, "ItemGroup", "Label", "TypeOModules")
        referenceEl = xmler.getOrCreateElementWithAttribute(csProjTestXML, itemGroupTypeOModulesEl, "Reference", "Include", "TypeOCore")
        xmler.createElement(csProjTestXML, referenceEl, "HintPath", "..\{}\$(OutDir)TypeOCore.dll".format(name))
        xmler.save(csProjTestXML, csTestProjFile)

    os.system("dotnet sln {} add {}".format(slnFile, csProjFile))
    if args.xUnit:
        os.system("dotnet sln {} add {}".format(slnFile, csTestProjFile))

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