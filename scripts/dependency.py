import os, urllib.request, zipfile, shutil
from scripts import product, xmler
from copy import deepcopy
 
def parse(parser):
    parser.add_argument('-p', '--projectPath', type=str, required=True, help="Path to project")
    if os.name == 'nt':
        parser.add_argument('-c', '--cachePath',   type=str, default="",    help="Path to modules cache, defaults to '{{LOCALAPPDATA}}/TypeO/ModulesCache'")
    else:
        parser.add_argument('-c', '--cachePath',   type=str, default="",    help="Path to modules cache, defaults to '{{HOME}}/TypeO/ModulesCache'")

def do(args):
    project = product.load(args.projectPath)
    modulecachepath = args.cachePath

    if modulecachepath == "":
        if os.name == 'nt':
            modulecachepath = "{}/TypeO/ModulesCache".format(os.getenv('LOCALAPPDATA'))
        else:
            modulecachepath = "{}/TypeO/ModulesCache".format(os.getenv('HOME'))
    slnPath = "{}/{}.sln".format(args.projectPath, project.name)
    projectTypes = [sub.type for sub in project.projects]

    print("Fetching dependencies for '{}'".format(project.name))

    expectedModules = {sub.name: {} for sub in project.projects}
    expectedNugets = {sub.name: set() for sub in project.projects}

    for dependency in project.dependencies:
        if dependency.projectTypes and not any(t in projectTypes for t in dependency.projectTypes):
            continue
        if dependency.local:
            localModulePath = "{}".format(dependency.version)
        else:
            localModulePath = "{}/{}/{}".format(modulecachepath, dependency.name, dependency.version)
        
        if not os.path.isdir(localModulePath) and not dependency.local and not dependency.nuget:
            downloadAndExtractDependency(dependency, localModulePath)
        
        localModuleProjectPath = "{0}/{1}/{1}.csproj".format(localModulePath, dependency.name)

        dependencyDevProjects = []
        if not dependency.nuget and any(t == "dev" for t in projectTypes):
            dependencyDevProjects = [sub for sub in product.load(localModulePath).projects if sub.type == "dev"]

        for sub in project.projects:
            csPath = "{}/{}".format(args.projectPath, sub.csprojPath)
            if dependency.appliesTo(sub.type):
                if dependency.nuget:
                    expectedNugets[sub.name].add(dependency.name)
                else:
                    expectedModules[sub.name][dependency.name] = localModuleProjectPath
            csProjXML = xmler.load(csPath)
            if manipulateProject(csProjXML, csPath, slnPath, localModuleProjectPath, dependency, sub.type):
                xmler.save(csProjXML, csPath)

            if sub.type == "dev":
                for devProject in dependencyDevProjects:
                    typeDDependency = deepcopy(dependency)
                    typeDDependency.name = devProject.name
                    localDevProjectPath = "{}/{}".format(localModulePath, devProject.csprojPath)
                    if typeDDependency.appliesTo("dev"):
                        expectedModules[sub.name][devProject.name] = localDevProjectPath
                    csProjXML = xmler.load(csPath)
                    if manipulateProject(csProjXML, csPath, slnPath, localDevProjectPath, typeDDependency, "dev"):
                        xmler.save(csProjXML, csPath)

    removedIncludes = set()
    for sub in project.projects:
        csPath = "{}/{}".format(args.projectPath, sub.csprojPath)
        removedIncludes |= removeStaleDependencies(csPath, expectedModules[sub.name], expectedNugets[sub.name])

    stillUsed = {include for modules in expectedModules.values() for include in modules.values()}
    for include in removedIncludes - stillUsed:
        os.system("dotnet sln {} remove {}".format(slnPath, include))

