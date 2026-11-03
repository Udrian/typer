import unittest
from xml.dom import minidom

from scripts import xmler
from tests.support import CSPROJ, TempDirTestCase, parseXml


class XmlerTests(unittest.TestCase):
    def test_get_element_with_name_returns_first_match(self):
        xml = parseXml()
        self.assertEqual(xmler.getElementWithName(xml, "TargetFramework").firstChild.data, "net8.0")

    def test_get_element_with_name_raises_when_missing(self):
        with self.assertRaises(IndexError):
            xmler.getElementWithName(parseXml(), "Missing")

    def test_get_element_with_no_attribute_skips_attributed_elements(self):
        xml = parseXml("<Project><ItemGroup Label='x'/><ItemGroup><A/></ItemGroup></Project>")
        group = xmler.getElementWithNameAndNoAttribute(xml, "ItemGroup")
        self.assertEqual(len(group.getElementsByTagName("A")), 1)

    def test_get_element_with_no_attribute_returns_zero_when_none(self):
        xml = parseXml("<Project><ItemGroup Label='x'/></Project>")
        self.assertEqual(xmler.getElementWithNameAndNoAttribute(xml, "ItemGroup"), 0)

    def test_create_element_adds_to_document_root(self):
        xml = parseXml()
        xmler.createElement(xml, xml, "Foo", "bar")
        foo = xml.getElementsByTagName("Foo")[0]
        self.assertEqual(foo.firstChild.data, "bar")
        self.assertIs(foo.parentNode, xml.documentElement)

    def test_create_element_adds_to_given_element(self):
        xml = parseXml()
        group = xmler.getElementWithName(xml, "PropertyGroup")
        xmler.createElement(xml, group, "Foo", "bar")
        self.assertIs(xml.getElementsByTagName("Foo")[0].parentNode, group)

    def test_get_or_create_with_value_creates_missing(self):
        xml = parseXml()
        group = xmler.getElementWithName(xml, "PropertyGroup")
        xmler.getOrCreateElementWithValue(xml, group, "GenerateDocumentationFile", "true")
        created = group.getElementsByTagName("GenerateDocumentationFile")
        self.assertEqual(len(created), 1)
        self.assertEqual(created[0].firstChild.data, "true")

    def test_get_or_create_with_value_does_not_duplicate(self):
        xml = parseXml()
        group = xmler.getElementWithName(xml, "PropertyGroup")
        xmler.getOrCreateElementWithValue(xml, group, "GenerateDocumentationFile", "true")
        found = xmler.getOrCreateElementWithValue(xml, group, "GenerateDocumentationFile", "true")
        self.assertEqual(len(group.getElementsByTagName("GenerateDocumentationFile")), 1)
        self.assertEqual(found.firstChild.data, "true")

    def test_get_or_create_with_value_creates_when_value_differs(self):
        xml = parseXml()
        group = xmler.getElementWithName(xml, "PropertyGroup")
        xmler.getOrCreateElementWithValue(xml, group, "Nullable", "disable")
        self.assertEqual(len(group.getElementsByTagName("Nullable")), 2)

    def test_set_element_with_value(self):
        xml = parseXml()
        xmler.setElementWithValue(xml, "TargetFramework", "net9.0")
        self.assertEqual(xml.getElementsByTagName("TargetFramework")[0].firstChild.data, "net9.0")

    def test_get_or_create_with_attribute_creates_under_root(self):
        xml = parseXml()
        group = xmler.getOrCreateElementWithAttribute(xml, xml, "ItemGroup", "Label", "TypeOModules")
        self.assertEqual(group.getAttribute("Label"), "TypeOModules")
        self.assertIs(group.parentNode, xml.documentElement)

    def test_get_or_create_with_attribute_is_idempotent(self):
        xml = parseXml()
        first = xmler.getOrCreateElementWithAttribute(xml, xml, "ItemGroup", "Label", "TypeOModules")
        second = xmler.getOrCreateElementWithAttribute(xml, xml, "ItemGroup", "Label", "TypeOModules")
        self.assertIs(first, second)
        self.assertEqual(len(xml.getElementsByTagName("ItemGroup")), 1)

    def test_get_or_create_with_attributes_requires_all_to_match(self):
        xml = parseXml()
        a = xmler.getOrCreateElementWithAttributes(xml, xml, "Target", [
            {"name": "Name", "value": "PreBuild"}, {"name": "BeforeTargets", "value": "PreBuildEvent"}])
        b = xmler.getOrCreateElementWithAttributes(xml, xml, "Target", [
            {"name": "Name", "value": "PreBuild"}, {"name": "BeforeTargets", "value": "Other"}])
        self.assertIsNot(a, b)
        self.assertEqual(len(xml.getElementsByTagName("Target")), 2)

    def test_get_or_create_with_attributes_under_element(self):
        xml = parseXml()
        group = xmler.getElementWithName(xml, "PropertyGroup")
        child = xmler.getOrCreateElementWithAttributes(xml, group, "Exec", [{"name": "Command", "value": "x"}])
        self.assertIs(child.parentNode, group)

    def test_delete_element(self):
        xml = parseXml()
        group = xmler.getElementWithName(xml, "PropertyGroup")
        xmler.deleteElement(group, "Nullable")
        self.assertEqual(group.getElementsByTagName("Nullable"), [])
        self.assertEqual(len(group.getElementsByTagName("TargetFramework")), 1)

    def test_delete_missing_element_is_a_no_op(self):
        xml = parseXml()
        group = xmler.getElementWithName(xml, "PropertyGroup")
        xmler.deleteElement(group, "Missing")
        self.assertEqual(len(group.getElementsByTagName("TargetFramework")), 1)

    def test_add_appends_to_root(self):
        xml = parseXml()
        element = xml.createElement("Target")
        xmler.add(xml, element)
        self.assertIs(element.parentNode, xml.documentElement)

    def test_add_moves_existing_element_instead_of_duplicating(self):
        xml = parseXml()
        element = xml.createElement("Target")
        xmler.add(xml, element)
        xmler.add(xml, element)
        self.assertEqual(len(xml.getElementsByTagName("Target")), 1)


