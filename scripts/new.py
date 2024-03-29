import os, json
from datetime import date
from scripts import product

def parse(parser):
    parser.add_argument('-n',  '--name',          type=str, required=True,       help="New project name")
    parser.add_argument('-o',  '--output',        type=str, required=True,       help="Output folder")
    parser.add_argument('-g',  '--git',           type=str,                      help="Existing git link to project")
    parser.add_argument(       '--disableGit',              action='store_true', help="Disables the use of git")
    parser.add_argument(       '--noCommit',                action='store_true', help="Do not ask for git commit input")
    parser.add_argument('-v',  '--version',       type=str, default="0.1.0",     help="Version of project to set, defaults to 0.1.0")
    parser.add_argument('-d',  '--dependencies',  type=str, default="",          help="List of project dependencies")
    parser.add_argument('-t',  '--type',          type=str, default="Module",    help="Sets project type, defaults to 'Module'", choices=["Module, Exe"])
    parser.add_argument(       '--clean',                   action='store_true', help="Creates a clean project with no code file template")
    parser.add_argument(       '--test',                    action='store_true', help="Add XUnit Test project")
    parser.add_argument(       '--testName',      type=str, default="",          help="Name for Test project")
    parser.add_argument(       '--dev',                     action='store_true', help="Add a TypeD Dev module")
    parser.add_argument(       '--devModuleName', type=str, default="",          help="Name for TypeD Dev module")

def cloneTyper(args):
    if not args.disableGit:
        if args.git is not None and not os.path.exists(".git"):
            os.system("git clone {} .".format(args.git))
        else:
            os.system("git init")

        if not os.path.exists("typer"):
            os.system("git submodule add https://github.com/Udrian/typer.git")
            commitAndPushMessage("Added submodule typer", args)
    else:
        if not os.path.exists("typer"):
            os.system("git clone https://github.com/Udrian/typer.git")

def addExtraFiles(args):
    if not args.disableGit:
        if not os.path.exists(".gitignore"):
            os.system("dotnet new gitignore")
        else:
            print("Appending to .gitignore")
        with open(".gitignore", "a+") as f:
            f.readlines
            f.writelines([
                "" if f.tell() == 0 else "\n",
                "# TypeO\n",
                "dependency_override\n",
                "*.sln\n",
                "*.csproj"
            ])

    CreateFileFromTemplate("dependency_override", "templates/dependency_override.template", {})
    
    dependencies = args.dependencies.split()
    if len(dependencies) == 0:
        dependencies.append("TypeOCore-0.1.0")
        if args.dev:
            dependencies.append("TypeD-0.1.0;dev")
    
    product = {
        "name": args.name,
        "version": args.version,
        "externals": [],
        "dependencies": dependencies,
        "type" : args.type
    }
    if args.dev:
        if args.devModuleName == "":
            product["devModuleName"] = "TypeD{}".format(args.name.removeprefix("TypeO"))
        else:
            product["devModuleName"] = args.devModuleName
    if args.test:
        if args.testName == "":
            product["testName"] = "{}Test".format(args.name)
        else:
            product["testName"] = args.testName
    CreateFile("product", json.dumps(product, ensure_ascii=False, indent=4))

    CreateFileFromTemplate("Readme-TypeO.txt", "templates/Readme-TypeO.template", {})

    CreateFileFromTemplate("ReleaseNotes-{}.txt".format(args.name), "templates/ReleaseNotes.template", {
        "version": args.version,
        "day": date.today().day,
        "month": date.today().month,
        "year": str(date.today().year)[0:2]
    })
    
    CreateFileFromTemplate("create_project_files.bat", "templates/create_project_files.template", {})

def createCodeFiles(project):
    CreateFileFromTemplate("{}/{}Module.cs".format(project.name, project.name), "templates/code/Module.template", {
        "name": project.name
    })

    CreateFileFromTemplate("{}/{}ModuleOption.cs".format(project.name, project.name), "templates/code/ModuleOption.template", {
        "name": project.name
    })

def createCodeTestFiles(project):
    CreateFileFromTemplate("{}/{}ModuleTest.cs".format(project.testName, project.name), "templates/codetest/ModuleTest.template", {
        "name":     project.name,
        "testName": project.testName
    })

    CreateFileFromTemplate("{}/Usings.cs".format(project.testName), "templates/codetest/Usings.template", {})

def createCodeTypeDTestFiles(project):
    CreateFileFromTemplate("{}/TypeDMock.cs".format(project.testName), "templates/codetest/TypeDMock.template", {
        "testName": project.testName
    })

    CreateFileFromTemplate("{}/{}ModuleTest.cs".format(project.testName, project.devModuleName), "templates/codetest/TypeDModuleTest.template", {
        "testName": project.testName,
        "devModuleName": project.devModuleName
    })

def createCodeTypeDFiles(project):
    CreateFileFromTemplate("{}/{}Initializer.cs".format(project.devModuleName, project.devModuleName), "templates/codetyped/Initializer.template", {
        "devModuleName": project.devModuleName
    })

def CreateFile(file, content):
    if not os.path.exists(file):
        print("Creating '{}'".format(file))
        with open(file, "w") as f:
            f.write(content)

def CreateFileFromTemplate(file, templateFile, content):
    templateFile = "{}/{}".format(os.path.dirname(os.path.realpath(__file__)), templateFile)
    if not os.path.exists(templateFile):
        print("Can't find template '{}'".format(templateFile))
        return
    if not os.path.exists(file):
        print("Creating '{}' from template '{}'".format(file, templateFile))
        with open(templateFile, "r") as t:
            template = t.read()
            for key in content:
                template = template.replace("{{{{{}}}}}".format(key), str(content[key]))
            with open(file, "w") as f:
                f.write(template)

def do(args):
    projectPath = "{}/{}".format(args.output, args.name.lower())
    os.makedirs(projectPath, exist_ok=True)
    os.chdir(projectPath)

    cloneTyper(args)
    addExtraFiles(args)

    os.system("create_project_files.bat")
    os.system("py typer/typer.py dependency -p .")

    if not args.clean:
        project = product.load(projectPath)
        createCodeFiles(project)
        if args.dev:
            createCodeTypeDFiles(project)
        if args.test:
            createCodeTestFiles(project)
            if args.dev:
                createCodeTypeDTestFiles(project)

    if not args.disableGit:
        os.system("git add .")
        commitAndPushMessage("Initial commit", args)

def commitAndPushMessage(default, args):
    if args.noCommit:
        return
    os.system("git status")
    answer = input("Do you want to commit and push?\n")
    if(answer.lower() in ("y", "yes")):
        commitmsg = input("Commit message [{}]".format(default))
        commitmsg = commitmsg or default
        os.system("git commit -m \"{}\"".format(commitmsg))
        os.system("git push")