from scripts import product, moduleinfo
import requests
import json
import os
from datetime import datetime
 
def parse(parser):
    parser.add_argument('-a', '--authorName',  type=str, required=True, help="Name of author")
    parser.add_argument('-n', '--projectName', type=str, required=True, help="Name of project")

def do(args):
    list(args.authorName, args.projectName)

def fetch(author, project):
    cachepath = "{}/{}/{}/cache.json".format(moduleinfo.defaultCachePath(), author, project)

    if os.path.exists(cachepath):
        cachedata = json.loads(open(cachepath, "r").read())
        if cachedata["timestamp"] > datetime.now().timestamp() - 300:
            return cachedata["cache"]

    """Returns the tagged versions of a module as a list of version/zip dicts, or None if the request failed."""
    url = "https://api.github.com/repos/{}/{}/tags".format(author, project)

    response = requests.get(url)
    if(not response.ok):
        return None
    data = json.loads(response.content)

    result = [{"version": version["name"], "zip": version["zipball_url"]} for version in data]
    with open(cachepath, "w+") as cachefile:
        json.dump({"timestamp": datetime.now().timestamp(), "cache": result}, cachefile)
    return result

def list(author, project):
    versions = fetch(author, project)
    if versions is None:
        return

    print(json.dumps(versions))