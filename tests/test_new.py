import argparse, json, os, unittest
from unittest import mock

from scripts import new, product
from tests.support import TempDirTestCase


def parser():
    p = argparse.ArgumentParser()
    new.parse(p)
    return p


def makeArgs(**overrides):
    values = dict(name="Foo", output=".", git=None, disableGit=True, noCommit=True, version="0.1.0",
                  dependencies="", type="module", clean=False)
    values.update(overrides)
    return argparse.Namespace(**values)


class ParseTests(unittest.TestCase):
    def test_defaults(self):
        args = parser().parse_args(["-n", "Foo", "-o", "out"])
        self.assertEqual(args.name, "Foo")
        self.assertEqual(args.output, "out")
        self.assertIsNone(args.git)
        self.assertFalse(args.disableGit)
        self.assertFalse(args.noCommit)
        self.assertEqual(args.version, "0.1.0")
        self.assertEqual(args.dependencies, "")
        self.assertEqual(args.type, "module")
        self.assertFalse(args.clean)

    def test_name_and_output_required(self):
        with self.assertRaises(SystemExit):
            with mock.patch("sys.stderr"):
                parser().parse_args(["-n", "Foo"])
        with self.assertRaises(SystemExit):
            with mock.patch("sys.stderr"):
                parser().parse_args(["-o", "out"])

    def test_all_options(self):
        args = parser().parse_args(["-n", "Foo", "-o", "out", "-g", "url", "--disableGit", "--noCommit",
                                    "-v", "2.0.0", "-d", "A-1 B-2", "-t", "exe", "--clean"])
        self.assertEqual(args.git, "url")
        self.assertTrue(args.disableGit and args.noCommit and args.clean)
        self.assertEqual(args.version, "2.0.0")
        self.assertEqual(args.dependencies, "A-1 B-2")
        self.assertEqual(args.type, "exe")

    def test_type_accepts_module_and_exe_only(self):
        for value in ("module", "exe"):
            self.assertEqual(parser().parse_args(["-n", "F", "-o", "o", "-t", value]).type, value)
        with self.assertRaises(SystemExit):
            with mock.patch("sys.stderr"):
                parser().parse_args(["-n", "F", "-o", "o", "-t", "other"])


class FileCreationTests(TempDirTestCase):
    def setUp(self):
        super().setUp()
        os.chdir(self.tmp)

    def test_create_file_writes_content(self):
        new.CreateFile("a.txt", "hello")
        self.assertEqual(self.read("a.txt"), "hello")

    def test_create_file_does_not_overwrite(self):
        self.write("a.txt", "original")
        new.CreateFile("a.txt", "new")
        self.assertEqual(self.read("a.txt"), "original")

    def test_create_file_from_template_replaces_placeholders(self):
        new.CreateFileFromTemplate("notes.txt", "templates/ReleaseNotes.template",
                                   {"version": "1.2.3", "day": 4, "month": 5, "year": "26"})
        text = self.read("notes.txt")
        self.assertIn("1.2.3 - 4/5-26", text)
        self.assertNotIn("{{", text)

    def test_create_file_from_template_does_not_overwrite(self):
        self.write("notes.txt", "original")
        new.CreateFileFromTemplate("notes.txt", "templates/ReleaseNotes.template", {})
        self.assertEqual(self.read("notes.txt"), "original")

    def test_create_file_from_missing_template_creates_nothing(self):
        new.CreateFileFromTemplate("x.txt", "templates/DoesNotExist.template", {})
        self.assertFalse(os.path.exists("x.txt"))

    def test_override_template_is_valid_json_list(self):
        new.CreateFileFromTemplate("typeo_override.json", "templates/typeo_override.json.template", {})
        self.assertEqual(json.loads(self.read("typeo_override.json")), [])


