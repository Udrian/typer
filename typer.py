import build, pack, upload, product
import argparse
import subprocess
import os.path

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-b',  '--buildNumber',        type=int,  required=True,     help="Build number to append to versioning")
    parser.add_argument('-o',  '--output',             type=str,  default="..",      help="Output folder")
    parser.add_argument('-p',  '--projectPath',        type=str,  required=True,     help="Path to project")
    parser.add_argument('-c',  '--config',             type=str,  default="Release", help="Debug|Release defaults to Release")
    parser.add_argument('-sb', '--skip_building',      type=bool, default=False,     help="Skip building")
    parser.add_argument('-sp', '--skip_packing',       type=bool, default=False,     help="Skip packing")
    parser.add_argument('-su', '--skip_uploading',     type=bool, default=False,     help="Skip uploading")
    parser.add_argument('-st', '--skip_tag',           type=bool, default=False,     help="Skip git tag")
    parser.add_argument('-k',  '--key',                type=str,  required=True,     help="Space key")
    parser.add_argument('-s',  '--secret',             type=str,  required=True,     help="Space secret")
    parser.add_argument('-d',  '--deploy_path_prefix', type=str,  default="",        help="deploy path configuration prefix")
    parser.add_argument('-t',  '--tag_commit_hash',    type=str,  default="develop", help="Git commit hash for tag")
    
    args = parser.parse_args()

    extraProjectPaths = product.getExtraProjects(args.projectPath)#!!
    projectPaths = [args.projectPath] + extraProjectPaths#!!

    if not args.skip_building:
        for project in projectPaths:
            build.build(project, args.buildNumber, args.config, args.output)
    
    if not args.skip_packing:
        package_project = pack.pack(args.projectPath, args.buildNumber, args.output)

        if not args.skip_uploading:
            version = product.getVersion(args.projectPath, args.buildNumber)
            path = "typeo/releases{}{}/{}/{}".format(args.deploy_path_prefix, ("/modules" if product.getModule(args.projectPath) else ""), product.getName(args.projectPath), version)
            upload_package(args.key, args.secret, package_project, path)
            upload_package(args.key, args.secret, "../{}/product".format(args.projectPath), path)
            projectName = product.getName(args.projectPath)
            upload_package(args.key, args.secret, "../{}/ReleaseNotes-{}.txt".format(args.projectPath, projectName), path)

    if not args.skip_tag:
        version = product.getVersion(args.projectPath, args.buildNumber)
        print("Tagging git commit with tag {}".format(version))

        try:
            subprocess.run(["git", "tag", "-a", "-f", "-m", version, version], check=True)
            subprocess.run(["git", "push", "origin", "-f", version], check=True)
        except subprocess.CalledProcessError as e:
            print(e.output)
            raise e

def upload_package(key, secret, package, dir):
    path = "{}/{}".format(dir, os.path.basename(package))

    upload.upload(key, secret, "typedeaf", path, package)

if __name__ == "__main__":
    main()