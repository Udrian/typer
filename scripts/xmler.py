from xml.dom import minidom

def getElementWithName(element, name):
    return element.getElementsByTagName(name)[0]

def getOrCreateElementWithValue(xml, element, name, content):
    retEl = 0
    for itemGroup in element.getElementsByTagName(name):
        if itemGroup.firstChild.data == content:
            retEl = itemGroup
            break
    if retEl == 0:
        createElement(xml, element, name, content)
    return retEl

def setElementWithValue(element, name, content):
    for itemGroup in element.getElementsByTagName(name):
        itemGroup.firstChild.data = content


def getOrCreateElementWithAttribute(xml, element, name, attribute, value):
    return getOrCreateElementWithAttributes(xml, element, name, [{"name": attribute, "value": value}])

def getOrCreateElementWithAttributes(xml, element, name, attributes):
    retEl = 0
    for itemGroup in element.getElementsByTagName(name):
        found = True
        for attribute in attributes:
            if not (itemGroup.hasAttribute(attribute["name"]) and itemGroup.getAttribute(attribute["name"]) == attribute["value"]):
                found = False
        if found:
            retEl = itemGroup
    if retEl == 0:
        retEl = xml.createElement(name)
    
        for attribute in attributes:
            retEl.setAttribute(attribute["name"], attribute["value"])
    
        if xml == element:
            element.childNodes[0].appendChild(retEl)
        else:
            element.appendChild(retEl)
    return retEl

def createElement(xml, element, name, content):
    retEl = xml.createElement(name)
    
    txt = xml.createTextNode(content)
    retEl.appendChild(txt)

    if xml == element:
        element.childNodes[0].appendChild(retEl)
    else:
        element.appendChild(retEl)

def add(xml, element):
    xml.childNodes[0].appendChild(element)

def load(path):
    return minidom.parse(path)

def save(xml, path):
    with open(path, "w") as fs:
        dom_string = xml.childNodes[0].toprettyxml()
        dom_string = dom_string.replace("&amp;", "&")

        dom_string = '\n'.join([s for s in dom_string.splitlines() if s.strip()])
        fs.write(dom_string)
        fs.close()