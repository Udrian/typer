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

def getDependencies(projectPath):
    product = loadProduct(projectPath)
    dependencyOverridePath = "{}/dependency_override".format(projectPath)
    dependencyOverrides = []
    if os.path.exists(dependencyOverridePath):
        with open(dependencyOverridePath) as f:
            dependencyOverrides = json.load(f)

    dependencies = []
    if "dependencies" in product:
        dependencies = product["dependencies"]

    for dependencyOverride in dependencyOverrides:
        i = 0
        found = False
        for dependency in dependencies:
            if dependency.split("-")[0] == dependencyOverride.split("-")[0]:
                dependencies[i] = dependencyOverride
                found = True
                break
            i += 1
        if not found:
            dependencies.append(dependencyOverride)
            
    return dependencies