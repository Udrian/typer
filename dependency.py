import argparse, os
import product
import urllib.request
import zipfile
from xml.dom import minidom
 
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', '--projectPath', type=str, required=True, help="Path to project to build")
    parser.add_argument('-c', '--cachePath',   type=str, default="",    help="Path to project to build")
    args = parser.parse_args()

    dependency(args.projectPath, args.cachePath)

def dependency(projectPath, modulecachepath):
    name = product.getName(projectPath)
    dependencies = product.getDependencies(projectPath)

    if modulecachepath == "":
        LOCALAPPDATA = os.getenv('LOCALAPPDATA')
        modulecachepath = "{}/TypeO/ModulesCache".format(LOCALAPPDATA)
    csPath = "{}/{}/{}.csproj".format(projectPath, name, name)

    print("Fetching dependencies for '{}'".format(name))

    for dependency in dependencies:
        dependencyName = dependency.split("-")[0]
        dependencyVersion = dependency.split("-")[1]
        localModulePath = "{}/{}/{}".format(modulecachepath, dependencyName, dependencyVersion)
        localModuleDllPath = "{}/{}.dll".format(localModulePath, dependencyName)
        
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

        moduleItemGroup = 0
        for itemGroup in itemGroups:
            if itemGroup.hasAttribute('Label') and itemGroup.getAttribute('Label') == "TypeOModules":
                moduleItemGroup = itemGroup
                break

        if moduleItemGroup == 0:
            moduleItemGroup = csProjXML.createElement("ItemGroup")
            moduleItemGroup.setAttribute("Label", "TypeOModules")
            csProjXML.childNodes[0].appendChild(moduleItemGroup)

        moduleReference = 0
        for reference in moduleItemGroup.getElementsByTagName('Reference'):
            if reference.getAttribute('Include') == dependencyName:
                moduleReference = reference
                break
        
        if moduleReference == 0:
            reference = csProjXML.createElement("Reference")
            moduleItemGroup.appendChild(reference)
        reference.setAttribute("Include", dependencyName)
        reference.setAttribute("HintPath", localModuleDllPath)
        
        with open(csPath,"w") as fs:
            dom_string = csProjXML.childNodes[0].toprettyxml()
            dom_string = '\n'.join([s for s in dom_string.splitlines() if s.strip()])
            fs.write(dom_string)
            fs.close()

if __name__ == "__main__":
    main()