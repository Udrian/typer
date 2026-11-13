import os
from scripts import product, xmler, cmd, dependency

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
    parser.add_argument('--resolvedModules', type=str, help="Project TypeO/cache/modules.json to use for module versions")
    if os.name == 'nt':
        parser.add_argument('-c', '--cachePath',   type=str, default="",    help="Path to modules cache, defaults to '{{LOCALAPPDATA}}/TypeO/ModulesCache'")
    else:
        parser.add_argument('-c', '--cachePath',   type=str, default="",    help="Path to modules cache, defaults to '{{HOME}}/TypeO/ModulesCache'")

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
        
        # Remove template's auto-included diagnostics packages since typeo.json specifies which one to use
        for pkg in csProjXML.getElementsByTagName("PackageReference"):
            pkgName = pkg.getAttribute("Include").lower()
            if pkgName in ("avaloniaui.diagnosticssupport", "avalonia.diagnostics"):
                pkg.parentNode.removeChild(pkg)
        
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

def addDefaultVar(csProjXML, sub):
    propertyGroup = xmler.getElementWithName(csProjXML, "PropertyGroup")
    
    # Clear all PropertyGroup children
    while propertyGroup.firstChild:
        propertyGroup.removeChild(propertyGroup.firstChild)
    
    # Add standard properties
    xmler.createElement(csProjXML, propertyGroup, "TargetFramework", "net10.0")
    xmler.createElement(csProjXML, propertyGroup, "ImplicitUsings", "enable")
    
    # Apply project-specific PropertyGroup settings
    for key, value in sub.propertyGroup.items():
        if value is not None:
            xmler.createElement(csProjXML, propertyGroup, key, str(value))
    
    # Add GenerateDocumentationFile for main projects if not overridden
    if sub.type == "" and "GenerateDocumentationFile" not in sub.propertyGroup:
        xmler.createElement(csProjXML, propertyGroup, "GenerateDocumentationFile", "true")

def addPreBuildEvents(csProjXML):
    target = xmler.getOrCreateElementWithAttributes(csProjXML, csProjXML, "Target",[
        {"name": "Name",          "value": "PreBuild"},
        {"name": "BeforeTargets", "value": "PreBuildEvent"}
    ])

    windowsExec = xmler.getOrCreateElementWithAttributes(csProjXML, target, "Exec", [
        {"name": "Condition", "value": "!$([MSBuild]::IsOSUnixLike()) And '$(TypeODependenciesResolved)' != 'true'"},
        {"name": "Command",   "value": "cmd /c &quot;$(ProjectDir)../typer/typer.bat dependency -p $(ProjectDir)../&quot;"}
    ])
    
    unixExec = xmler.getOrCreateElementWithAttributes(csProjXML, target, "Exec", [
        {"name": "Condition", "value": "$([MSBuild]::IsOSUnixLike()) And '$(TypeODependenciesResolved)' != 'true'"},
        {"name": "Command",   "value": "bash &quot;$(ProjectDir)../typer/typer.sh&quot; dependency -p &quot;$(ProjectDir)../&quot;"}
    ])

def addPackageReferences(csProjXML, sub):
    """Apply project-specific PackageReference attributes and conditions"""
    # Find or create the main PackageReference ItemGroup
    packageGroup = None
    for group in csProjXML.getElementsByTagName("ItemGroup"):
        # Look for a group that doesn't have a Label attribute, or has a specific label for packages
        if group.hasAttribute("Label"):
            continue
        refs = group.getElementsByTagName("PackageReference")
        if refs.length > 0:
            packageGroup = group
            break
    
    # If no PackageReference group exists, create one
    if packageGroup is None:
        # Only create if we have packageReferences to add
        if not sub.packageReferences:
            return
        packageGroup = csProjXML.createElement("ItemGroup")
        csProjXML.documentElement.appendChild(packageGroup)
    
    # Track which packages from typeo.json we've processed
    processedPackages = set()
    
    # Apply customizations to existing PackageReferences
    for pkgRef in packageGroup.getElementsByTagName("PackageReference"):
        pkgName = pkgRef.getAttribute("Include")
        if pkgName in sub.packageReferences:
            processedPackages.add(pkgName)
            attrs = sub.packageReferences[pkgName]
            
            # Handle nested elements like IncludeAssets, PrivateAssets
            for attrName, attrValue in attrs.items():
                if attrName == "Condition":
                    continue  # Condition goes on child elements, not PackageReference
                
                if attrValue is not None and attrName in ("IncludeAssets", "PrivateAssets"):
                    # Check if element already exists
                    existing = None
                    for child in pkgRef.getElementsByTagName(attrName):
                        existing = child
                        break
                    
                    if existing is None:
                        child = csProjXML.createElement(attrName)
                        child.appendChild(csProjXML.createTextNode(attrValue))
                        # If Condition is specified, apply it to the child element
                        if "Condition" in attrs and attrs["Condition"] is not None:
                            child.setAttribute("Condition", attrs["Condition"])
                        pkgRef.appendChild(child)
                    else:
                        # Update existing element
                        existing.firstChild.data = attrValue
                        if "Condition" in attrs and attrs["Condition"] is not None:
                            existing.setAttribute("Condition", attrs["Condition"])
                else:
                    # Regular attributes (not IncludeAssets/PrivateAssets/Condition)
                    if attrValue is not None:
                        pkgRef.setAttribute(attrName, str(attrValue))
    
    # Create missing PackageReferences that are specified in typeo.json but not in the template
    for pkgName, attrs in sub.packageReferences.items():
        if pkgName not in processedPackages:
            # Create new PackageReference element
            pkgRef = csProjXML.createElement("PackageReference")
            pkgRef.setAttribute("Include", pkgName)
            
            # Add nested elements (Condition goes on the child elements, not the PackageReference)
            for attrName, attrValue in attrs.items():
                if attrName == "Condition":
                    continue  # Condition goes on child elements, not PackageReference
                
                if attrValue is not None and attrName in ("IncludeAssets", "PrivateAssets"):
                    child = csProjXML.createElement(attrName)
                    child.appendChild(csProjXML.createTextNode(attrValue))
                    # If Condition is specified, apply it to the child element
                    if "Condition" in attrs and attrs["Condition"] is not None:
                        child.setAttribute("Condition", attrs["Condition"])
                    pkgRef.appendChild(child)
                elif attrValue is not None and attrName not in ("IncludeAssets", "PrivateAssets"):
                    pkgRef.setAttribute(attrName, str(attrValue))
            packageGroup.appendChild(pkgRef)

