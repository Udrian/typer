import sys
from scripts import product

def parse(parser):
    parser.add_argument('-p', '--projectPath', type=str, required=True,  help="Path to project")
    parser.add_argument('-n', '--name',        type=str, required=True,  help="Name of the project to add")
    parser.add_argument('-t', '--type',        type=str, default="",     help="Project type: '' (default), 'dev' or 'test'", choices=["", "dev", "test"])
    parser.add_argument('-d', '--depends_on',  type=str, nargs="*", default=[], help="Names of already added projects that this project should reference")

def addProject(projectPath, name, projectType, dependsOn):
    data = product.readJson(projectPath)
    projects = data.setdefault("project", [])
    if not any(p["Name"] == data["name"] for p in projects):
        projects.insert(0, {"Name": data["name"], "type": "", "depends_on": []})

    names = [p["Name"] for p in projects]
    if name in names:
        sys.exit("Error: project '{}' already exists".format(name))
    for dependency in dependsOn:
        if dependency not in names:
            sys.exit("Error: can't depend on unknown project '{}'".format(dependency))

    projects.append({"Name": name, "type": projectType, "depends_on": list(dict.fromkeys(dependsOn))})
    product.writeJson(projectPath, data)

def do(args):
    addProject(args.projectPath, args.name, args.type, args.depends_on)
    print("Added project '{}'. Run generate to create it".format(args.name))
