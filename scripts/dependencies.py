import json
import os
from scripts import product

def parse(parser):
    parser.add_argument('-p', '--projectPath', type=str, required=True, help="Path to project")

def key(dependency):
    return (dependency.name, frozenset(dependency.projectTypes))

def localBase(projectPath):
    """Relative local paths are written from the folder of the project's main csproj (where typer runs when building)."""
    projects = product.readJson(projectPath).get("project", [])
    if projects:
        base = os.path.join(projectPath, projects[0]["Name"])
        if os.path.isdir(base):
            return base
    return projectPath

def dependencies(projectPath):
    """Returns the effective dependencies of a project, with the declared version and the local path of any override."""
    declared = {key(d): d for d in map(product.Dependency, product.readJson(projectPath).get("dependencies", []))}
    overridden = {key(d) for d in map(product.Dependency, product.readOverrides(projectPath))}

    retval = []
    for dependency in product.load(projectPath).dependencies:
        original = declared.get(key(dependency))
        retval.append({
            "name": dependency.name,
            "author": dependency.author,
            "version": original.version if original else dependency.version,
            "tags": dependency.projectTypes,
            "nuget": dependency.nuget,
            "overridden": key(dependency) in overridden,
            "localPath": os.path.normpath(os.path.join(localBase(projectPath), dependency.version)).replace("\\", "/") if dependency.local else ""
        })
    return retval

def do(args):
    print(json.dumps(dependencies(args.projectPath)))
