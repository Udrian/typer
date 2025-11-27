import os
from scripts import product
 
def parse(parser):
    parser.add_argument('-p', '--projectPath',        type=str, required=True,                help="Path to project")

def do(args):
    project = product.load(args.projectPath)

    branch = os.popen("cd {} && git branch --show-current".format(args.projectPath)).read().strip()
    tag = "{}{}".format(project.version, "" if branch in ["main", "master"] else ".{}".format(branch))

    os.system("cd {} && git tag -f {}".format(args.projectPath, tag))
    os.system("cd {} && git push -f origin {}".format(args.projectPath, tag))