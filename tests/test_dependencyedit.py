import argparse, json, os, unittest
from unittest import mock

from scripts import adddependency, removedependency
from tests.support import TempDirTestCase


def parser(module):
    p = argparse.ArgumentParser()
    module.parse(p)
    return p


class DependencyListTestCase(TempDirTestCase):
    def setUp(self):
        super().setUp()
        self.writeTypeO("proj", {"name": "Foo", "version": "1",
                                 "dependencies": ["Udrian@TypeOCore-0.1.0", "MathNet.Numerics-5.0.0;nuget"]})
        self.root = self.path("proj")

    def dependencies(self):
        with open(os.path.join(self.root, "typeo.json")) as f:
            return json.load(f)["dependencies"]


class AddDependencyTests(DependencyListTestCase):
    def test_parse(self):
        args = parser(adddependency).parse_args(["-p", "x", "-d", "A-1"])
        self.assertEqual((args.projectPath, args.dependency), ("x", "A-1"))
        for argv in (["-p", "x"], ["-d", "A-1"]):
            with self.assertRaises(SystemExit), mock.patch("sys.stderr"):
                parser(adddependency).parse_args(argv)

    def test_adds_typeo_dependency(self):
        adddependency.addDependency(self.root, "Udrian@TypeOTK-0.2.0.dev")
        self.assertEqual(self.dependencies()[-1], "Udrian@TypeOTK-0.2.0.dev")

    def test_adds_tagged_and_nuget_dependencies(self):
        adddependency.addDependency(self.root, "Udrian@TypeD-0.1.0;dev")
        adddependency.addDependency(self.root, "xunit-2.9.3;nuget;test")
        self.assertEqual(self.dependencies()[-2:], ["Udrian@TypeD-0.1.0;dev", "xunit-2.9.3;nuget;test"])

    def test_existing_name_is_replaced_in_place(self):
        message = adddependency.addDependency(self.root, "Udrian@TypeOCore-0.2.0")
        self.assertEqual(self.dependencies(), ["Udrian@TypeOCore-0.2.0", "MathNet.Numerics-5.0.0;nuget"])
        self.assertIn("Replaced", message)

    def test_missing_dependency_list_is_created(self):
        self.writeTypeO("bare", {"name": "Bare", "version": "1"})
        adddependency.addDependency(self.path("bare"), "A-1")
        with open(self.path("bare", "typeo.json")) as f:
            self.assertEqual(json.load(f)["dependencies"], ["A-1"])

    def test_invalid_dependencies_are_rejected_and_file_unchanged(self):
        before = self.dependencies()
        for bad in ("NoVersion", "A-1;bogus", "-1"):
            with self.assertRaises(SystemExit):
                adddependency.addDependency(self.root, bad)
        self.assertEqual(self.dependencies(), before)

    def test_other_fields_are_preserved(self):
        adddependency.addDependency(self.root, "A-1")
        with open(os.path.join(self.root, "typeo.json")) as f:
            data = json.load(f)
        self.assertEqual((data["name"], data["version"]), ("Foo", "1"))

    def test_do(self):
        adddependency.do(argparse.Namespace(projectPath=self.root, dependency="A-1"))
        self.assertIn("A-1", self.dependencies())


class RemoveDependencyTests(DependencyListTestCase):
    def test_parse(self):
        args = parser(removedependency).parse_args(["-p", "x", "-n", "TypeOCore"])
        self.assertEqual((args.projectPath, args.name), ("x", "TypeOCore"))
        with self.assertRaises(SystemExit), mock.patch("sys.stderr"):
            parser(removedependency).parse_args(["-p", "x"])

    def test_removes_by_name_ignoring_author_version_and_tags(self):
        removedependency.removeDependency(self.root, "TypeOCore")
        self.assertEqual(self.dependencies(), ["MathNet.Numerics-5.0.0;nuget"])
        removedependency.removeDependency(self.root, "MathNet.Numerics")
        self.assertEqual(self.dependencies(), [])

    def test_returns_removed_strings(self):
        self.assertEqual(removedependency.removeDependency(self.root, "TypeOCore"), ["Udrian@TypeOCore-0.1.0"])

    def test_unknown_dependency_is_rejected_and_file_unchanged(self):
        before = self.dependencies()
        with self.assertRaises(SystemExit):
            removedependency.removeDependency(self.root, "Nope")
        self.assertEqual(self.dependencies(), before)

    def test_name_must_match_exactly(self):
        with self.assertRaises(SystemExit):
            removedependency.removeDependency(self.root, "TypeO")

    def test_add_then_remove_round_trips(self):
        before = self.dependencies()
        adddependency.addDependency(self.root, "Pkg-1.0;nuget")
        removedependency.removeDependency(self.root, "Pkg")
        self.assertEqual(self.dependencies(), before)

    def test_do(self):
        removedependency.do(argparse.Namespace(projectPath=self.root, name="TypeOCore"))
        self.assertNotIn("Udrian@TypeOCore-0.1.0", self.dependencies())


if __name__ == "__main__":
    unittest.main()
