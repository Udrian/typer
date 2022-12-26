import os, shutil
from scripts import product
 
def parse(parser):
    parser.add_argument('-p', '--projectPath', type=str, required=True,     help="Path to project")
    parser.add_argument('-b', '--buildNumber', type=int, required=True,     help="Build number to append to versioning")
    parser.add_argument('-c', '--config',      type=str, default="Release", help="Debug|Release defaults to Release", choices=["Debug", "Release"])
    parser.add_argument('-o', '--output',      type=str, default="bin",     help="Output folder")

def do(args):
    project = product.load(args.projectPath)

    output = "{}/build/{}/{}".format(args.output, project.name, args.config)
    print("Building '{}' '{}' '{}' to output '{}'".format(project.name, args.config, "{}.{}".format(project.version, args.buildNumber), output))

    csPath = "{}/{}/{}.csproj".format(args.projectPath, project.name, project.name)

    if os.path.exists(output):
        shutil.rmtree(output)
    os.system("dotnet publish {} --configuration {} --output {} --verbosity n /property:Version={}".format(csPath, args.config, output, "{}.{}".format(project.version, args.buildNumber)))