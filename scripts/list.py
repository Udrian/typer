from scripts import product
import requests
import json
 
def parse(parser):
    parser.add_argument('-a', '--authorName',  type=str, required=True, help="Name of author")
    parser.add_argument('-n', '--projectName', type=str, required=True, help="Name of project")

def do(args):
    list(args.authorName, args.projectName)

def list(author, project):
    url = "https://api.github.com/repos/{}/{}/tags".format(author, project)

    response = requests.get(url)
    if(not response.ok):
        return
    data = json.loads(response.content)
    
    retval = []
    for version in data:
        retval.append({"version": version["name"], "zip": version["zipball_url"]})
    
    print(json.dumps(retval))