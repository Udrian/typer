import json, os
from scripts import list as listing

def parse(parser):
    parser.add_argument('-r', '--registry', type=str, default="",
                        help="Path to a json list of 'Author/Name' module repositories, defaults to modules.json next to typer.py")

def defaultRegistry():
    return os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "modules.json")

def modules(registryPath):
    """Returns every registered module with its available versions, newest tag first as reported by GitHub."""
    with open(registryPath or defaultRegistry()) as f:
        entries = json.load(f)

    retval = []
    for entry in entries:
        author, name = entry.split("/")
        versions = listing.fetch(author, name)
        retval.append({"author": author, "name": name, "versions": versions or []})
    return retval

def do(args):
    print(json.dumps(modules(args.registry)))
