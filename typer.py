from scripts import build, pack, upload, dependency, new, generate, install
import argparse

def run_command(parser, args):
    if args.command == 'build':
        build.do(args)
    elif args.command == 'pack':
        pack.do(args)
    elif args.command == 'upload':
        upload.do(args)
    elif args.command == 'dependency':
        dependency.do(args)
    elif args.command == 'new':
        new.do(args)
    elif args.command == 'generate':
        generate.do(args)
    elif args.command == 'install':
        install.do(args)

def main():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest='command')

    def AddParser(name, helpText):
        subparser = subparsers.add_parser(name, help=helpText)
        subparser.set_defaults(func=run_command)
        return subparser

    build.     parse(AddParser('build',      "Builds the specified projects"))
    pack.      parse(AddParser('pack',       "Packs the specified project to a zip"))
    upload.    parse(AddParser('upload',     "Upload the specified project"))
    dependency.parse(AddParser('dependency', "Downloads dependencies for project and add them to the project solution/proj files"))
    new.       parse(AddParser('new',        "Helper for creating and setting up a new clean project"))
    generate.  parse(AddParser('generate',   "Helper for generating Project and Solution"))
    install.   parse(AddParser('install',    "Sets Typer to path"))
    
    args = parser.parse_args()
    if args.command is not None:
        args.func(parser, args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()