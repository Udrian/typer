import json, os
from scripts import list as listing

def parse(parser):
    parser.add_argument('-r', '--registry', type=str, default="", help="Path to a json list of 'Author/Name' module repositories, defaults to modules.json next to typer.py")
    parser.add_argument('-e', '--extra', type=str, default="", help="Extra repositories added on top of the ones read from the registry")

def defaultRegistry():
    return os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "modules.json")

def modules(registryPath, extraRepositories):
    """Returns every registered module with its available versions, newest tag first as reported by GitHub."""
    with open(registryPath or defaultRegistry()) as f:
        entries = json.load(f)

    if extraRepositories:
        for repository in extraRepositories.split(", "):
            entries.append(repository)

    retval = []
    for entry in entries:
        delimiter = ""
        if entry.find('/') != -1:
            delimiter = "/"
        elif entry.find('@') != -1:
            delimiter = "@"
        if(delimiter == ""):
            continue

        author, name = entry.split(delimiter)
        versions = listing.fetch(author, name)
        retval.append({"author": author, "name": name, "versions": versions or []})
    return retval

def do(args):
    print(json.dumps(modules(args.registry, args.extra)))
