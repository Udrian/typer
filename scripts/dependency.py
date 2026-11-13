import json, os, subprocess, sys, urllib.request, zipfile, shutil
from scripts import product, xmler
from copy import deepcopy
from xml.dom import minidom

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
    parser.add_argument('--resolvedModules', type=str, help="Project TypeO/cache/modules.json to use for module versions")
    if os.name == 'nt':
        parser.add_argument('-c', '--cachePath',   type=str, default="",    help="Path to modules cache, defaults to '{{LOCALAPPDATA}}/TypeO/ModulesCache'")
    else:
        parser.add_argument('-c', '--cachePath',   type=str, default="",    help="Path to modules cache, defaults to '{{HOME}}/TypeO/ModulesCache'")

def do(args):
    resolvedPath = getattr(args, "resolvedModules", None)
    if resolvedPath is None:
        candidate = os.path.join(args.projectPath, "TypeO", "cache", "modules.json")
        if os.path.isfile(candidate):
            resolvedPath = candidate
    resolvedModules = {}
    if resolvedPath is not None:
        resolvedPath = os.path.abspath(resolvedPath)
        with open(resolvedPath) as f:
            for entry in json.load(f)["Modules"]:
                selected = product.Dependency("{}@{}-{}".format(entry["Author"], entry["Name"], entry["Version"]))
                key = (selected.author, selected.name)
                if selected.local:
                    selected.version = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(resolvedPath))), selected.version))
                if key in resolvedModules and (resolvedModules[key].version, resolvedModules[key].local) != (selected.version, selected.local):
                    raise ValueError("Conflicting resolved versions for '{}' in {}".format(selected.name, resolvedPath))
                resolvedModules[key] = selected
    resolveProject(args, resolvedPath, resolvedModules, set())

def resolveProject(args, resolvedPath, resolvedModules, visited):
    projectKey = os.path.normcase(os.path.realpath(args.projectPath))
    if projectKey in visited:
        return
    visited.add(projectKey)
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
        if not dependency.nuget:
            selected = resolvedModules.get((dependency.author, dependency.name))
            if selected is not None:
                dependency.version = selected.version
                dependency.local = selected.local
            elif dependency.local and resolvedPath is not None:
                dependency.version = os.path.abspath(os.path.join(args.projectPath, dependency.version))
        if dependency.local:
            localModulePath = "{}".format(dependency.version)
        else:
            localModulePath = "{}/{}/{}/{}".format(modulecachepath, dependency.author, dependency.name, dependency.version)
        
        if not os.path.isdir(localModulePath) and not dependency.local and not dependency.nuget:
            if resolvedPath is None:
                downloadAndExtractDependency(dependency, localModulePath)
            else:
                downloadAndExtractDependency(dependency, localModulePath, resolvedPath, modulecachepath)

        if resolvedPath is not None and not dependency.nuget:
            moduleArgs = deepcopy(args)
            moduleArgs.projectPath = localModulePath
            moduleArgs.cachePath = modulecachepath
            resolveProject(moduleArgs, resolvedPath, resolvedModules, visited)
        
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
            if manipulateProject(csProjXML, csPath, localModuleProjectPath, dependency, sub.type, projectTypes):
                xmler.save(csProjXML, csPath)

            if sub.type == "dev" or (sub.type == "" and dependency.usesMainAsDev(projectTypes)):
                for devProject in dependencyDevProjects:
                    typeDDependency = deepcopy(dependency)
                    typeDDependency.name = devProject.name
                    localDevProjectPath = "{}/{}".format(localModulePath, devProject.csprojPath)
                    expectedModules[sub.name][devProject.name] = localDevProjectPath
                    csProjXML = xmler.load(csPath)
                    if manipulateProject(csProjXML, csPath, localDevProjectPath, typeDDependency, "dev", ["dev"]):
                        xmler.save(csProjXML, csPath)

    removedIncludes = set()
    for sub in project.projects:
        csPath = "{}/{}".format(args.projectPath, sub.csprojPath)
        removedIncludes |= removeStaleDependencies(csPath, expectedModules[sub.name], expectedNugets[sub.name])
        if resolvedPath is not None:
            updateResolutionHook(csPath, args.projectPath, modulecachepath, resolvedPath)

    stillUsed = {include for modules in expectedModules.values() for include in modules.values()}
    expectedSolutionProjects = {
        os.path.splitext(os.path.basename(include))[0]: include
        for modules in expectedModules.values()
        for include in modules.values()
    }
    syncSolution(slnPath, expectedSolutionProjects, modulecachepath, removedIncludes - stillUsed)

