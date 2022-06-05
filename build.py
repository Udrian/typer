import argparse, os, shutil
import product
 
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', '--projectPath', type=str, required=True,     help="Path to project to build")
    parser.add_argument('-b', '--buildNumber', type=int, required=True,     help="Build number to append to versioning")
    parser.add_argument('-c', '--config',      type=str, default="Release", help="Debug|Release defaults to Release")
    parser.add_argument('-o', '--output',      type=str, default="bin",     help="Output folder")
    args = parser.parse_args()

    build(args.projectPath, args.buildNumber, args.config, args.output)

def build(projectPath, buildNumber, config, outputRoot):
    name = product.getName(projectPath)
    version = product.getVersion(projectPath)
    output = "{}/build/{}/{}".format(outputRoot, name, config)
    print("Building '{}' '{}' '{}' to output '{}'".format(name, config, "{}.{}".format(version, buildNumber), output))

    csPath = "{}/{}/{}.csproj".format(projectPath, name, name)

    if os.path.exists(output):
        shutil.rmtree(output)
    os.system("dotnet publish {} --configuration {} --output {} --verbosity n /property:Version={}".format(csPath, config, output, "{}.{}".format(version, buildNumber)))

if __name__ == "__main__":
    main()