class AddExtraFilesTests(TempDirTestCase):
    def setUp(self):
        super().setUp()
        os.chdir(self.tmp)

    def typeo(self):
        return json.loads(self.read("typeo.json"))

    def test_creates_all_project_files(self):
        new.addExtraFiles(makeArgs())
        for name in ("typeo.json", "typeo_override.json", "Readme-TypeO.txt", "ReleaseNotes-Foo.txt",
                     "create_project_files.bat", "create_project_files.sh",
                     "upload_version.bat", "upload_version.sh"):
            self.assertTrue(os.path.exists(name), name)
        self.assertFalse(os.path.exists("product"))
        self.assertFalse(os.path.exists("dependency_override"))

    def test_typeo_json_contents(self):
        new.addExtraFiles(makeArgs(version="2.3.4"))
        data = self.typeo()
        self.assertEqual(data["name"], "Foo")
        self.assertEqual(data["version"], "2.3.4")
        self.assertEqual(data["externals"], [])
        self.assertEqual(data["type"], "module")
        self.assertEqual(data["dependencies"], ["Udrian@TypeOCore-0.1.0"])
        self.assertEqual(data["project"], [{"Name": "Foo", "type": "", "depends_on": []}])
        self.assertNotIn("devModuleName", data)
        self.assertNotIn("testName", data)

    def test_only_default_project_is_created(self):
        new.addExtraFiles(makeArgs(name="TypeOFoo"))
        p = product.load(self.tmp)
        self.assertEqual([(s.name, s.type) for s in p.projects], [("TypeOFoo", "")])
        self.assertEqual((p.haveDevModule, p.haveTest), (False, False))

    def test_dev_and_test_options_are_gone(self):
        for option in ("--dev", "--devModuleName", "--test", "--testName"):
            with self.assertRaises(SystemExit):
                with mock.patch("sys.stderr"):
                    parser().parse_args(["-n", "F", "-o", "o", option])

    def test_explicit_dependencies_replace_defaults(self):
        new.addExtraFiles(makeArgs(dependencies="A-1.0 B-2.0;nuget"))
        self.assertEqual(self.typeo()["dependencies"], ["A-1.0", "B-2.0;nuget"])

    def test_type_exe(self):
        new.addExtraFiles(makeArgs(type="exe"))
        self.assertEqual(self.typeo()["type"], "exe")

    def test_existing_typeo_json_is_not_overwritten(self):
        self.write("typeo.json", '{"name": "Keep", "version": "9"}')
        new.addExtraFiles(makeArgs())
        self.assertEqual(self.typeo()["name"], "Keep")

    def test_release_notes_use_version_and_name(self):
        new.addExtraFiles(makeArgs(name="Bar", version="3.1.4"))
        self.assertIn("3.1.4", self.read("ReleaseNotes-Bar.txt"))

    def test_without_disable_git_creates_gitignore_entries(self):
        with mock.patch("scripts.new.os.system") as system:
            new.addExtraFiles(makeArgs(disableGit=False))
        system.assert_called_with("dotnet new gitignore")
        text = self.read(".gitignore")
        self.assertIn("# TypeO", text)
        self.assertIn("typeo_override.json", text)
        self.assertIn("*.sln", text)
        self.assertIn("*.csproj", text)
        self.assertNotIn("dependency_override", text)

    def test_existing_gitignore_is_appended_to(self):
        self.write(".gitignore", "bin/\n")
        with mock.patch("scripts.new.os.system") as system:
            new.addExtraFiles(makeArgs(disableGit=False))
        system.assert_not_called()
        text = self.read(".gitignore")
        self.assertTrue(text.startswith("bin/\n"))
        self.assertIn("typeo_override.json", text)

    def test_disable_git_leaves_gitignore_alone(self):
        new.addExtraFiles(makeArgs(disableGit=True))
        self.assertFalse(os.path.exists(".gitignore"))


class CodeFileTests(TempDirTestCase):
    def setUp(self):
        super().setUp()
        os.chdir(self.tmp)
        self.project = product.Product({"name": "TypeOFoo", "version": "1", "project": [
            {"Name": "TypeOFoo"},
            {"Name": "TypeDFoo", "type": "dev"},
            {"Name": "TypeOFooTest", "type": "test"},
        ]}, self.tmp)
        for name in ("TypeOFoo", "TypeDFoo", "TypeOFooTest"):
            os.mkdir(name)

    def test_create_code_files(self):
        new.createCodeFiles(self.project)
        self.assertIn("class TypeOFooModule", self.read("TypeOFoo/TypeOFooModule.cs"))
        self.assertTrue(os.path.exists("TypeOFoo/TypeOFooModuleOption.cs"))

    def test_create_code_test_files(self):
        new.createCodeTestFiles(self.project)
        self.assertIn("namespace TypeOFooTest;", self.read("TypeOFooTest/TypeOFooModuleTest.cs"))
        self.assertTrue(os.path.exists("TypeOFooTest/Usings.cs"))

    def test_create_code_typed_test_files(self):
        new.createCodeTypeDTestFiles(self.project)
        self.assertTrue(os.path.exists("TypeOFooTest/TypeDMock.cs"))
        text = self.read("TypeOFooTest/TypeDFooModuleTest.cs")
        self.assertIn("TypeDFooInitializer", text)
        self.assertIn("namespace TypeOFooTest;", text)

    def test_create_code_typed_files(self):
        new.createCodeTypeDFiles(self.project)
        text = self.read("TypeDFoo/TypeDFooInitializer.cs")
        self.assertIn("namespace TypeDFoo;", text)
        self.assertIn("class TypeDFooInitializer", text)


