import os, urllib.request, zipfile, shutil
from scripts import product, xmler
from copy import deepcopy

def find_solution_file(projectPath, projectName):
    """Find the solution file, checking for both .sln and .slnx formats"""
    sln_path = "{}/{}.sln".format(projectPath, projectName)
    slnx_path = "{}/{}.slnx".format(projectPath, projectName)
    
    if os.path.exists(sln_path):
        return sln_path
    elif os.path.exists(slnx_path):
        return slnx_path
    else:
        return sln_path  # Default to .sln if neither exists
 
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
    slnPath = find_solution_file(args.projectPath, project.name)
    projectTypes = [sub.type for sub in project.projects]

    print("Fetching dependencies for '{}'".format(project.name))

    expectedModules = {sub.name: {} for sub in project.projects}
    expectedNugets = {sub.name: set() for sub in project.projects}

    for dependency in project.dependencies:
        if dependency.projectTypes and not any(t in projectTypes for t in dependency.projectTypes) \
                and not dependency.usesMainAsDev(projectTypes):
            continue
        if dependency.local:
            localModulePath = "{}".format(dependency.version)
        else:
            localModulePath = "{}/{}/{}/{}".format(modulecachepath, dependency.author, dependency.name, dependency.version)
        
        if not os.path.isdir(localModulePath) and not dependency.local and not dependency.nuget:
            downloadAndExtractDependency(dependency, localModulePath)
        
        localModuleProjectPath = "{0}/{1}/{1}.csproj".format(localModulePath, dependency.name)

        dependencyDevProjects = []
        if not dependency.nuget and ("dev" in projectTypes or dependency.usesMainAsDev(projectTypes)):
            dependencyDevProjects = [sub for sub in product.load(localModulePath).projects if sub.type == "dev"]

        for sub in project.projects:
            csPath = "{}/{}".format(args.projectPath, sub.csprojPath)
            if dependency.appliesTo(sub.type, projectTypes):
                if dependency.nuget:
                    expectedNugets[sub.name].add(dependency.name)
                else:
                    expectedModules[sub.name][dependency.name] = localModuleProjectPath
            csProjXML = xmler.load(csPath)
            if manipulateProject(csProjXML, csPath, slnPath, localModuleProjectPath, dependency, sub.type, projectTypes):
                xmler.save(csProjXML, csPath)

            if sub.type == "dev" or (sub.type == "" and dependency.usesMainAsDev(projectTypes)):
                for devProject in dependencyDevProjects:
                    typeDDependency = deepcopy(dependency)
                    typeDDependency.name = devProject.name
                    localDevProjectPath = "{}/{}".format(localModulePath, devProject.csprojPath)
                    expectedModules[sub.name][devProject.name] = localDevProjectPath
                    csProjXML = xmler.load(csPath)
                    if manipulateProject(csProjXML, csPath, slnPath, localDevProjectPath, typeDDependency, "dev", ["dev"]):
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

def manipulateProject(csProjXML, csPath, slnPath, localModuleProjectPath, dependency, projectType, allProjectTypes=None):
    if not dependency.appliesTo(projectType, allProjectTypes):
        return False
    
    if dependency.nuget:
        return resolveNuget(csProjXML, csPath, dependency)
    
    return resolveTypeODep(csProjXML, slnPath, localModuleProjectPath, dependency)

def resolveNuget(csProjXML, csPath, dependency):
    dontAdd = False
    existingRef = None
    xmlModified = False
    
    for nuget in csProjXML.getElementsByTagName('PackageReference'):
        if nuget.getAttribute('Include').lower() != dependency.name.lower():
            continue
        
        # Found the package - check version
        version = nuget.getAttribute('Version')
        if not version:
            versionNodes = nuget.getElementsByTagName('Version')
            if versionNodes and versionNodes[0].firstChild:
                version = versionNodes[0].firstChild.data
        
        # If version matches or there's no version yet, preserve the existing entry
        if not version or version.strip() == dependency.version:
            dontAdd = True
            existingRef = nuget
        else:
            # Version mismatch - need to update
            existingRef = nuget
        break

    if dontAdd and existingRef is not None:
        # Version matches - ensure version is set (might be in child element)
        if not existingRef.getAttribute('Version'):
            existingRef.setAttribute('Version', dependency.version)
            xmlModified = True
        return xmlModified
    elif existingRef is not None:
        # Version mismatch - update the existing reference instead of calling dotnet add
        # This preserves custom attributes like Condition on child elements
        existingRef.setAttribute('Version', dependency.version)
        xmlModified = True
        return xmlModified
    else:
        # Package doesn't exist yet - only then use dotnet add
        os.system("dotnet add {} package {} -v {}".format(csPath, dependency.name, dependency.version))
        return False

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