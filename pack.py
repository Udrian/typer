import argparse, os
import zipfile
import product
from os.path import basename
from os.path import isfile, isdir
 
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', '--projectPath', type=str, required=True,     help="Path to project to pack")
    parser.add_argument('-c', '--config',      type=str, default="Release", help="Debug|Release defaults to Release")
    parser.add_argument('-o', '--output',      type=str, default="bin",     help="Output folder")
    args = parser.parse_args()

    pack(args.projectPath, args.config, args.output)

def pack(projectPath, config, outputRoot):
    projectName = product.getName(projectPath)
    version = product.getVersion(projectPath)
    externals = product.getExternals(projectPath)
    
    output = "{}/package/{}".format(outputRoot, projectName)
    print("Packing '{}' version '{}' to output path '{}'".format(projectName, version, output))

    print("Externals:")
    print(externals)

    zipfilename = "{}/{}-{}.zip".format(output, projectName, version)

    os.makedirs(output, exist_ok=True)
    with zipfile.ZipFile(zipfilename, 'w') as zipObj:
        buildPath = "{}/build/{}/{}".format(outputRoot, projectName, config)
        print("Adding project '{}' to zip from '{}'".format(projectName, buildPath))
        
        addFileToZip(zipObj, "{}/{}.runtimeconfig.json".format(buildPath, projectName), "")
        #addFileToZip(zipObj, "{}/{}.deps.json"         .format(buildPath, projectName), "")
        addFileToZip(zipObj, "{}/{}.dll"               .format(buildPath, projectName), "")
        addFileToZip(zipObj, "{}/{}.exe"               .format(buildPath, projectName), "")
        addFileToZip(zipObj, "{}/{}.xml"               .format(buildPath, projectName), "")

        addExternal(externals, zipObj, buildPath)
        addExternal(externals, zipObj, "{}".format(projectPath))
        addExternal(externals, zipObj, "{}/{}".format(projectPath, projectName))
        
        #Add readme and releasenotes
        print("Adding extra files to zip")
        addFileToZip(zipObj, "{}/Readme-TypeO.txt".format(projectPath), "")
        addFileToZip(zipObj, "{}/ReleaseNotes-{}.txt".format(projectPath, projectName), "")
        addFileToZip(zipObj, "{}/product".format(projectPath), "")
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