class CommitTests(unittest.TestCase):
    def test_no_commit_skips_everything(self):
        with mock.patch("scripts.new.os.system") as system, mock.patch("builtins.input") as ask:
            new.commitAndPushMessage("msg", makeArgs(noCommit=True))
        system.assert_not_called()
        ask.assert_not_called()

    def test_decline_does_not_commit(self):
        with mock.patch("scripts.new.os.system") as system, mock.patch("builtins.input", return_value="n"):
            new.commitAndPushMessage("msg", makeArgs(noCommit=False))
        system.assert_called_once_with("git status")

    def test_accept_commits_with_default_message(self):
        with mock.patch("scripts.new.os.system") as system, mock.patch("builtins.input", side_effect=["yes", ""]):
            new.commitAndPushMessage("Initial commit", makeArgs(noCommit=False))
        system.assert_has_calls([mock.call("git status"),
                                 mock.call('git commit -m "Initial commit"'),
                                 mock.call("git push")])

    def test_accept_commits_with_custom_message(self):
        with mock.patch("scripts.new.os.system") as system, mock.patch("builtins.input", side_effect=["Y", "Custom"]):
            new.commitAndPushMessage("Initial commit", makeArgs(noCommit=False))
        system.assert_any_call('git commit -m "Custom"')


class CloneTyperTests(TempDirTestCase):
    def setUp(self):
        super().setUp()
        os.chdir(self.tmp)

    def test_git_enabled_initialises_and_adds_submodule(self):
        with mock.patch("scripts.new.os.system") as system:
            new.cloneTyper(makeArgs(disableGit=False, noCommit=True))
        system.assert_has_calls([mock.call("git init"),
                                 mock.call("git submodule add https://github.com/Udrian/typer.git")])

    def test_git_link_is_cloned(self):
        with mock.patch("scripts.new.os.system") as system:
            new.cloneTyper(makeArgs(disableGit=False, git="https://example/x.git"))
        system.assert_any_call("git clone https://example/x.git .")

    def test_existing_typer_folder_is_not_added_again(self):
        os.mkdir("typer")
        with mock.patch("scripts.new.os.system") as system:
            new.cloneTyper(makeArgs(disableGit=False))
        system.assert_called_once_with("git init")

    def test_disable_git_clones_typer_plainly(self):
        with mock.patch("scripts.new.os.system") as system:
            new.cloneTyper(makeArgs(disableGit=True))
        system.assert_called_once_with("git clone https://github.com/Udrian/typer.git")


class DoTests(TempDirTestCase):
    def fakeProjectGeneration(self, command):
        # Stands in for create_project_files, which makes the project folders through dotnet.
        if "create_project_files" in command:
            with open("typeo.json") as f:
                for entry in json.load(f)["project"]:
                    os.makedirs(entry["Name"], exist_ok=True)
        return 0

    def run_do(self, **overrides):
        args = makeArgs(output=self.tmp, **overrides)
        with mock.patch("scripts.new.os.system", side_effect=self.fakeProjectGeneration), \
                mock.patch("scripts.new.cmd.exec"):
            new.do(args)
        return self.path(args.name.lower())

    def test_creates_project_in_lowercase_folder(self):
        root = self.run_do(name="TypeOFoo")
        self.assertTrue(os.path.isfile(os.path.join(root, "typeo.json")))
        self.assertTrue(os.path.isfile(os.path.join(root, "typeo_override.json")))

    def test_creates_module_code_files(self):
        root = self.run_do(name="TypeOFoo")
        self.assertTrue(os.path.isfile(os.path.join(root, "TypeOFoo", "TypeOFooModule.cs")))

    def test_clean_skips_code_files(self):
        root = self.run_do(name="TypeOFoo", clean=True)
        self.assertFalse(os.path.exists(os.path.join(root, "TypeOFoo", "TypeOFooModule.cs")))

    def test_git_enabled_stages_and_commits_initial(self):
        args = makeArgs(output=self.tmp, name="TypeOFoo", disableGit=False, noCommit=True)
        with mock.patch("scripts.new.os.system", side_effect=self.fakeProjectGeneration) as system, \
                mock.patch("scripts.new.cmd.exec"):
            new.do(args)
        system.assert_any_call("git add .")


if __name__ == "__main__":
    unittest.main()
