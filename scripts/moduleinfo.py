import json, os, sys
import requests

def parse(parser):
    parser.add_argument('-a', '--authorName',  type=str, required=True, help="Name of author")
    parser.add_argument('-n', '--projectName', type=str, required=True, help="Name of module")
    parser.add_argument('-v', '--version',     type=str, required=True, help="Version of the module")
    if os.name == 'nt':
        parser.add_argument('-c', '--cachePath', type=str, default="", help="Path to modules cache, defaults to '{{LOCALAPPDATA}}/TypeO/ModulesCache'")
    else:
        parser.add_argument('-c', '--cachePath', type=str, default="", help="Path to modules cache, defaults to '{{HOME}}/TypeO/ModulesCache'")

def defaultCachePath():
    if os.name == 'nt':
        return "{}/TypeO/ModulesCache".format(os.getenv('LOCALAPPDATA'))
    return "{}/TypeO/ModulesCache".format(os.getenv('HOME'))

def fetch(author, name, version, cachePath=""):
    """Returns the product description (typeo.json) of a module version, from the module cache or GitHub, or None if unavailable."""
    cached = os.path.join(cachePath or defaultCachePath(), author, name, version, "typeo.json")
    if os.path.exists(cached):
        with open(cached) as f:
            return json.load(f)

    url = "https://raw.githubusercontent.com/{}/{}/{}/typeo.json".format(author, name, version)
    response = requests.get(url)
    if not response.ok:
        return None
    return json.loads(response.content)

def do(args):
    info = fetch(args.authorName, args.projectName, args.version, args.cachePath)
    if info is None:
        sys.exit("Error: could not fetch typeo.json for '{}/{}-{}'".format(args.authorName, args.projectName, args.version))
    print(json.dumps(info))
