import json, os

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

    def __init__(self, product, projectPath):
        self.version = product["version"]
        self.name = product["name"]

        if "externals" in product:
            self.externals = product["externals"]
        if "type" in product:
            self.type = product["type"]
            self.isModule = self.type == "Module"
        if "devModuleName" in product and product["devModuleName"] != "":
            self.haveDevModule = True
            self.devModuleName = product["devModuleName"]
        if "testName" in product and product["testName"] != "":
            self.haveTest = True
            self.testName = product["testName"]

        dependencyOverridePath = "{}/dependency_override".format(projectPath)
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
                if dependency.split("-")[0] == dependencyOverride.split("-")[0]:
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

class Dependency:
    name = ""
    version = ""
    local = False
    dev = False
    Params = []

    def __init__(self, dependencyString):
        self.name = dependencyString.split("-")[0]
        self.version = dependencyString.split("-")[1]
        self.Params = []
        if ";" in self.version:
            params = self.version.split(";")
            self.Params = params[1:]
            if "dev" in self.Params:
                self.dev = True
            if "local" in self.Params:
                self.local = True
            self.version = params[0]

def load(projectPath):
    path = "{}/product".format(projectPath)
    with open(path) as f:
        product = json.load(f)
    return Product(product, projectPath)