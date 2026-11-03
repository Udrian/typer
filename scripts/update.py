import sys
from scripts import product
from scripts import list as listing

def parse(parser):
    parser.add_argument('-p', '--projectPath', type=str, required=True, help="Path to project")
    parser.add_argument('-n', '--name',        type=str, default="",   help="Name of the dependency to update, defaults to all TypeO dependencies")
    parser.add_argument('-v', '--version',     type=str, default="",   help="Version to update to, defaults to the latest release. Requires --name")

def withVersion(dependencyString, version):
    head, separator, tail = dependencyString.partition(";")
    name = head.partition("-")[0]
    return "{}-{}{}{}".format(name, version, separator, tail)

def updateDependencies(projectPath, name="", version=""):
    if version and not name:
        sys.exit("Error: a version can only be set for a named dependency")

    data = product.readJson(projectPath)
    dependencies = data.get("dependencies", [])
    messages = []
    found = False

    for i, dependencyString in enumerate(dependencies):
        dependency = product.Dependency(dependencyString)
        if name and dependency.name != name:
            continue
        found = True
        if dependency.nuget or dependency.local:
            if name:
                sys.exit("Error: '{}' is a {} dependency and can not be updated".format(name, "nuget" if dependency.nuget else "local"))
            continue

        target = version
        if not target:
            versions = listing.fetch(dependency.author, dependency.name)
            if versions is None:
                sys.exit("Error: could not fetch versions for '{}'".format(dependency.name))
            target = product.latestVersion([v["version"] for v in versions])
            if target is None or product.versionKey(target) <= product.versionKey(dependency.version):
                continue

        updated = withVersion(dependencyString, target)
        if updated != dependencyString:
            dependencies[i] = updated
            messages.append("Updated '{}' to '{}'".format(dependencyString, updated))

    if name and not found:
        sys.exit("Error: '{}' is not a dependency of this project".format(name))

    if messages:
        product.writeJson(projectPath, data)
    return messages

def do(args):
    messages = updateDependencies(args.projectPath, args.name, args.version)
    for message in messages:
        print(message)
    if messages:
        print("Run dependency to update the project references")
    else:
        print("Everything is up to date")
