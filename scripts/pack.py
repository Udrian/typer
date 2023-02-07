import os, zipfile
from os.path import basename
from os.path import isfile, isdir
from scripts import product
 
def parse(parser):
    parser.add_argument('-p', '--projectPath', type=str, required=True,     help="Path to project")
    parser.add_argument('-c', '--config',      type=str, default="Release", help="Debug|Release defaults to Release", choices=["Debug", "Release"])
    parser.add_argument('-o', '--output',      type=str, default="bin",     help="Output folder")

def do(args):
    project = product.load(args.projectPath)
    
    output = getOutputPath(args.output, project.name)
    pack(project.name, output, project, args)
    if project.haveDevModule:
        pack(project.devModuleName, output, project, args)

def pack(name, output, project, args):
    print("Packing '{}' version '{}' to output path '{}'".format(name, project.version, output))

    print("Externals:")
    print(project.externals)

    zipfilename = getZipPathName(output, name, project.version)

    os.makedirs(output, exist_ok=True)
    with zipfile.ZipFile(zipfilename, 'w') as zipObj:
        buildPath = "{}/build/{}/{}".format(args.output, name, args.config)
        print("Adding project '{}' to zip from '{}'".format(name, buildPath))
        
        addFileToZip(zipObj, "{}/{}.runtimeconfig.json".format(buildPath, name), "")
        #addFileToZip(zipObj, "{}/{}.deps.json"         .format(buildPath, name), "")
        addFileToZip(zipObj, "{}/{}.dll"               .format(buildPath, name), "")
        addFileToZip(zipObj, "{}/{}.exe"               .format(buildPath, name), "")
        addFileToZip(zipObj, "{}/{}.xml"               .format(buildPath, name), "")

        print("Adding external files to zip")
        addExternal(project.externals, zipObj, buildPath)
        addExternal(project.externals, zipObj, "{}".format(args.projectPath))
        addExternal(project.externals, zipObj, "{}/{}".format(args.projectPath, name))
        
        for external in project.externals:
            print("Could not find external file: '{}'".format(external))

        #Add readme and releasenotes
        print("Adding extra files to zip")
        addFileToZip(zipObj, "{}/Readme-TypeO.txt".format(args.projectPath), "")
        addFileToZip(zipObj, "{}/ReleaseNotes-{}.txt".format(args.projectPath, name), "")
        addFileToZip(zipObj, "{}/product".format(args.projectPath), "")

def addExternal(externals, zipObj, path):
    for external in externals.copy():
        externalPath = "{}/{}".format(path, external)
        if isdir(externalPath):
            print("Checking project external '{}' to zip".format(external))
        
        if isfile(externalPath):
            if addFileToZip(zipObj, "{}".format(externalPath), ""):
                externals.remove(external)
        
        if isdir(externalPath):
            for filename in os.listdir(externalPath):
                if addFileToZip(zipObj, "{}/{}".format(externalPath, filename), ""):
                    externals.remove(external)

def addFileToZip(zipObj, filepath, pathTo):
    if isfile(filepath):
        filename = basename(filepath)
        filepathTo = "./{}/{}".format(pathTo, filename)
        print("... Adding file: {}".format(filepathTo))
        zipObj.write(filepath, filepathTo, zipfile.ZIP_DEFLATED)
        return True
    return False

def getOutputPath(output, projectName):
    return "{}/package/{}".format(output, projectName)

def getZipPathName(output, projectName, version):
    return "{}/{}-{}.zip".format(output, projectName, version)