import argparse, os
from asyncio.windows_events import NULL
import product
import urllib.request
import zipfile
from xml.dom import minidom
 
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', '--projectPath', type=str, required=True, help="Path to project to build")
    args = parser.parse_args()

    dependency(args.projectPath)

def dependency(projectPath):
    name = product.getName(projectPath)
    dependencies = product.getDependencies(projectPath)

    LOCALAPPDATA = os.getenv('LOCALAPPDATA')
    modulecachepath = "{}/TypeO/ModulesCache".format(LOCALAPPDATA)
    csPath = "{}/{}/{}.csproj".format(projectPath, name, name)

    print("Fetching dependencies for '{}'".format(name))

    for dependency in dependencies:
        dependencyName = dependency.split("-")[0]
        dependencyVersion = dependency.split("-")[1]
        localModulePath = "{}/{}/{}".format(modulecachepath, dependencyName, dependencyVersion)
        
        if not os.path.isdir(localModulePath):
            print("Downloading '{}'".format(dependency))

            zipName = "{}-{}.zip".format(dependencyName, dependencyVersion)
            url = "https://typedeaf.nyc3.cdn.digitaloceanspaces.com/typeo/releases/modules/{}/{}/{}".format(dependencyName, dependencyVersion, zipName)
            localZipPath = "{}/{}".format(localModulePath, zipName)
            
            os.makedirs(localModulePath)
            urllib.request.urlretrieve(url, localZipPath)

            with zipfile.ZipFile(localZipPath, 'r') as zip_ref:
                zip_ref.extractall(localModulePath)

            os.remove(localZipPath)

        csProjXML = minidom.parse(csPath)
        itemGroups = csProjXML.getElementsByTagName('ItemGroup')

        moduleItemGroup = NULL
        for itemGroup in itemGroups:
            if itemGroup.hasAttribute('Label') and itemGroup.getAttribute('Label') == "TypeOModules":
                moduleItemGroup = itemGroup
                break

        if moduleItemGroup == NULL:
            moduleItemGroup = csProjXML.createElement("ItemGroup")
            moduleItemGroup.setAttribute("Label", "TypeOModules")

        alreadyAdded = False
        for reference in moduleItemGroup.getElementsByTagName('Reference'):
            if reference.getAttribute('Include') == dependencyName:
                alreadyAdded = True
                break
        if alreadyAdded:
            continue
        
        reference = csProjXML.createElement("Reference")
        reference.setAttribute("Include", dependencyName)
        reference.setAttribute("HintPath", "{}/{}.dll".format(localModulePath, dependencyName))

        moduleItemGroup.appendChild(reference)
        csProjXML.childNodes[0].appendChild(moduleItemGroup)

        with open(csPath,"w") as fs:
            dom_string = csProjXML.childNodes[0].toprettyxml()
            dom_string = '\n'.join([s for s in dom_string.splitlines() if s.strip()])
            fs.write(dom_string)
            fs.close()

if __name__ == "__main__":
    main()