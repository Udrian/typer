import sys
from scripts import product

def parse(parser):
    parser.add_argument('-p', '--projectPath', type=str, required=True, help="Path to project")
    parser.add_argument('-n', '--name',        type=str, required=True, help="Name of the dependency whose override should be removed")

def removeOverride(projectPath, name):
    overrides = product.readOverrides(projectPath)
    remaining = [o for o in overrides if product.Dependency(o).name != name]
    if len(remaining) == len(overrides):
        sys.exit("Error: '{}' has no override".format(name))

    product.writeOverrides(projectPath, remaining)
    return [o for o in overrides if o not in remaining]

def do(args):
    for removed in removeOverride(args.projectPath, args.name):
        print("Removed override '{}'".format(removed))
    print("Run dependency to update the project references")
