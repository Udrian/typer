from scripts import product
import requests
import json
 
def parse(parser):
    parser.add_argument('-a', '--authorName',  type=str, required=True, help="Name of author")
    parser.add_argument('-n', '--projectName', type=str, required=True, help="Name of project")

def do(args):
    list(args.authorName, args.projectName)

def fetch(author, project):
    """Returns the tagged versions of a module as a list of version/zip dicts, or None if the request failed."""
    url = "https://api.github.com/repos/{}/{}/tags".format(author, project)

    response = requests.get(url)
    if(not response.ok):
        return None
    data = json.loads(response.content)

    return [{"version": version["name"], "zip": version["zipball_url"]} for version in data]

def list(author, project):
    versions = fetch(author, project)
    if versions is None:
        return

    print(json.dumps(versions))