def addUsingStatements(csProjXML, sub):
    """Add Using directives for test projects"""
    if not sub.usingStatements:
        return
    
    # Find or create ItemGroup for Using statements
    usingGroup = None
    for group in csProjXML.getElementsByTagName("ItemGroup"):
        usings = group.getElementsByTagName("Using")
        if usings.length > 0:
            usingGroup = group
            break
    
    if usingGroup is None:
        usingGroup = csProjXML.createElement("ItemGroup")
        csProjXML.documentElement.appendChild(usingGroup)
    
    # Add Using statements
    for usingName in sub.usingStatements:
        # Check if already exists
        exists = False
        for using in usingGroup.getElementsByTagName("Using"):
            if using.getAttribute("Include") == usingName:
                exists = True
                break
        
        if not exists:
            using = csProjXML.createElement("Using")
            using.setAttribute("Include", usingName)
            usingGroup.appendChild(using)

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

def addTypeoConfigFiles(csProjXML):
    configFiles = ["../typeo.json", "../typeo_override.json"]
    
    for configFile in configFiles:
        noneItemGroup = xmler.getOrCreateElementWithAttribute(csProjXML, csProjXML, "ItemGroup", "Label", "TypeOConfig")
        
        dontAdd = False
        for none in noneItemGroup.getElementsByTagName('None'):
            if none.getAttribute('Include') == configFile:
                dontAdd = True
                break
        
        if not dontAdd:
            noneElement = csProjXML.createElement("None")
            noneElement.setAttribute("Include", configFile)
            noneItemGroup.appendChild(noneElement)

def addCustomItemGroups(csProjXML, sub):
    if not sub.itemGroups:
        return
    
    for itemGroupDef in sub.itemGroups:
        if "items" not in itemGroupDef:
            continue
        
        # Create an ItemGroup (without Label so it's a regular group)
        itemGroup = csProjXML.createElement("ItemGroup")
        
        # Add each item to the ItemGroup
        hasItems = False
        for item in itemGroupDef.get("items", []):
            itemName = item.get("name")
            if not itemName:
                continue
            
            # Check if this item already exists in any ItemGroup
            exists = False
            for existingGroup in csProjXML.getElementsByTagName("ItemGroup"):
                for existingItem in existingGroup.getElementsByTagName(itemName):
                    # Compare attributes to see if it's the same item
                    sameItem = True
                    for attrKey, attrValue in item.items():
                        if attrKey == "name":
                            continue
                        attrName = attrKey[0].upper() + attrKey[1:] if attrKey else attrKey
                        if existingItem.getAttribute(attrName) != str(attrValue if attrValue else ""):
                            sameItem = False
                            break
                    if sameItem:
                        exists = True
                        break
                if exists:
                    break
            
            if not exists:
                element = csProjXML.createElement(itemName)
                
                # Add attributes from the item definition
                for attrKey, attrValue in item.items():
                    if attrKey == "name":
                        continue  # name is the element type, not an attribute
                    # Convert attribute keys to proper casing (e.g., "include" -> "Include")
                    attrName = attrKey[0].upper() + attrKey[1:] if attrKey else attrKey
                    if attrValue is not None:
                        element.setAttribute(attrName, str(attrValue))
                
                itemGroup.appendChild(element)
                hasItems = True
        
        # Only append the ItemGroup if it has items
        if hasItems:
            csProjXML.documentElement.appendChild(itemGroup)

def do(args):
    project = product.load(args.projectPath)
    os.chdir(args.projectPath)
    checkAndInstallPrerequisites()
    createProjectAndSolution(project)

    for sub in project.projects:
        csPath = "{}/{}".format(args.projectPath, sub.csprojPath)
        csProjXML = xmler.load(csPath)
        if sub.type == "":
            addDefaultVar(csProjXML, sub)
            addPreBuildEvents(csProjXML)
        else:
            addDefaultVar(csProjXML, sub)
        addPackageReferences(csProjXML, sub)
        addUsingStatements(csProjXML, sub)
        addExternals(csProjXML, project, sub.type == "dev", sub.type == "test")
        addTypeoConfigFiles(csProjXML)
        addCustomItemGroups(csProjXML, sub)
        xmler.save(csProjXML, csPath)
    
    # Resolve dependencies after generating csproj files
    dependency.do(args)