class XmlerFileTests(TempDirTestCase):
    def test_load_parses_file(self):
        path = self.write("a.csproj", CSPROJ)
        xml = xmler.load(path)
        self.assertEqual(xml.documentElement.tagName, "Project")

    def test_load_missing_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            xmler.load(self.path("missing.csproj"))

    def test_save_roundtrip(self):
        path = self.write("a.csproj", CSPROJ)
        xml = xmler.load(path)
        xmler.createElement(xml, xml.getElementsByTagName("PropertyGroup")[0], "Foo", "bar")
        xmler.save(xml, path)
        reloaded = minidom.parse(path)
        self.assertEqual(reloaded.getElementsByTagName("Foo")[0].firstChild.data, "bar")
        self.assertEqual(reloaded.getElementsByTagName("TargetFramework")[0].firstChild.data, "net8.0")

    def test_save_has_no_blank_lines(self):
        path = self.write("a.csproj", CSPROJ)
        xmler.save(xmler.load(path), path)
        self.assertTrue(all(line.strip() for line in self.read("a.csproj").splitlines()))

    def test_save_unescapes_ampersand(self):
        path = self.write("a.csproj", CSPROJ)
        xml = xmler.load(path)
        element = xml.createElement("Exec")
        element.setAttribute("Command", "&quot;x&quot;")
        xml.documentElement.appendChild(element)
        xmler.save(xml, path)
        self.assertIn('Command="&quot;x&quot;"', self.read("a.csproj"))
        self.assertNotIn("&amp;", self.read("a.csproj"))


if __name__ == "__main__":
    unittest.main()
