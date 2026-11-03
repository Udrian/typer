import json, os, re

def overrideKey(dependencyString):
    # A plain and a ;dev/;test entry for the same name are separate dependencies
    parts = dependencyString.split(";")
    tags = {p for p in parts[1:] if p in ("dev", "test")}
    return (parts[0].split("-")[0], frozenset(tags))

class Product:
    name = ""
    version = ""
    externals = []
    type = ""
    isModule = True
    haveDevModule = False
    devModuleName = ""
    dependencies = []
    haveTest = False
    testName = ""
    projects = []

    def __init__(self, product, projectPath):
        self.version = product["version"]
        self.name = product["name"]

        if "externals" in product:
            externals = []
            for externalString in product["externals"]:
                externals.append(External(externalString))
            self.externals = externals
        if "type" in product:
            self.type = product["type"]
            self.isModule = self.type == "module"
        self.projects = [SubProject(p) for p in product.get("project", [])]
        if not any(p.name == self.name for p in self.projects):
            self.projects.insert(0, SubProject({"Name": self.name}))
        for subProject in self.projects:
            if subProject.type == "dev" and not self.haveDevModule:
                self.haveDevModule = True
                self.devModuleName = subProject.name
            if subProject.type == "test" and not self.haveTest:
                self.haveTest = True
                self.testName = subProject.name

        dependencyOverridePath = "{}/typeo_override.json".format(projectPath)
        dependencyOverrides = []
        if os.path.exists(dependencyOverridePath):
            with open(dependencyOverridePath) as f:
                dependencyOverrides = json.load(f)

        dependencyStrings = []
        if "dependencies" in product:
            dependencyStrings = product["dependencies"]

        for dependencyOverride in dependencyOverrides:
            i = 0
            found = False
            for dependency in dependencyStrings:
                if overrideKey(dependency) == overrideKey(dependencyOverride):
                    dependencyStrings[i] = dependencyOverride
                    found = True
                    break
                i += 1
            if not found:
                dependencyStrings.append(dependencyOverride)
                
        dependencies = []
        for dependency in dependencyStrings:
            dependencies.append(Dependency(dependency))

        self.dependencies = dependencies

class SubProject:
    name = ""
    type = ""
    dependsOn = []

    def __init__(self, subProject):
        self.name = subProject["Name"]
        self.type = subProject.get("type", "")
        self.dependsOn = list(subProject.get("depends_on", []))

    @property
    def csprojPath(self):
        return "{0}/{0}.csproj".format(self.name)

class Dependency:
    name = ""
    author = ""
    version = ""
    local = False
    dev = False
    test = False
    nuget = False
    Params = []
    projectTypes = []

    def appliesTo(self, projectType, allProjectTypes=None):
        # Untagged dependencies go to every project, tagged ones to the project of that type.
        # The test project builds against everything.
        if projectType == "test" or not self.projectTypes:
            return True
        if projectType in self.projectTypes:
            return True
        return projectType == "" and self.usesMainAsDev(allProjectTypes)

    def usesMainAsDev(self, allProjectTypes):
        # Without a dev project, a ;dev module dependency is taken by the main project instead
        return bool(allProjectTypes is not None and not self.nuget and "dev" in self.projectTypes
                    and "dev" not in allProjectTypes)

    def __init__(self, dependencyString):
        # Only the first '-' separates name and version, local paths may contain more
        nameAuthor, separator, version = dependencyString.partition("-")
        if not separator:
            raise IndexError(dependencyString)
        if "@" in nameAuthor:
            self.author, self.name = nameAuthor.split("@", 1)
        else:
            self.name = nameAuthor
        self.version = version
        self.Params = []
        self.projectTypes = []
        if ";" in self.version:
            params = self.version.split(";")
            self.Params = params[1:]
            if "local" in self.Params:
                self.local = True
            if "nuget" in self.Params:
                self.nuget = True
            self.projectTypes = [p for p in self.Params if p not in ("local", "nuget")]
            self.dev = "dev" in self.projectTypes
            self.test = "test" in self.projectTypes
            self.version = params[0]

class External:
    path = ""
    test = False
    dev = False

    def __init__(self, externalString):
        if ";" in externalString:
            params = externalString.split(";")
            self.path = params[0]
            if "test" in params:
                self.test = True
            if "dev" in params:
                self.dev = True
        else:
            self.path = externalString

def readJson(projectPath):
    with open("{}/typeo.json".format(projectPath)) as f:
        return json.load(f)

def writeJson(projectPath, data):
    with open("{}/typeo.json".format(projectPath), "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def readOverrides(projectPath):
    path = "{}/typeo_override.json".format(projectPath)
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return json.load(f)

def writeOverrides(projectPath, overrides):
    with open("{}/typeo_override.json".format(projectPath), "w") as f:
        json.dump(overrides, f, ensure_ascii=False, indent=2)

def versionKey(version):
    return tuple(int(n) for n in re.findall(r"\d+", version))

def latestVersion(versions):
    """Returns the highest plain release version, ignoring branch tags such as '1.0.0.feature'."""
    releases = [v for v in versions if re.fullmatch(r"\d+(\.\d+)*", v)]
    return max(releases, key=versionKey) if releases else None

def load(projectPath):
    path = "{}/typeo.json".format(projectPath)
    with open(path) as f:
        product = json.load(f)
    return Product(product, projectPath)