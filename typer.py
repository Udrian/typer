from scripts import build, pack, upload, dependency
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

def main():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest='command')

    def AddParser(name, helpText):
        subparser = subparsers.add_parser(name, help=helpText)
        subparser.set_defaults(func=run_command)
        return subparser

    build.     parse(AddParser('build',      "BUILD help text"))
    pack.      parse(AddParser('pack',       "PACK help text"))
    upload.    parse(AddParser('upload',     "UPLOAD help text"))
    dependency.parse(AddParser('dependency', "DEPENDENCY help text"))
    
    args = parser.parse_args()
    if args.command is not None:
        args.func(parser, args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()