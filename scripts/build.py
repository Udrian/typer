import os, shutil
from scripts import product
 
def parse(parser):
    parser.add_argument('-p', '--projectPath', type=str, required=True,     help="Path to project")
    parser.add_argument('-b', '--buildNumber', type=int, required=True,     help="Build number to append to versioning")
    parser.add_argument('-c', '--config',      type=str, default="Release", help="Debug|Release defaults to Release", choices=["Debug", "Release"])
    parser.add_argument('-o', '--output',      type=str, default="bin",     help="Output folder")

def do(args):
    project = product.load(args.projectPath)

    build(project.name, args.output, args.config, args.buildNumber, project.version, args.projectPath)
    if project.haveDevModule:
        build(project.devModuleName, args.output, args.config, args.buildNumber, project.version, args.projectPath)

def build(name, output, config, buildNumber, version, projectPath):
    output = "{}/build/{}/{}".format(output, name, config)
    print("Building '{}' '{}' '{}' to output '{}'".format(name, config, "{}.{}".format(version, buildNumber), output))

    csPath = "{}/{}/{}.csproj".format(projectPath, name, name)

    if os.path.exists(output):
        shutil.rmtree(output)
    os.system("dotnet publish {} --configuration {} --output {} --verbosity n /property:Version={}".format(csPath, config, output, "{}.{}".format(version, buildNumber)))