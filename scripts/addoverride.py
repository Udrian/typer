import os, sys
from scripts import product

def parse(parser):
    parser.add_argument('-p', '--projectPath', type=str, required=True, help="Path to project")
    parser.add_argument('-n', '--name',        type=str, required=True, help="Name of the dependency to override, for example 'TypeOCore'")
    parser.add_argument('-l', '--localPath',   type=str, required=True, help="Path to the local module to use instead")

def findDependency(projectPath, name):
    for dependencyString in product.readJson(projectPath).get("dependencies", []):
        dependency = product.Dependency(dependencyString)
        if dependency.name == name and not dependency.nuget:
            return dependency
    return None

def addOverride(projectPath, name, localPath):
    dependency = findDependency(projectPath, name)
    if dependency is None:
        sys.exit("Error: '{}' is not a TypeO dependency of this project".format(name))

    localPath = os.path.abspath(localPath).replace("\\", "/")
    if not os.path.isfile("{}/typeo.json".format(localPath)):
        sys.exit("Error: '{}' is not a TypeO project, typeo.json is missing".format(localPath))

    tags = "".join(";{}".format(t) for t in dependency.projectTypes)
    overrideString = "{}{}-{};local{}".format(
        "{}@".format(dependency.author) if dependency.author else "", dependency.name, localPath, tags)

    overrides = product.readOverrides(projectPath)
    key = product.overrideKey(overrideString)
    overrides = [o for o in overrides if product.overrideKey(o) != key]
    overrides.append(overrideString)
    product.writeOverrides(projectPath, overrides)
    return overrideString

def do(args):
    print("Added override '{}'".format(addOverride(args.projectPath, args.name, args.localPath)))
    print("Run dependency to update the project references")
