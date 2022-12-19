import json, os

def loadProduct(projectPath):
    path = "{}/product".format(projectPath)
    with open(path) as f:
        product = json.load(f)
    return product

def getVersion(projectPath):
    product = loadProduct(projectPath)

    return product["version"]

def getExternals(projectPath):
    product = loadProduct(projectPath)

    if "externals" in product:
        return product["externals"]
    return []

def getName(projectPath):
    product = loadProduct(projectPath)

    return product["name"]

def getModule(projectPath):
    product = loadProduct(projectPath)

    if "type" in product:
        return product["type"] == "Module" or product["type"] == "TypeDModule"
    return True

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

def getDependencies(projectPath):
    product = loadProduct(projectPath)
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

    return dependencies