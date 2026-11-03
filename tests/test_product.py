import json, unittest

from scripts import product
from tests.support import TempDirTestCase


class DependencyTests(unittest.TestCase):
    def test_author_name_and_version(self):
        dep = product.Dependency("Udrian@TypeOCore-0.1.0.dev")
        self.assertEqual(dep.author, "Udrian")
        self.assertEqual(dep.name, "TypeOCore")
        self.assertEqual(dep.version, "0.1.0.dev")
        self.assertEqual(dep.Params, [])
        self.assertFalse(dep.dev or dep.test or dep.local or dep.nuget)

    def test_without_author(self):
        dep = product.Dependency("TypeD-0.1.0")
        self.assertEqual(dep.author, "")
        self.assertEqual(dep.name, "TypeD")
        self.assertEqual(dep.version, "0.1.0")

    def test_params_are_parsed_and_removed_from_version(self):
        dep = product.Dependency("Udrian@TypeD-0.1.0.dev;dev")
        self.assertEqual(dep.version, "0.1.0.dev")
        self.assertEqual(dep.Params, ["dev"])
        self.assertTrue(dep.dev)
        self.assertFalse(dep.test or dep.local or dep.nuget)

    def test_multiple_params(self):
        dep = product.Dependency("MessageBox.Avalonia-12.1.0;nuget;dev")
        self.assertEqual(dep.name, "MessageBox.Avalonia")
        self.assertEqual(dep.version, "12.1.0")
        self.assertTrue(dep.nuget)
        self.assertTrue(dep.dev)
        self.assertFalse(dep.test or dep.local)

    def test_test_and_local_params(self):
        dep = product.Dependency("Foo-somepath;local;test")
        self.assertTrue(dep.local)
        self.assertTrue(dep.test)
        self.assertEqual(dep.version, "somepath")

    def test_instances_do_not_share_params(self):
        a = product.Dependency("A-1;dev")
        b = product.Dependency("B-1")
        self.assertEqual(a.Params, ["dev"])
        self.assertEqual(b.Params, [])


class ExternalTests(unittest.TestCase):
    def test_plain_path(self):
        ext = product.External("Shaders/a.frag")
        self.assertEqual(ext.path, "Shaders/a.frag")
        self.assertFalse(ext.test or ext.dev)

    def test_test_flag(self):
        ext = product.External("Mock/texture.png;test")
        self.assertEqual(ext.path, "Mock/texture.png")
        self.assertTrue(ext.test)
        self.assertFalse(ext.dev)

    def test_dev_and_test_flags(self):
        ext = product.External("x.txt;dev;test")
        self.assertTrue(ext.dev and ext.test)


class ProductTests(TempDirTestCase):
    def make(self, data, override=None):
        if override is not None:
            self.write("typeo_override.json", json.dumps(override))
        return product.Product(data, self.tmp)

    def test_minimal_product_defaults(self):
        p = self.make({"name": "Foo", "version": "1.2.3"})
        self.assertEqual(p.name, "Foo")
        self.assertEqual(p.version, "1.2.3")
        self.assertEqual(p.type, "")
        self.assertTrue(p.isModule)
        self.assertFalse(p.haveDevModule)
        self.assertFalse(p.haveTest)
        self.assertEqual(p.dependencies, [])
        self.assertEqual(p.externals, [])

    def test_name_and_version_are_required(self):
        with self.assertRaises(KeyError):
            self.make({"version": "1"})
        with self.assertRaises(KeyError):
            self.make({"name": "Foo"})

    def test_type_exe_is_not_module(self):
        p = self.make({"name": "Foo", "version": "1", "type": "exe"})
        self.assertEqual(p.type, "exe")
        self.assertFalse(p.isModule)

    def test_type_module_is_module(self):
        p = self.make({"name": "Foo", "version": "1", "type": "module"})
        self.assertTrue(p.isModule)

    def test_projects_list_sets_dev_and_test(self):
        p = self.make({"name": "Foo", "version": "1", "project": [
            {"Name": "Foo", "type": ""},
            {"Name": "TypeDFoo", "type": "dev"},
            {"Name": "FooTest", "type": "test"},
        ]})
        self.assertTrue(p.haveDevModule)
        self.assertEqual(p.devModuleName, "TypeDFoo")
        self.assertTrue(p.haveTest)
        self.assertEqual(p.testName, "FooTest")

    def test_projects_list_without_dev_or_test(self):
        p = self.make({"name": "Foo", "version": "1", "project": [
            {"Name": "Foo", "type": ""}
        ]})
        self.assertFalse(p.haveDevModule)
        self.assertEqual(p.devModuleName, "")
        self.assertFalse(p.haveTest)
        self.assertEqual(p.testName, "")

    def test_first_dev_and_first_test_project_win(self):
        p = self.make({"name": "Foo", "version": "1", "project": [
            {"Name": "D1", "type": "dev"},
            {"Name": "D2", "type": "dev"},
            {"Name": "T1", "type": "test"},
            {"Name": "T2", "type": "test"},
        ]})
        self.assertEqual(p.devModuleName, "D1")
        self.assertEqual(p.testName, "T1")

    def test_project_flags_are_optional(self):
        p = self.make({"name": "Foo", "version": "1", "project": [
            {"Name": "Foo"}, {"Name": "FooTest", "type": "test"}
        ]})
        self.assertFalse(p.haveDevModule)
        self.assertEqual(p.testName, "FooTest")

    def test_externals_become_external_objects(self):
        p = self.make({"name": "Foo", "version": "1", "externals": ["a.txt", "b.png;test"]})
        self.assertEqual([e.path for e in p.externals], ["a.txt", "b.png"])
        self.assertTrue(all(isinstance(e, product.External) for e in p.externals))
        self.assertTrue(p.externals[1].test)

    def test_dependencies_become_dependency_objects(self):
        p = self.make({"name": "Foo", "version": "1", "dependencies": [
            "Udrian@TypeOCore-0.1.0.dev", "OpenTK-4.9.4;nuget"
        ]})
        self.assertEqual([d.name for d in p.dependencies], ["TypeOCore", "OpenTK"])
        self.assertTrue(p.dependencies[1].nuget)

    def test_override_replaces_dependency_with_same_name(self):
        p = self.make({"name": "Foo", "version": "1", "dependencies": [
            "Udrian@TypeOCore-0.1.0.dev", "Other-1.0"
        ]}, override=["Udrian@TypeOCore-9.9.9;local"])
        self.assertEqual([d.name for d in p.dependencies], ["TypeOCore", "Other"])
        core = p.dependencies[0]
        self.assertEqual(core.version, "9.9.9")
        self.assertTrue(core.local)

    def test_override_appends_unknown_dependency(self):
        p = self.make({"name": "Foo", "version": "1", "dependencies": ["A-1.0"]},
                      override=["B-2.0"])
        self.assertEqual([d.name for d in p.dependencies], ["A", "B"])

    def test_override_applies_without_dependencies_key(self):
        p = self.make({"name": "Foo", "version": "1"}, override=["B-2.0"])
        self.assertEqual([d.name for d in p.dependencies], ["B"])

    def test_empty_override_changes_nothing(self):
        p = self.make({"name": "Foo", "version": "1", "dependencies": ["A-1.0"]}, override=[])
        self.assertEqual([d.name for d in p.dependencies], ["A"])

    def test_missing_override_file_is_ignored(self):
        p = self.make({"name": "Foo", "version": "1", "dependencies": ["A-1.0"]})
        self.assertEqual([d.name for d in p.dependencies], ["A"])

    def test_legacy_dependency_override_file_is_not_used(self):
        self.write("dependency_override", json.dumps(["B-2.0"]))
        p = self.make({"name": "Foo", "version": "1"})
        self.assertEqual(p.dependencies, [])


