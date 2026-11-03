import sys
from scripts import product

def parse(parser):
    parser.add_argument('-p', '--projectPath', type=str, required=True, help="Path to project")
    parser.add_argument('-n', '--name',        type=str, required=True, help="Name of the dependency to remove, for example 'TypeOCore' or 'MathNet.Numerics'")

def removeDependency(projectPath, name):
    data = product.readJson(projectPath)
    dependencies = data.get("dependencies", [])

    remaining = [d for d in dependencies if product.Dependency(d).name != name]
    if len(remaining) == len(dependencies):
        sys.exit("Error: '{}' is not a dependency of this project".format(name))

    data["dependencies"] = remaining
    product.writeJson(projectPath, data)
    return [d for d in dependencies if d not in remaining]

def do(args):
    for removed in removeDependency(args.projectPath, args.name):
        print("Removed '{}'".format(removed))
    print("Run dependency to update the project references")
