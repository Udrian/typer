import os
from scripts import product, xmler, cmd

def parse(parser):
    parser.add_argument('-p', '--projectPath', type=str, required=True,       help="Path to project")

def checkAndInstallPrerequisites():
    if not cmd.exist("dotnet new list Avalonia", "Avalonia"):
        cmd.exec("dotnet new install Avalonia.Templates")

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
            cmd.exec("dotnet new avalonia.app --name {}".format(project.devModuleName))
        filesToCleanup = ["{}/App.axaml".format(project.devModuleName),
                          "{}/App.axaml.cs".format(project.devModuleName),
                          "{}/app.manifest".format(project.devModuleName),
                          "{}/MainWindow.axaml".format(project.devModuleName),
                          "{}/MainWindow.axaml.cs".format(project.devModuleName),
                          "{}/Program.cs".format(project.devModuleName)]
        for file in filesToCleanup:
            if os.path.exists(file):
                os.remove(file)

        if project.isModule:
            csTypeDProjXML = xmler.load(csTypeDProjFile)
            propertyGroup = xmler.getElementWithName(csTypeDProjXML, "PropertyGroup")
            xmler.deleteElement(propertyGroup, "OutputType")
            xmler.deleteElement(propertyGroup, "ApplicationManifest")
            xmler.deleteElement(propertyGroup, "AvaloniaUseCompiledBindingsByDefault")
            xmler.save(csTypeDProjXML, csTypeDProjFile)
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

def addDefaultVar(csProjXML):
    propertyGroup = xmler.getElementWithName(csProjXML, "PropertyGroup")
    xmler.getOrCreateElementWithValue(csProjXML, propertyGroup, "GenerateDocumentationFile", "true")

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

def addExternals(csProjXML, project, dev, test):
    if not project.externals:
        return

    contentItemGroup = xmler.getOrCreateElementWithAttribute(csProjXML, csProjXML, "ItemGroup", "Label", "TypeOContent")
    
    for external in project.externals:
        if not dev and external.dev:
            continue
        if not test and external.test:
            continue

        dontAdd = False
        for resource in contentItemGroup.getElementsByTagName('Content'):
            if resource.getAttribute('Include') == external.path:
                dontAdd = True
                break
        
        if dontAdd:
            continue

        content = csProjXML.createElement("Content")
        content.setAttribute("Include", external.path)
        xmler.getOrCreateElementWithValue(csProjXML, content, "CopyToOutputDirectory", "PreserveNewest")
        contentItemGroup.appendChild(content)

def do(args):
    project = product.load(args.projectPath)
    csPath = "{}/{}/{}.csproj".format(args.projectPath, project.name, project.name)
    os.chdir(args.projectPath)
    checkAndInstallPrerequisites()
    createProjectAndSolution(project)

    csProjXML = xmler.load(csPath)
    addDefaultVar(csProjXML)
    addPreBuildEvents(csProjXML)
    addExternals(csProjXML, project, False, False)

    if project.haveDevModule:
        csTypeDPath = "{}/{}/{}.csproj".format(args.projectPath, project.devModuleName, project.devModuleName)
        csTypeDProjXML = xmler.load(csTypeDPath)
        addExternals(csTypeDProjXML, project, True, False)
        xmler.save(csTypeDProjXML, csTypeDPath)

    if project.haveTest:
        csTestPath = "{}/{}/{}.csproj".format(args.projectPath, project.testName, project.testName)
        csTestProjXML = xmler.load(csTestPath)
        addExternals(csTestProjXML, project, False, True)
        xmler.save(csTestProjXML, csTestPath)

    xmler.save(csProjXML, csPath)