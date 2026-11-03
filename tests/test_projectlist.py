import argparse, json, os, unittest
from unittest import mock

from scripts import addproject, product, removeproject
from tests.support import TempDirTestCase


def parser(module):
    p = argparse.ArgumentParser()
    module.parse(p)
    return p


class ProjectListTestCase(TempDirTestCase):
    def setUp(self):
        super().setUp()
        self.writeTypeO("proj", {"name": "Foo", "version": "1", "project": [
            {"Name": "Foo", "type": "", "depends_on": []}]})
        self.root = self.path("proj")

    def projects(self):
        with open(os.path.join(self.root, "typeo.json")) as f:
            return json.load(f)["project"]


class AddParseTests(unittest.TestCase):
    def test_defaults(self):
        args = parser(addproject).parse_args(["-p", "x", "-n", "Bar"])
        self.assertEqual((args.projectPath, args.name, args.type, args.depends_on), ("x", "Bar", "", []))

    def test_all_options(self):
        args = parser(addproject).parse_args(["-p", "x", "-n", "Bar", "-t", "dev", "--depends_on", "A", "B"])
        self.assertEqual((args.type, args.depends_on), ("dev", ["A", "B"]))

    def test_type_choices_and_required(self):
        for argv in (["-p", "x", "-n", "B", "-t", "bogus"], ["-p", "x"], ["-n", "B"]):
            with self.assertRaises(SystemExit), mock.patch("sys.stderr"):
                parser(addproject).parse_args(argv)


class AddProjectTests(ProjectListTestCase):
    def test_adds_project_with_type_and_dependencies(self):
        addproject.addProject(self.root, "TypeDFoo", "dev", ["Foo"])
        self.assertEqual(self.projects()[-1], {"Name": "TypeDFoo", "type": "dev", "depends_on": ["Foo"]})

    def test_added_projects_load_through_product(self):
        addproject.addProject(self.root, "TypeDFoo", "dev", ["Foo"])
        addproject.addProject(self.root, "FooTest", "test", ["Foo", "TypeDFoo"])
        p = product.load(self.root)
        self.assertEqual([(s.name, s.type, s.dependsOn) for s in p.projects], [
            ("Foo", "", []), ("TypeDFoo", "dev", ["Foo"]), ("FooTest", "test", ["Foo", "TypeDFoo"])])
        self.assertEqual((p.devModuleName, p.testName), ("TypeDFoo", "FooTest"))

    def test_can_depend_on_a_project_added_earlier(self):
        addproject.addProject(self.root, "A", "", ["Foo"])
        addproject.addProject(self.root, "B", "", ["A"])
        self.assertEqual(self.projects()[-1]["depends_on"], ["A"])

    def test_duplicate_dependencies_are_collapsed(self):
        addproject.addProject(self.root, "A", "", ["Foo", "Foo"])
        self.assertEqual(self.projects()[-1]["depends_on"], ["Foo"])

    def test_duplicate_name_is_rejected_and_file_unchanged(self):
        before = self.projects()
        with self.assertRaises(SystemExit):
            addproject.addProject(self.root, "Foo", "", [])
        self.assertEqual(self.projects(), before)

    def test_unknown_dependency_is_rejected_and_file_unchanged(self):
        before = self.projects()
        with self.assertRaises(SystemExit):
            addproject.addProject(self.root, "Bar", "", ["Nope"])
        self.assertEqual(self.projects(), before)

    def test_project_depending_on_itself_is_rejected(self):
        with self.assertRaises(SystemExit):
            addproject.addProject(self.root, "Bar", "", ["Bar"])

    def test_missing_project_list_gets_main_project_first(self):
        self.writeTypeO("old", {"name": "Old", "version": "1"})
        addproject.addProject(self.path("old"), "OldTest", "test", ["Old"])
        with open(self.path("old", "typeo.json")) as f:
            self.assertEqual(json.load(f)["project"], [
                {"Name": "Old", "type": "", "depends_on": []},
                {"Name": "OldTest", "type": "test", "depends_on": ["Old"]}])

    def test_other_fields_are_preserved(self):
        self.writeTypeO("proj", {"name": "Foo", "version": "1", "externals": ["a.txt"],
                                 "dependencies": ["A-1"], "type": "exe"})
        addproject.addProject(self.root, "Bar", "", [])
        with open(os.path.join(self.root, "typeo.json")) as f:
            data = json.load(f)
        self.assertEqual((data["externals"], data["dependencies"], data["type"]), (["a.txt"], ["A-1"], "exe"))

    def test_do_reports_and_writes(self):
        args = argparse.Namespace(projectPath=self.root, name="Bar", type="", depends_on=["Foo"])
        addproject.do(args)
        self.assertEqual(self.projects()[-1]["Name"], "Bar")


