import os, sys
from scripts import product, cmd

def parse(parser):
    parser.add_argument('-p', '--projectPath', type=str, required=True, help="Path to project")
    parser.add_argument('-n', '--name',        type=str, required=True, help="Name of the project to remove")

def removeProject(projectPath, name):
    data = product.readJson(projectPath)
    projects = data.get("project", [])

    if not any(p["Name"] == name for p in projects):
        sys.exit("Error: project '{}' doesn't exist".format(name))
    if name == data["name"]:
        sys.exit("Error: can't remove the main project '{}'".format(name))
    dependents = [p["Name"] for p in projects if name in p.get("depends_on", [])]
    if dependents:
        sys.exit("Error: '{}' is still referenced by {}".format(name, ", ".join(dependents)))

    data["project"] = [p for p in projects if p["Name"] != name]
    product.writeJson(projectPath, data)

def removeFromSolution(projectPath, solutionName, name):
    slnFile = "{}/{}.sln".format(projectPath, solutionName)
    csProjFile = "{0}/{0}.csproj".format(name)
    if os.path.exists(slnFile):
        oldcwd = os.getcwd()
        os.chdir(projectPath)
        try:
            if cmd.exist("dotnet sln {}.sln list".format(solutionName), csProjFile):
                cmd.exec("dotnet sln {}.sln remove {}".format(solutionName, csProjFile))
        finally:
            os.chdir(oldcwd)

def do(args):
    removeProject(args.projectPath, args.name)
    removeFromSolution(args.projectPath, product.readJson(args.projectPath)["name"], args.name)
    print("Removed project '{}'. Its files on disk were left untouched".format(args.name))