def removeStaleDependencies(csPath, expectedModules, expectedNugets):
    """Removes TypeO module and nuget references that are no longer dependencies. Returns the removed module project paths."""
    csProjXML = xmler.load(csPath)

    removedIncludes = set()
    for reference in csProjXML.getElementsByTagName("ProjectReference"):
        group = reference.parentNode
        if group.getAttribute("Label") != "TypeOModules" or reference.getAttribute("Name") in expectedModules:
            continue
        removedIncludes.add(reference.getAttribute("Include"))
        group.removeChild(reference)
        if not group.getElementsByTagName("ProjectReference"):
            group.parentNode.removeChild(group)

    staleNugets = [p.getAttribute("Include") for p in csProjXML.getElementsByTagName("PackageReference")
                   if p.getAttribute("Include") not in expectedNugets]

    if removedIncludes:
        xmler.save(csProjXML, csPath)
    for name in staleNugets:
        os.system("dotnet remove {} package {}".format(csPath, name))

    return removedIncludes

def downloadAndExtractDependency(dependency, localModulePath):
    print("Downloading '{}-{}'".format(dependency.name, dependency.version))

    zipName = "{}.zip".format(dependency.version)
    url = "https://github.com/{}/{}/archive/refs/tags/{}".format(dependency.author, dependency.name, zipName)
    localZipPath = "{}/{}".format(localModulePath, zipName)
    
    os.makedirs(localModulePath)
    urllib.request.urlretrieve(url, localZipPath)

    with zipfile.ZipFile(localZipPath, 'r') as zip_ref:
        zip_ref.extractall(localModulePath)

    extractedDir = "{}/{}-{}".format(localModulePath, dependency.name.lower(), dependency.version)
    files = os.listdir(extractedDir)
    for file in files:
        shutil.move(os.path.join(extractedDir, file), localModulePath)

    os.remove(localZipPath)
    os.removedirs(extractedDir)

    os.system("git clone https://github.com/Udrian/typer.git {}/typer".format(localModulePath))
    oldcwd = os.getcwd()
    os.chdir(localModulePath)
    if os.name == 'nt':
        os.system("create_project_files.bat")
    else:
        os.system("bash ./create_project_files.sh")
    os.chdir(oldcwd)

def manipulateProject(csProjXML, csPath, slnPath, localModuleProjectPath, dependency, projectType):
    if not dependency.appliesTo(projectType):
        return False
    
    if dependency.nuget:
        resolveNuget(csProjXML, csPath, dependency)
        return False
    
    return resolveTypeODep(csProjXML, slnPath, localModuleProjectPath, dependency)

def resolveNuget(csProjXML, csPath, dependency):
    nugetItemGroup = xmler.getElementWithNameAndNoAttribute(csProjXML, "ItemGroup")

    dontAdd = False
    if nugetItemGroup != 0:
        for nuget in nugetItemGroup.getElementsByTagName('PackageReference'):
            if nuget.getAttribute('Include') == dependency.name and nuget.getAttribute('Version') == dependency.version:
                dontAdd = True
                break

    if not dontAdd:
        os.system("dotnet add {} package {} -v {}".format(csPath, dependency.name, dependency.version))

def resolveTypeODep(csProjXML, slnPath, localModuleProjectPath, dependency):
    moduleItemGroup = xmler.getOrCreateElementWithAttribute(csProjXML, csProjXML, "ItemGroup", "Label", "TypeOModules")
        
    dontAdd = False
    for reference in moduleItemGroup.getElementsByTagName('ProjectReference'):
        if reference.getAttribute('Name') == dependency.name:
            if reference.getAttribute('Include') != localModuleProjectPath:
                os.system("dotnet sln {} remove {}".format(slnPath, reference.getAttribute('Include')))
                moduleItemGroup.removeChild(reference)
            else:
                dontAdd = True
            break
    
    if dontAdd == True:
        return False

    reference = csProjXML.createElement("ProjectReference")
    reference.setAttribute("Name", dependency.name)
    reference.setAttribute("Include", localModuleProjectPath)
    os.system("dotnet sln {} add {}".format(slnPath, localModuleProjectPath))
    moduleItemGroup.appendChild(reference)

    return True