def syncSolution(slnPath, expectedProjects, modulecachepath, removedProjects=()):
    """Reconcile the solution with TypeO module references, including previously failed updates."""
    if not os.path.isfile(slnPath):
        return

    solutionPath = os.path.abspath(slnPath)
    solutionDirectory = os.path.dirname(solutionPath)
    expectedPaths = {
        name: os.path.normcase(os.path.abspath(os.path.join(solutionDirectory, path)))
        for name, path in expectedProjects.items()
    }
    removedPaths = {os.path.normcase(os.path.abspath(path)) for path in removedProjects}
    cacheRoot = os.path.normcase(os.path.abspath(modulecachepath))

    def shouldRemove(path, name):
        normalizedPath = os.path.normcase(path)
        expectedPath = expectedPaths.get(name)
        try:
            inCache = os.path.commonpath((normalizedPath, cacheRoot)) == cacheRoot
        except ValueError:
            inCache = False
        return (normalizedPath in removedPaths
                or inCache and normalizedPath != expectedPath
                or expectedPath is not None and normalizedPath != expectedPath)

    if solutionPath.lower().endswith(".slnx"):
        solutionXML = minidom.parse(solutionPath)
        present = set()
        modified = False
        for project in list(solutionXML.getElementsByTagName("Project")):
            if not project.hasAttribute("Path"):
                continue
            path = project.getAttribute("Path")
            fullPath = os.path.normcase(os.path.abspath(os.path.join(solutionDirectory, path)))
            name = os.path.splitext(os.path.basename(path))[0]
            if shouldRemove(fullPath, name):
                project.parentNode.removeChild(project)
                modified = True
            else:
                present.add(name)

        for name, path in expectedProjects.items():
            if name in present:
                continue
            project = solutionXML.createElement("Project")
            project.setAttribute("Path", os.path.abspath(path).replace(os.sep, "/"))
            solutionXML.documentElement.appendChild(project)
            modified = True

        if modified:
            content = solutionXML.toprettyxml(indent="  ")
            with open(solutionPath, "w", encoding="utf-8") as solutionFile:
                solutionFile.write("\n".join(line for line in content.splitlines() if line.strip()) + "\n")
        return

    result = subprocess.run(
        ["dotnet", "sln", solutionPath, "list"],
        check=True, capture_output=True, text=True, cwd=solutionDirectory)
    listedProjects = []
    for line in result.stdout.splitlines():
        path = line.strip().strip('"')
        if path.lower().endswith(".csproj"):
            fullPath = os.path.abspath(os.path.join(os.path.dirname(slnPath), path))
            listedProjects.append((path, fullPath, os.path.splitext(os.path.basename(path))[0]))

    present = set()
    for listedPath, fullPath, name in listedProjects:
        normalizedPath = os.path.normcase(fullPath)
        if shouldRemove(normalizedPath, name):
            subprocess.run(["dotnet", "sln", solutionPath, "remove", listedPath],
                           check=True, cwd=solutionDirectory)
        else:
            present.add(name)

    for name, path in expectedProjects.items():
        if name not in present:
            subprocess.run(["dotnet", "sln", solutionPath, "add", os.path.abspath(path)],
                           check=True, cwd=solutionDirectory)

def updateResolutionHook(csPath, projectPath, cachePath, resolvedPath):
    """Keep module pre-build resolution on this TypeR and the root project's selected versions."""
    csProjXML = xmler.load(csPath)
    typerPath = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "typer.py")
    command = '"{}" "{}" dependency -p "{}" -c "{}" --resolvedModules "{}"'.format(
        sys.executable, typerPath, os.path.abspath(projectPath), os.path.abspath(cachePath), resolvedPath)
    modified = False
    for target in csProjXML.getElementsByTagName("Target"):
        if target.getAttribute("Name") != "PreBuild":
            continue
        for task in target.getElementsByTagName("Exec"):
            previous = task.getAttribute("Command")
            if "typer" in previous and "dependency" in previous and previous != command:
                task.setAttribute("Command", command)
                modified = True
    if modified:
        xmler.save(csProjXML, csPath)

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

def downloadAndExtractDependency(dependency, localModulePath, resolvedPath=None, cachePath=""):
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

    if resolvedPath is not None:
        typerPath = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "typer.py")
        subprocess.run([sys.executable, typerPath, "generate", "-p", os.path.abspath(localModulePath),
                        "-c", os.path.abspath(cachePath), "--resolvedModules", resolvedPath], check=True)
        return

    os.system("git clone https://github.com/Udrian/typer.git {}/typer".format(localModulePath))
    oldcwd = os.getcwd()
    os.chdir(localModulePath)
    if os.name == 'nt':
        os.system("create_project_files.bat")
    else:
        os.system("bash ./create_project_files.sh")
    os.chdir(oldcwd)

def manipulateProject(csProjXML, csPath, localModuleProjectPath, dependency, projectType, allProjectTypes=None):
    if not dependency.appliesTo(projectType, allProjectTypes):
        return False
    
    if dependency.nuget:
        return resolveNuget(csProjXML, csPath, dependency)
    
    return resolveTypeODep(csProjXML, localModuleProjectPath, dependency)

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

def resolveTypeODep(csProjXML, localModuleProjectPath, dependency):
    moduleItemGroup = xmler.getOrCreateElementWithAttribute(csProjXML, csProjXML, "ItemGroup", "Label", "TypeOModules")
        
    dontAdd = False
    for reference in moduleItemGroup.getElementsByTagName('ProjectReference'):
        if reference.getAttribute('Name') == dependency.name:
            if reference.getAttribute('Include') != localModuleProjectPath:
                moduleItemGroup.removeChild(reference)
            else:
                dontAdd = True
            break
    
    if dontAdd == True:
        return False

    reference = csProjXML.createElement("ProjectReference")
    reference.setAttribute("Name", dependency.name)
    reference.setAttribute("Include", localModuleProjectPath)
    moduleItemGroup.appendChild(reference)

    return True