class LoadTests(TempDirTestCase):
    def test_load_reads_typeo_json(self):
        root = self.writeTypeO("", {
            "name": "Foo", "version": "0.1.0", "type": "module",
            "dependencies": ["Udrian@TypeOCore-0.1.0"],
            "project": [{"Name": "Foo", "type": ""},
                        {"Name": "FooTest", "type": "test"}]
        })
        p = product.load(root)
        self.assertEqual(p.name, "Foo")
        self.assertEqual(p.testName, "FooTest")
        self.assertEqual(p.dependencies[0].name, "TypeOCore")

    def test_load_applies_typeo_override_json(self):
        root = self.writeTypeO("", {"name": "Foo", "version": "1", "dependencies": ["A-1.0"]},
                               override=["A-2.0"])
        self.assertEqual(product.load(root).dependencies[0].version, "2.0")

    def test_load_missing_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            product.load(self.tmp)

    def test_load_ignores_legacy_product_file(self):
        self.write("product", json.dumps({"name": "Foo", "version": "1"}))
        with self.assertRaises(FileNotFoundError):
            product.load(self.tmp)

    def test_load_invalid_json_raises(self):
        self.write("typeo.json", "{ not json")
        with self.assertRaises(json.JSONDecodeError):
            product.load(self.tmp)



class SubProjectTests(unittest.TestCase):
    def test_defaults_and_depends_on(self):
        s = product.SubProject({"Name": "A"})
        self.assertEqual((s.name, s.type, s.dependsOn, s.csprojPath), ("A", "", [], "A/A.csproj"))
        s = product.SubProject({"Name": "B", "type": "dev", "depends_on": ["A"]})
        self.assertEqual((s.type, s.dependsOn), ("dev", ["A"]))

    def test_product_lists_all_projects_and_adds_missing_main(self):
        p = product.Product({"name": "Foo", "version": "1", "project": [
            {"Name": "X"}, {"Name": "Y", "type": "test", "depends_on": ["X"]}]}, ".")
        self.assertEqual([s.name for s in p.projects], ["Foo", "X", "Y"])
        self.assertEqual(p.testName, "Y")



class OverrideMergeTests(TempDirTestCase):
    def load(self, dependencies, overrides):
        self.writeTypeO(".", {"name": "Foo", "version": "1", "dependencies": dependencies}, override=overrides)
        return product.load(self.tmp)

    def test_plain_and_dev_entries_of_same_name_are_kept_separate(self):
        p = self.load(["A-1"], ["A-2", "A-2;dev"])
        self.assertEqual([(d.name, d.version, d.dev) for d in p.dependencies], [("A", "2", False), ("A", "2", True)])

    def test_override_replaces_entry_with_same_name_and_tags(self):
        p = self.load(["A-1", "A-1;dev"], ["A-9;dev"])
        self.assertEqual([(d.version, d.dev) for d in p.dependencies], [("1", False), ("9", True)])

    def test_local_and_nuget_tags_do_not_change_identity(self):
        p = self.load(["A-1"], ["A-../a;local"])
        self.assertEqual([(d.version, d.local) for d in p.dependencies], [("../a", True)])


if __name__ == "__main__":
    unittest.main()
