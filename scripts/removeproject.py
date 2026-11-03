import os, sys
from scripts import product, cmd

def find_solution_file(projectPath, projectName):
    """Find the solution file, checking for both .sln and .slnx formats"""
    sln_path = "{}/{}.sln".format(projectPath, projectName)
    slnx_path = "{}/{}.slnx".format(projectPath, projectName)
    
    if os.path.exists(sln_path):
        return sln_path
    elif os.path.exists(slnx_path):
        return slnx_path
    else:
        return sln_path  # Default to .sln if neither exists

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
    slnFile = find_solution_file(projectPath, solutionName)
    csProjFile = "{0}/{0}.csproj".format(name)
    if os.path.exists(slnFile):
        oldcwd = os.getcwd()
        os.chdir(projectPath)
        try:
            # Use the actual solution filename
            if cmd.exist("dotnet sln {} list".format(os.path.basename(slnFile)), csProjFile):
                cmd.exec("dotnet sln {} remove {}".format(os.path.basename(slnFile), csProjFile))
        finally:
            os.chdir(oldcwd)

def do(args):
    removeProject(args.projectPath, args.name)
    removeFromSolution(args.projectPath, product.readJson(args.projectPath)["name"], args.name)
    print("Removed project '{}'. Its files on disk were left untouched".format(args.name))
