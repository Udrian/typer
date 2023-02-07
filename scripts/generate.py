import os
from scripts import product, xmler

def parse(parser):
    parser.add_argument('-p', '--projectPath', type=str, required=True,       help="Path to project")

def createProjectAndSolution(project):
    csProjFile = "{}/{}.csproj".format(project.name, project.name)
    csTestProjFile = "{}/{}.csproj".format(project.testName, project.testName)
    csTypeDProjFile = "{}/{}.csproj".format(project.devModuleName, project.devModuleName)
    slnFile = "{}.sln".format(project.name)

    os.system("dotnet new sln --name {}".format(project.name))
    os.system("dotnet new classlib --name {}".format(project.name))
    if os.path.exists("{}/Class1.cs".format(project.name)):
        os.remove("{}/Class1.cs".format(project.name))
    if project.haveDevModule:
        os.system("dotnet new wpflib --name {}".format(project.devModuleName))
        if os.path.exists("{}/Class1.cs".format(project.devModuleName)):
            os.remove("{}/Class1.cs".format(project.devModuleName))
        os.system("dotnet add {} reference {}".format(csTypeDProjFile, csProjFile))
    
    if project.haveTest:
        testFile = "{}/UnitTest1.cs".format(project.testName)
        testUsingFile = "{}/Usings.cs".format(project.testName)
        testUsingFileTemp = "{}_temp".format(testUsingFile)
        testUsingFileExisted = False
        testFileFound = False
        if os.path.exists(testFile):
            testFileFound = True
        if os.path.exists(testUsingFile):
            testUsingFileExisted = True
            os.rename(testUsingFile, testUsingFileTemp)
        os.system("dotnet new xunit --name {}".format(project.testName))
        os.system("dotnet add {} reference {}".format(csTestProjFile, csProjFile))
        if project.haveDevModule:
            csProjTestXML = xmler.load(csTestProjFile)
            propertyGroup = xmler.getElementWithName(csProjTestXML, "PropertyGroup")
            xmler.setElementWithValue(propertyGroup, "TargetFramework", "{}-windows".format(xmler.getElementWithName(propertyGroup, "TargetFramework").firstChild.data))
            xmler.getOrCreateElementWithValue(csProjTestXML, propertyGroup, "UseWPF", "true")
            xmler.save(csProjTestXML, csTestProjFile)
            os.system("dotnet add {} reference {}".format(csTestProjFile, csTypeDProjFile))
        os.remove(testUsingFile)
        if testUsingFileExisted:
            os.rename(testUsingFileTemp, testUsingFile)
        if not testFileFound:
            os.remove(testFile)

    os.system("dotnet sln {} add {}".format(slnFile, csProjFile))
    if project.haveDevModule:
        os.system("dotnet sln {} add {}".format(slnFile, csTypeDProjFile))
    if project.haveTest:
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
    project = product.load(args.projectPath)
    csPath = "{}/{}/{}.csproj".format(args.projectPath, project.name, project.name)
    os.chdir(args.projectPath)
    createProjectAndSolution(project)

    csProjXML = xmler.load(csPath)
    addPreBuildEvents(csProjXML)
    xmler.save(csProjXML, csPath)