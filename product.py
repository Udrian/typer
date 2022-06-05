import json

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

    if "dependencies" in product:
        return product["dependencies"]
    return []