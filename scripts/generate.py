import os
from scripts import product, xmler, cmd

def find_solution_file(projectPath, projectName):
    """Find the solution file, checking for both .sln and .slnx formats"""
    sln_path = "{}.sln".format(projectName)
    slnx_path = "{}.slnx".format(projectName)
    
    if os.path.exists(sln_path):
        return sln_path
    elif os.path.exists(slnx_path):
        return slnx_path
    else:
        return sln_path  # Default to .sln if neither exists

def parse(parser):
    parser.add_argument('-p', '--projectPath', type=str, required=True,       help="Path to project")

def checkAndInstallPrerequisites():
    if not cmd.exist("dotnet new list Avalonia", "Avalonia"):
        cmd.exec("dotnet new install Avalonia.Templates")

def createClassLib(sub):
    if not os.path.exists(sub.csprojPath):
        cmd.exec("dotnet new classlib --name {}".format(sub.name))
    if os.path.exists("{}/Class1.cs".format(sub.name)):
        os.remove("{}/Class1.cs".format(sub.name))

def createDevProject(project, sub):
    if not os.path.exists(sub.csprojPath):
        cmd.exec("dotnet new avalonia.app --name {}".format(sub.name))
    filesToCleanup = ["{}/App.axaml".format(sub.name),
                      "{}/App.axaml.cs".format(sub.name),
                      "{}/app.manifest".format(sub.name),
                      "{}/MainWindow.axaml".format(sub.name),
                      "{}/MainWindow.axaml.cs".format(sub.name),
                      "{}/Program.cs".format(sub.name)]
    for file in filesToCleanup:
        if os.path.exists(file):
            os.remove(file)

    if project.isModule:
        csProjXML = xmler.load(sub.csprojPath)
        propertyGroup = xmler.getElementWithName(csProjXML, "PropertyGroup")
        xmler.deleteElement(propertyGroup, "OutputType")
        xmler.deleteElement(propertyGroup, "ApplicationManifest")
        xmler.deleteElement(propertyGroup, "AvaloniaUseCompiledBindingsByDefault")
        xmler.save(csProjXML, sub.csprojPath)

def createTestProject(sub):
    testFile = "{}/UnitTest1.cs".format(sub.name)
    testUsingFile = "{}/Usings.cs".format(sub.name)
    testUsingFileTemp = "{}_temp".format(testUsingFile)
    testUsingFileExisted = os.path.exists(testUsingFile)
    testFileFound = os.path.exists(testFile)
    if testUsingFileExisted:
        os.rename(testUsingFile, testUsingFileTemp)
    if not os.path.exists(sub.csprojPath):
        cmd.exec("dotnet new xunit --name {}".format(sub.name))
    if os.path.exists(testUsingFile):
        os.remove(testUsingFile)
    if testUsingFileExisted:
        os.rename(testUsingFileTemp, testUsingFile)
    if not testFileFound and os.path.exists(testFile):
        os.remove(testFile)

def validateProjects(project):
    names = [sub.name for sub in project.projects]
    for sub in project.projects:
        if names.count(sub.name) > 1:
            raise ValueError("Project '{}' is defined more than once".format(sub.name))
        if sub.type not in ("", "dev", "test"):
            raise ValueError("Project '{}' has unknown type '{}'".format(sub.name, sub.type))
        for dependency in sub.dependsOn:
            if dependency not in names:
                raise ValueError("Project '{}' depends on unknown project '{}'".format(sub.name, dependency))
            if dependency == sub.name:
                raise ValueError("Project '{}' can't depend on itself".format(sub.name))

def createProjectAndSolution(project):
    validateProjects(project)
    slnFile = find_solution_file(".", project.name)

    if not os.path.exists(slnFile):
        cmd.exec("dotnet new sln --name {}".format(project.name))
        slnFile = find_solution_file(".", project.name)

    for sub in project.projects:
        if sub.type == "dev":
            createDevProject(project, sub)
        elif sub.type == "test":
            createTestProject(sub)
        else:
            createClassLib(sub)

    projectsByName = {sub.name: sub for sub in project.projects}
    for sub in project.projects:
        for dependency in sub.dependsOn:
            dependencyFile = projectsByName[dependency].csprojPath
            if not cmd.exist("dotnet list {} reference".format(sub.csprojPath), dependencyFile):
                cmd.exec("dotnet add {} reference {}".format(sub.csprojPath, dependencyFile))

    for sub in project.projects:
        if not cmd.exist("dotnet sln {} list".format(slnFile), sub.csprojPath):
            cmd.exec("dotnet sln {} add {}".format(slnFile, sub.csprojPath))

def addDefaultVar(csProjXML):
    propertyGroup = xmler.getElementWithName(csProjXML, "PropertyGroup")
    xmler.getOrCreateElementWithValue(csProjXML, propertyGroup, "GenerateDocumentationFile", "true")
    xmler.deleteElement(propertyGroup, "Nullable")

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
    os.chdir(args.projectPath)
    checkAndInstallPrerequisites()
    createProjectAndSolution(project)

    for sub in project.projects:
        csPath = "{}/{}".format(args.projectPath, sub.csprojPath)
        csProjXML = xmler.load(csPath)
        if sub.type == "":
            addDefaultVar(csProjXML)
            addPreBuildEvents(csProjXML)
        addExternals(csProjXML, project, sub.type == "dev", sub.type == "test")
        xmler.save(csProjXML, csPath)