class RemoveProjectTests(ProjectListTestCase):
    def setUp(self):
        super().setUp()
        addproject.addProject(self.root, "TypeDFoo", "dev", ["Foo"])
        addproject.addProject(self.root, "FooTest", "test", ["Foo"])

    def test_parse(self):
        args = parser(removeproject).parse_args(["-p", "x", "-n", "Bar"])
        self.assertEqual((args.projectPath, args.name), ("x", "Bar"))
        with self.assertRaises(SystemExit), mock.patch("sys.stderr"):
            parser(removeproject).parse_args(["-p", "x"])

    def test_removes_project_from_list(self):
        removeproject.removeProject(self.root, "FooTest")
        self.assertEqual([p["Name"] for p in self.projects()], ["Foo", "TypeDFoo"])
        self.assertFalse(product.load(self.root).haveTest)

    def test_unknown_project_is_rejected(self):
        with self.assertRaises(SystemExit):
            removeproject.removeProject(self.root, "Nope")

    def test_main_project_cannot_be_removed(self):
        with self.assertRaises(SystemExit):
            removeproject.removeProject(self.root, "Foo")
        self.assertEqual(len(self.projects()), 3)

    def test_project_with_dependents_cannot_be_removed(self):
        addproject.addProject(self.root, "Mid", "", ["Foo"])
        addproject.addProject(self.root, "Top", "", ["Mid"])
        with self.assertRaises(SystemExit):
            removeproject.removeProject(self.root, "Mid")
        removeproject.removeProject(self.root, "Top")
        removeproject.removeProject(self.root, "Mid")
        self.assertEqual([p["Name"] for p in self.projects()], ["Foo", "TypeDFoo", "FooTest"])

    def test_files_on_disk_are_left_alone(self):
        self.write("proj/FooTest/FooTest.csproj", "<Project/>")
        removeproject.removeProject(self.root, "FooTest")
        self.assertTrue(os.path.exists(self.path("proj/FooTest/FooTest.csproj")))

    def run_do(self, listed):
        self.write("proj/Foo.sln", "")
        with mock.patch("scripts.removeproject.cmd.exist", return_value=listed) as exist, \
                mock.patch("scripts.removeproject.cmd.exec") as run:
            removeproject.do(argparse.Namespace(projectPath=self.root, name="FooTest"))
        return exist, run

    def test_do_removes_project_from_solution_when_listed(self):
        exist, run = self.run_do(True)
        exist.assert_called_once_with("dotnet sln Foo.sln list", "FooTest/FooTest.csproj")
        run.assert_called_once_with("dotnet sln Foo.sln remove FooTest/FooTest.csproj")
        self.assertEqual([p["Name"] for p in self.projects()], ["Foo", "TypeDFoo"])

    def test_do_leaves_solution_alone_when_not_listed(self):
        _, run = self.run_do(False)
        run.assert_not_called()

    def test_do_without_solution_does_not_call_dotnet(self):
        with mock.patch("scripts.removeproject.cmd.exist") as exist:
            removeproject.do(argparse.Namespace(projectPath=self.root, name="FooTest"))
        exist.assert_not_called()

    def test_do_restores_working_directory(self):
        before = os.getcwd()
        self.run_do(True)
        self.assertEqual(os.getcwd(), before)


if __name__ == "__main__":
    unittest.main()
