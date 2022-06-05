import argparse, os
import zipfile
import product
from os.path import basename
from os.path import isfile, isdir
 
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', '--projectPath',  type=str, required=True, help="Path to project to pack")
    parser.add_argument('-b', '--buildNumber',  type=int, required=True, help="Build number to append to versioning")
    parser.add_argument('-o', '--output',       type=str, default="..",  help="Output folder")
    args = parser.parse_args()

    pack(args.projectPath, args.buildNumber, args.output)

def pack(projectPath, buildNumber, outputRoot):
    extraProjectPaths = product.getExtraProjects(projectPath)
    projectPaths = [projectPath] + extraProjectPaths

    name = product.getName(projectPath)
    version = product.getVersion(projectPath, buildNumber)

    externals = sum([product.getExternals(project) for project in projectPaths], [])
    
    print("Projects:")
    print(projectPaths)
    print("Externals:")
    print(externals)

    output = "{}/bin/package/{}".format(outputRoot, name)
    print("Packing '{}' version '{}' to output path '{}'".format(name, version, output))

    zipfilename = "{}/{}-v{}.zip".format(output, name, version)

    os.makedirs(output, exist_ok=True)
    with zipfile.ZipFile(zipfilename, 'w') as zipObj:
        for project in projectPaths:
            projectName = product.getName(project)
            outputPath = "{}/bin/builds/{}/Release".format(outputRoot, projectName)
            print("Adding project '{}' to zip from '{}'".format(projectName, outputPath))
            
            addFileToZip(zipObj, "{}/{}.runtimeconfig.json".format(outputPath, projectName), "")
            #addFileToZip(zipObj, "{}/{}.deps.json"         .format(outputPath, projectName), "")
            addFileToZip(zipObj, "{}/{}.dll"               .format(outputPath, projectName), "")
            addFileToZip(zipObj, "{}/{}.exe"               .format(outputPath, projectName), "")

            projectExternals = product.getExternals(project)
            addExternal(projectExternals, zipObj, outputPath)
            addExternal(projectExternals, zipObj, "../{}".format(project))
        addExternal(externals, zipObj, outputRoot)
        
        #Add readme and releasenotes
        print("Adding extra files to zip")
        addFileToZip(zipObj, "./../Readme-TypeO.txt", "")
        addFileToZip(zipObj, "./../{}/ReleaseNotes-{}.txt".format(projectPath, name), "")
        addFileToZip(zipObj, "./../{}/product".format(projectPath), "")
    return zipfilename

def addExternal(externals, zipObj, path):
    for external in externals:
        externalPath = "{}/{}".format(path, external)
        if isdir(externalPath):
            print("Checking project external '{}' to zip".format(external))
        
        if isfile(externalPath):
            addFileToZip(zipObj, "{}".format(externalPath), "")
        
        if isdir(externalPath):
            for filename in os.listdir(externalPath):
                addFileToZip(zipObj, "{}/{}".format(externalPath, filename), "")

def addFileToZip(zipObj, filepath, pathTo):
    if isfile(filepath):
        filename = basename(filepath)
        filepathTo = "./{}/{}".format(pathTo, filename)
        print("... Adding file: {}".format(filepathTo))
        zipObj.write(filepath, filepathTo, zipfile.ZIP_DEFLATED)

if __name__ == "__main__":
    main()