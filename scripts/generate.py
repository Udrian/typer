import os
from scripts import product, xmler, cmd

def parse(parser):
    parser.add_argument('-p', '--projectPath', type=str, required=True,       help="Path to project")

def createProjectAndSolution(project):
    csProjFile = "{}/{}.csproj".format(project.name, project.name)
    csTestProjFile = "{}/{}.csproj".format(project.testName, project.testName)
    csTypeDProjFile = "{}/{}.csproj".format(project.devModuleName, project.devModuleName)
    slnFile = "{}.sln".format(project.name)

    if not os.path.exists(slnFile):
        cmd.exec("dotnet new sln --name {}".format(project.name))
    if not os.path.exists(csProjFile):
        cmd.exec("dotnet new classlib --name {}".format(project.name))
    if os.path.exists("{}/Class1.cs".format(project.name)):
        os.remove("{}/Class1.cs".format(project.name))
    if project.haveDevModule:
        if not os.path.exists(csTypeDProjFile):
            cmd.exec("dotnet new wpflib --name {}".format(project.devModuleName))
        if os.path.exists("{}/Class1.cs".format(project.devModuleName)):
            os.remove("{}/Class1.cs".format(project.devModuleName))
        if not cmd.exist("dotnet list {} reference".format(csTypeDProjFile), csProjFile):
            cmd.exec("dotnet add {} reference {}".format(csTypeDProjFile, csProjFile))
    
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
        if not os.path.exists(csTestProjFile):
            cmd.exec("dotnet new xunit --name {}".format(project.testName))
        if not cmd.exist("dotnet list {} reference".format(csTestProjFile), csProjFile):
            cmd.exec("dotnet add {} reference {}".format(csTestProjFile, csProjFile))
        if project.haveDevModule:
            csProjTestXML = xmler.load(csTestProjFile)
            propertyGroup = xmler.getElementWithName(csProjTestXML, "PropertyGroup")
            xmler.setElementWithValue(propertyGroup, "TargetFramework", "{}-windows".format(xmler.getElementWithName(propertyGroup, "TargetFramework").firstChild.data))
            xmler.getOrCreateElementWithValue(csProjTestXML, propertyGroup, "UseWPF", "true")
            xmler.save(csProjTestXML, csTestProjFile)
            if not cmd.exist("dotnet list {} reference".format(csTestProjFile), csTypeDProjFile):
                cmd.exec("dotnet add {} reference {}".format(csTestProjFile, csTypeDProjFile))
        if(os.path.exists(testUsingFile)):
            os.remove(testUsingFile)
        if testUsingFileExisted:
            os.rename(testUsingFileTemp, testUsingFile)
        if not testFileFound:
            if(os.path.exists(testFile)):
                os.remove(testFile)

    if not cmd.exist("dotnet sln {} list".format(slnFile), csProjFile):
        cmd.exec("dotnet sln {} add {}".format(slnFile, csProjFile))
    if project.haveDevModule:
        if not cmd.exist("dotnet sln {} list".format(slnFile), csTypeDProjFile):
            cmd.exec("dotnet sln {} add {}".format(slnFile, csTypeDProjFile))
    if project.haveTest:
        if not cmd.exist("dotnet sln {} list".format(slnFile), csTestProjFile):
            cmd.exec("dotnet sln {} add {}".format(slnFile, csTestProjFile))

def addPreBuildEvents(csProjXML):
    target = xmler.getOrCreateElementWithAttributes(csProjXML, csProjXML, "Target",[
        {"name": "Name",          "value": "PreBuild"},
        {"name": "BeforeTargets", "value": "PreBuildEvent"}
    ])

    xmler.getOrCreateElementWithAttributes(csProjXML, target, "Exec", [
        {"name": "Condition", "value": "!$([MSBuild]::IsOSUnixLike())"},
        {"name": "Command",   "value": "cmd /c &quot;$(ProjectDir)../typer/typer.bat dependency -p $(ProjectDir)../&quot;"}
    ])
    xmler.getOrCreateElementWithAttributes(csProjXML, target, "Exec", [
        {"name": "Condition", "value": "$([MSBuild]::IsOSUnixLike())"},
        {"name": "Command",   "value": "bash &quot;$(ProjectDir)../typer/typer.sh&quot; dependency -p &quot;$(ProjectDir)../&quot;"}
    ])

    xmler.add(csProjXML, target)

def addDefaultVar(csProjXML):
    propertyGroup = xmler.getElementWithName(csProjXML, "PropertyGroup")
    xmler.getOrCreateElementWithValue(csProjXML, propertyGroup, "GenerateDocumentationFile", "true")

def do(args):
    project = product.load(args.projectPath)
    csPath = "{}/{}/{}.csproj".format(args.projectPath, project.name, project.name)
    os.chdir(args.projectPath)
    createProjectAndSolution(project)

    csProjXML = xmler.load(csPath)
    addDefaultVar(csProjXML)
    addPreBuildEvents(csProjXML)
    xmler.save(csProjXML, csPath)