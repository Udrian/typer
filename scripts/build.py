import os, shutil
from scripts import product
 
def parse(parser):
    parser.add_argument('-p', '--projectPath', type=str, required=True,     help="Path to project")
    parser.add_argument('-b', '--buildNumber', type=int, required=True,     help="Build number to append to versioning")
    parser.add_argument('-c', '--config',      type=str, default="Release", help="Debug|Release defaults to Release", choices=["Debug", "Release"])
    parser.add_argument('-o', '--output',      type=str, default="bin",     help="Output folder")

def do(args):
    name = product.getName(args.projectPath)
    version = product.getVersion(args.projectPath)
    output = "{}/build/{}/{}".format(args.output, name, args.config)
    print("Building '{}' '{}' '{}' to output '{}'".format(name, args.config, "{}.{}".format(version, args.buildNumber), output))

    csPath = "{}/{}/{}.csproj".format(args.projectPath, name, name)

    if os.path.exists(output):
        shutil.rmtree(output)
    os.system("dotnet publish {} --configuration {} --output {} --verbosity n /property:Version={}".format(csPath, args.config, output, "{}.{}".format(version, args.buildNumber)))