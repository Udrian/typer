from scripts import build, pack, upload, dependency, new, generate, list, addproject, removeproject, adddependency, removedependency, modules, moduleinfo, dependencies, update, addoverride, removeoverride
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
    elif args.command == 'list':
        list.do(args)
    elif args.command == 'addproject':
        addproject.do(args)
    elif args.command == 'removeproject':
        removeproject.do(args)
    elif args.command == 'adddependency':
        adddependency.do(args)
    elif args.command == 'removedependency':
        removedependency.do(args)
    elif args.command == 'modules':
        modules.do(args)
    elif args.command == 'moduleinfo':
        moduleinfo.do(args)
    elif args.command == 'dependencies':
        dependencies.do(args)
    elif args.command == 'update':
        update.do(args)
    elif args.command == 'addoverride':
        addoverride.do(args)
    elif args.command == 'removeoverride':
        removeoverride.do(args)

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
    list.      parse(AddParser('list',       "List all versions for a module"))
    addproject.parse(AddParser('addproject', "Adds a project to the project list in typeo.json"))
    removeproject.parse(AddParser('removeproject', "Removes a project from the project list in typeo.json"))
    adddependency.parse(AddParser('adddependency', "Adds a dependency to typeo.json"))
    removedependency.parse(AddParser('removedependency', "Removes a dependency from typeo.json"))
    modules.   parse(AddParser('modules',    "Lists all registered modules and their versions as json"))
    moduleinfo.parse(AddParser('moduleinfo', "Prints the product description (typeo.json) of a module version as json"))
    dependencies.parse(AddParser('dependencies', "Lists the dependencies of a project as json"))
    update.    parse(AddParser('update',     "Updates dependencies in typeo.json to the latest or a given version"))
    addoverride.parse(AddParser('addoverride', "Overrides a dependency with a local module in typeo_override.json"))
    removeoverride.parse(AddParser('removeoverride', "Removes a dependency override from typeo_override.json"))
    
    args = parser.parse_args()
    if args.command is not None:
        args.func(parser, args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()