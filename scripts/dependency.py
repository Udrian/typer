import os, urllib.request, zipfile
from scripts import product, xmler
 
def parse(parser):
    parser.add_argument('-p', '--projectPath', type=str, required=True, help="Path to project")
    parser.add_argument('-c', '--cachePath',   type=str, default="",    help="Path to modules cache, defaults to '{LOCALAPPDATA}/TypeO/ModulesCache'")

def do(args):
    name = product.getName(args.projectPath)
    dependencies = product.getDependencies(args.projectPath)
    modulecachepath = args.cachePath

    if modulecachepath == "":
        LOCALAPPDATA = os.getenv('LOCALAPPDATA')
        modulecachepath = "{}/TypeO/ModulesCache".format(LOCALAPPDATA)
    csPath = "{}/{}/{}.csproj".format(args.projectPath, name, name)
    slnPath = "{}/{}.sln".format(args.projectPath, name)

    print("Fetching dependencies for '{}'".format(name))

    for dependency in dependencies:
        dependencyName = dependency.split("-")[0]
        dependencyVersion = dependency.split("-")[1]
        dependencyParam = []
        if ";" in dependencyVersion:
            dependencyParam = dependencyVersion.split(";")
            if "dev" in dependencyParam:
                continue
            dependencyVersion = dependencyVersion.split(";")[0]
        localModulePath = "{}/{}/{}".format(modulecachepath, dependencyName, dependencyVersion)
        
        if not os.path.isdir(localModulePath) and "local" not in dependencyParam:
            print("Downloading '{}'".format(dependency))

            zipName = "{}-{}.zip".format(dependencyName, dependencyVersion)
            url = "https://typedeaf.nyc3.cdn.digitaloceanspaces.com/typeo/releases/modules/{}/{}/{}".format(dependencyName, dependencyVersion, zipName)
            localZipPath = "{}/{}".format(localModulePath, zipName)
            
            os.makedirs(localModulePath)
            urllib.request.urlretrieve(url, localZipPath)

            with zipfile.ZipFile(localZipPath, 'r') as zip_ref:
                zip_ref.extractall(localModulePath)

            os.remove(localZipPath)

        localModuleDllPath = "{}/{}.dll".format(localModulePath, dependencyName)
        
        csProjXML = xmler.load(csPath)
        moduleItemGroup = xmler.getOrCreateElementWithAttribute(csProjXML, csProjXML, "ItemGroup", "Label", "TypeOModules")
        
        dontAdd = False
        for reference in moduleItemGroup.getElementsByTagName('Reference'):
            if reference.getAttribute('Include') == dependencyName:
                if reference.getAttribute('HintPath') != localModuleDllPath or "local" in dependencyParam:
                    moduleItemGroup.removeChild(reference)
                else:
                    dontAdd = True
                break
        for reference in moduleItemGroup.getElementsByTagName('ProjectReference'):
            if reference.getAttribute('Name') == dependencyName:
                if reference.getAttribute('Include') != dependencyVersion or "local" not in dependencyParam:
                    os.system("dotnet sln {} remove {}".format(slnPath, reference.getAttribute('Include')))
                    moduleItemGroup.removeChild(reference)
                else:
                    dontAdd = True
                break
        
        if dontAdd == True:
            continue

        if "local" in dependencyParam:
            reference = csProjXML.createElement("ProjectReference")
            reference.setAttribute("Name", dependencyName)
            reference.setAttribute("Include", dependencyVersion)
            os.system("dotnet sln {} add {}".format(slnPath, dependencyVersion))
        else:
            reference = csProjXML.createElement("Reference")
            reference.setAttribute("Include", dependencyName)
            reference.setAttribute("HintPath", localModuleDllPath)
        moduleItemGroup.appendChild(reference)

        xmler.save(csProjXML, csPath)