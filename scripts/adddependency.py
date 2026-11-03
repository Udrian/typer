import sys
from scripts import product

def parse(parser):
    parser.add_argument('-p', '--projectPath', type=str, required=True, help="Path to project")
    parser.add_argument('-d', '--dependency',  type=str, required=True, help="Dependency string, for example 'Udrian@TypeOCore-0.1.0', 'Udrian@TypeD-0.1.0;dev' or 'Pkg-1.0;nuget'")

def validate(dependencyString):
    try:
        dependency = product.Dependency(dependencyString)
    except IndexError:
        sys.exit("Error: '{}' is not a valid dependency, expected 'Author@Name-Version[;tag]'".format(dependencyString))
    if dependency.name == "" or dependency.version == "":
        sys.exit("Error: '{}' is not a valid dependency, expected 'Author@Name-Version[;tag]'".format(dependencyString))
    for tag in dependency.projectTypes:
        if tag not in ("dev", "test"):
            sys.exit("Error: unknown tag '{}', valid tags are dev, test, local and nuget".format(tag))
    return dependency

def addDependency(projectPath, dependencyString):
    dependency = validate(dependencyString)
    data = product.readJson(projectPath)
    dependencies = data.setdefault("dependencies", [])

    for i, existing in enumerate(dependencies):
        if product.Dependency(existing).name == dependency.name:
            dependencies[i] = dependencyString
            product.writeJson(projectPath, data)
            return "Replaced '{}' with '{}'".format(existing, dependencyString)

    dependencies.append(dependencyString)
    product.writeJson(projectPath, data)
    return "Added '{}'".format(dependencyString)

def do(args):
    print(addDependency(args.projectPath, args.dependency))
    print("Run dependency to update the project references")
