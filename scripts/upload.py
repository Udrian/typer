import boto3, os
from scripts import product, pack
 
def parse(parser):
    parser.add_argument('-p', '--projectPath',        type=str, required=True,                help="Path to project")
    parser.add_argument('-k', '--key',                type=str, required=True,                help="Space key")
    parser.add_argument('-s', '--secret',             type=str, required=True,                help="Space secret")
    parser.add_argument('-d', '--deploy_path_prefix', type=str,                default="",    help="deploy path configuration prefix")
    parser.add_argument('-o', '--output',             type=str,                default="bin", help="Output folder")

def do(args):
    project = product.load(args.projectPath)
    package_project = pack.getZipPathName(pack.getOutputPath(args.output, project.name), project.name, project.version)

    path = "typeo/releases{}{}/{}/{}".format(args.deploy_path_prefix, ("/modules" if product.getModule(args.projectPath) else ""), project.name, project.version)
    upload_package(args.key, args.secret, package_project, path)
    upload_package(args.key, args.secret, "{}/product".format(args.projectPath), path)
    upload_package(args.key, args.secret, "{}/ReleaseNotes-{}.txt".format(args.projectPath, project.name), path)

def upload_package(key, secret, package, dir):
    path = "{}/{}".format(dir, os.path.basename(package))

    upload(key, secret, "typedeaf", path, package)

def upload(key, secret, bucket, path, filename):
    print("Uploading '{}' to '{}'".format(filename, path))
    # Initialize a session using DigitalOcean Spaces.
    session = boto3.session.Session()
    client = session.client('s3',
                            region_name='nyc3',
                            endpoint_url='https://nyc3.digitaloceanspaces.com',
                            aws_access_key_id=key,
                            aws_secret_access_key=secret)

    client.upload_file(filename, bucket, path, ExtraArgs={'ACL':'public-read'})