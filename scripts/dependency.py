import os, urllib.request, zipfile
from scripts import product, xmler
 
def parse(parser):
    parser.add_argument('-p', '--projectPath', type=str, required=True, help="Path to project")
    parser.add_argument('-c', '--cachePath',   type=str, default="",    help="Path to modules cache, defaults to '{{LOCALAPPDATA}}/TypeO/ModulesCache'")

def do(args):
    project = product.load(args.projectPath)
    modulecachepath = args.cachePath

    if modulecachepath == "":
        modulecachepath = "{}/TypeO/ModulesCache".format(os.getenv('LOCALAPPDATA'))
    csPath = "{}/{}/{}.csproj".format(args.projectPath, project.name, project.name)
    slnPath = "{}/{}.sln".format(args.projectPath, project.name)

    print("Fetching dependencies for '{}'".format(project.name))

    for dependency in project.dependencies:
        if not project.haveDevModule and dependency.dev:
            continue
        localModulePath = "{}/{}/{}".format(modulecachepath, dependency.name, dependency.version)
        
        if not os.path.isdir(localModulePath) and not dependency.local:
            print("Downloading '{}'".format(dependency))

            zipName = "{}-{}.zip".format(dependency.name, dependency.version)
            url = "https://typedeaf.nyc3.cdn.digitaloceanspaces.com/typeo/releases/modules/{}/{}/{}".format(dependency.name, dependency.version, zipName)
            localZipPath = "{}/{}".format(localModulePath, zipName)
            
            os.makedirs(localModulePath)
            urllib.request.urlretrieve(url, localZipPath)

            with zipfile.ZipFile(localZipPath, 'r') as zip_ref:
                zip_ref.extractall(localModulePath)

            os.remove(localZipPath)

        localModuleDllPath = "{}/{}.dll".format(localModulePath, dependency.name)
        
        csProjXML = xmler.load(csPath)
        if manipulateProject(csProjXML, slnPath, localModuleDllPath, dependency, False):
            xmler.save(csProjXML, csPath)

        if project.haveDevModule:
            csTypeDPath = "{}/{}/{}.csproj".format(args.projectPath, project.devModuleName, project.devModuleName)
            csTypeDProjXML = xmler.load(csTypeDPath)
            if manipulateProject(csTypeDProjXML, slnPath, localModuleDllPath, dependency, True):
                xmler.save(csTypeDProjXML, csTypeDPath)

        if project.haveTest:
            csTestPath = "{}/{}/{}.csproj".format(args.projectPath, project.testName, project.testName)
            csTestProjXML = xmler.load(csTestPath)
            if manipulateProject(csTestProjXML, slnPath, localModuleDllPath, dependency, project.haveDevModule):
                xmler.save(csTestProjXML, csTestPath)
        

def manipulateProject(csProjXML, slnPath, localModuleDllPath, dependency, dev):
    if not dev and dependency.dev:
        return False
    moduleItemGroup = xmler.getOrCreateElementWithAttribute(csProjXML, csProjXML, "ItemGroup", "Label", "TypeOModules")
        
    dontAdd = False
    for reference in moduleItemGroup.getElementsByTagName('Reference'):
        if reference.getAttribute('Include') == dependency.name:
            if reference.getAttribute('HintPath') != localModuleDllPath or dependency.local:
                moduleItemGroup.removeChild(reference)
            else:
                dontAdd = True
            break
    for reference in moduleItemGroup.getElementsByTagName('ProjectReference'):
        if reference.getAttribute('Name') == dependency.name:
            if reference.getAttribute('Include') != dependency.version or not dependency.local:
                os.system("dotnet sln {} remove {}".format(slnPath, reference.getAttribute('Include')))
                moduleItemGroup.removeChild(reference)
            else:
                dontAdd = True
            break
    
    if dontAdd == True:
        return False

    if dependency.local:
        reference = csProjXML.createElement("ProjectReference")
        reference.setAttribute("Name", dependency.name)
        reference.setAttribute("Include", dependency.version)
        os.system("dotnet sln {} add {}".format(slnPath, dependency.version))
    else:
        reference = csProjXML.createElement("Reference")
        reference.setAttribute("Include", dependency.name)
        reference.setAttribute("HintPath", localModuleDllPath)
    moduleItemGroup.appendChild(reference)

    return True