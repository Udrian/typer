import argparse, os, unittest
from unittest import mock

from scripts import generate, product, xmler
from tests.support import CSPROJ, TempDirTestCase, parseXml


def makeProject(root, data):
    return product.Product(data, root)


class ParseTests(unittest.TestCase):
    def test_project_path_required(self):
        p = argparse.ArgumentParser()
        generate.parse(p)
        self.assertEqual(p.parse_args(["-p", "x"]).projectPath, "x")
        with self.assertRaises(SystemExit):
            with mock.patch("sys.stderr"):
                p.parse_args([])


class CsProjEditingTests(unittest.TestCase):
    def test_add_default_var_enables_documentation_and_removes_nullable(self):
        xml = parseXml()
        generate.addDefaultVar(xml)
        self.assertEqual(xml.getElementsByTagName("GenerateDocumentationFile")[0].firstChild.data, "true")
        self.assertEqual(xml.getElementsByTagName("Nullable"), [])
        self.assertEqual(len(xml.getElementsByTagName("TargetFramework")), 1)

    def test_add_default_var_is_idempotent(self):
        xml = parseXml()
        generate.addDefaultVar(xml)
        generate.addDefaultVar(xml)
        self.assertEqual(len(xml.getElementsByTagName("GenerateDocumentationFile")), 1)

    def test_add_pre_build_events_adds_windows_and_unix_commands(self):
        xml = parseXml()
        generate.addPreBuildEvents(xml)
        target = xml.getElementsByTagName("Target")[0]
        self.assertEqual(target.getAttribute("Name"), "PreBuild")
        self.assertEqual(target.getAttribute("BeforeTargets"), "PreBuildEvent")
        execs = target.getElementsByTagName("Exec")
        self.assertEqual(len(execs), 2)
        windows = [e for e in execs if e.getAttribute("Condition").startswith("!")][0]
        unix = [e for e in execs if not e.getAttribute("Condition").startswith("!")][0]
        self.assertIn("typer.bat dependency", windows.getAttribute("Command"))
        self.assertIn("typer.sh", unix.getAttribute("Command"))
        self.assertIn("dependency -p", unix.getAttribute("Command"))

    def test_add_pre_build_events_is_idempotent(self):
        xml = parseXml()
        generate.addPreBuildEvents(xml)
        generate.addPreBuildEvents(xml)
        self.assertEqual(len(xml.getElementsByTagName("Target")), 1)
        self.assertEqual(len(xml.getElementsByTagName("Exec")), 2)


class AddExternalsTests(TempDirTestCase):
    def project(self, externals):
        return makeProject(self.tmp, {"name": "Foo", "version": "1", "externals": externals})

    def includes(self, xml):
        return [c.getAttribute("Include") for c in xml.getElementsByTagName("Content")]

    def test_no_externals_adds_nothing(self):
        xml = parseXml()
        generate.addExternals(xml, self.project([]), False, False)
        self.assertEqual(xml.getElementsByTagName("ItemGroup"), [])

    def test_adds_content_items_in_labelled_group(self):
        xml = parseXml()
        generate.addExternals(xml, self.project(["a.txt", "b/c.png"]), False, False)
        self.assertEqual(self.includes(xml), ["a.txt", "b/c.png"])
        group = xml.getElementsByTagName("ItemGroup")[0]
        self.assertEqual(group.getAttribute("Label"), "TypeOContent")
        copy = xml.getElementsByTagName("CopyToOutputDirectory")
        self.assertEqual([c.firstChild.data for c in copy], ["PreserveNewest", "PreserveNewest"])

    def test_does_not_duplicate_on_repeat(self):
        xml = parseXml()
        project = self.project(["a.txt"])
        generate.addExternals(xml, project, False, False)
        generate.addExternals(xml, project, False, False)
        self.assertEqual(self.includes(xml), ["a.txt"])

    def test_test_externals_only_for_test_projects(self):
        project = self.project(["a.txt", "mock.png;test"])
        main, test = parseXml(), parseXml()
        generate.addExternals(main, project, False, False)
        generate.addExternals(test, project, False, True)
        self.assertEqual(self.includes(main), ["a.txt"])
        self.assertEqual(self.includes(test), ["a.txt", "mock.png"])

    def test_dev_externals_only_for_dev_projects(self):
        project = self.project(["a.txt", "dev.png;dev"])
        main, dev = parseXml(), parseXml()
        generate.addExternals(main, project, False, False)
        generate.addExternals(dev, project, True, False)
        self.assertEqual(self.includes(main), ["a.txt"])
        self.assertEqual(self.includes(dev), ["a.txt", "dev.png"])


class CreateProjectAndSolutionTests(TempDirTestCase):
    def setUp(self):
        super().setUp()
        os.chdir(self.tmp)
        self.commands = []

    def run_generate(self, project, existing=()):
        def fakeExec(command, printout=True):
            self.commands.append(command)
            return ""

        def fakeExist(command, var):
            return (command, var) in existing

        with mock.patch("scripts.generate.cmd.exec", side_effect=fakeExec), \
                mock.patch("scripts.generate.cmd.exist", side_effect=fakeExist):
            generate.createProjectAndSolution(project)

    def test_plain_project_creates_solution_library_and_links_them(self):
        self.run_generate(makeProject(self.tmp, {"name": "Foo", "version": "1"}))
        self.assertEqual(self.commands, [
            "dotnet new sln --name Foo",
            "dotnet new classlib --name Foo",
            "dotnet sln Foo.sln add Foo/Foo.csproj",
        ])

    def test_existing_files_are_not_recreated(self):
        self.write("Foo.sln", "")
        self.write("Foo/Foo.csproj", CSPROJ)
        self.run_generate(makeProject(self.tmp, {"name": "Foo", "version": "1"}),
                          existing={("dotnet sln Foo.sln list", "Foo/Foo.csproj")})
        self.assertEqual(self.commands, [])

    def test_template_class_file_is_removed(self):
        self.write("Foo/Class1.cs", "")
        self.run_generate(makeProject(self.tmp, {"name": "Foo", "version": "1"}))
        self.assertFalse(os.path.exists("Foo/Class1.cs"))

    def test_test_project_is_created_and_referenced(self):
        project = makeProject(self.tmp, {"name": "Foo", "version": "1", "project": [
            {"Name": "Foo"}, {"Name": "FooTest", "isTest": True}]})
        self.run_generate(project)
        self.assertIn("dotnet new xunit --name FooTest", self.commands)
        self.assertIn("dotnet add FooTest/FooTest.csproj reference Foo/Foo.csproj", self.commands)
        self.assertIn("dotnet sln Foo.sln add FooTest/FooTest.csproj", self.commands)

    def test_dev_project_is_created_and_referenced(self):
        self.write("TypeDFoo/TypeDFoo.csproj", """<Project><PropertyGroup>
<OutputType>WinExe</OutputType><ApplicationManifest>app.manifest</ApplicationManifest>
<AvaloniaUseCompiledBindingsByDefault>true</AvaloniaUseCompiledBindingsByDefault>
<TargetFramework>net8.0</TargetFramework></PropertyGroup></Project>""")
        project = makeProject(self.tmp, {"name": "Foo", "version": "1", "type": "module", "project": [
            {"Name": "Foo"}, {"Name": "TypeDFoo", "isDev": True}]})
        self.run_generate(project)
        self.assertNotIn("dotnet new avalonia.app --name TypeDFoo", self.commands)
        self.assertIn("dotnet add TypeDFoo/TypeDFoo.csproj reference Foo/Foo.csproj", self.commands)
        self.assertIn("dotnet sln Foo.sln add TypeDFoo/TypeDFoo.csproj", self.commands)
        xml = xmler.load("TypeDFoo/TypeDFoo.csproj")
        for removed in ("OutputType", "ApplicationManifest", "AvaloniaUseCompiledBindingsByDefault"):
            self.assertEqual(xml.getElementsByTagName(removed), [])
        self.assertEqual(len(xml.getElementsByTagName("TargetFramework")), 1)

    def test_dev_project_missing_is_created_with_avalonia_template(self):
        self.write("TypeDFoo/TypeDFoo.csproj", "<Project><PropertyGroup><OutputType/><ApplicationManifest/>"
                   "<AvaloniaUseCompiledBindingsByDefault/></PropertyGroup></Project>")
        os.remove("TypeDFoo/TypeDFoo.csproj")
        self.write("TypeDFoo/App.axaml", "")
        self.write("TypeDFoo/Program.cs", "")
        project = makeProject(self.tmp, {"name": "Foo", "version": "1", "type": "exe", "project": [
            {"Name": "Foo"}, {"Name": "TypeDFoo", "isDev": True}]})
        self.run_generate(project)
        self.assertIn("dotnet new avalonia.app --name TypeDFoo", self.commands)
        self.assertFalse(os.path.exists("TypeDFoo/App.axaml"))
        self.assertFalse(os.path.exists("TypeDFoo/Program.cs"))

    def test_existing_test_files_are_preserved(self):
        self.write("FooTest/Usings.cs", "keep usings")
        self.write("FooTest/UnitTest1.cs", "keep test")
        project = makeProject(self.tmp, {"name": "Foo", "version": "1", "project": [
            {"Name": "Foo"}, {"Name": "FooTest", "isTest": True}]})
        self.run_generate(project)
        self.assertEqual(self.read("FooTest/Usings.cs"), "keep usings")
        self.assertEqual(self.read("FooTest/UnitTest1.cs"), "keep test")

    def test_generated_template_test_file_is_removed(self):
        project = makeProject(self.tmp, {"name": "Foo", "version": "1", "project": [
            {"Name": "Foo"}, {"Name": "FooTest", "isTest": True}]})

        def fakeExec(command, printout=True):
            self.commands.append(command)
            if command.startswith("dotnet new xunit"):
                self.write("FooTest/UnitTest1.cs", "template")
                self.write("FooTest/Usings.cs", "template usings")
            return ""

        with mock.patch("scripts.generate.cmd.exec", side_effect=fakeExec), \
                mock.patch("scripts.generate.cmd.exist", return_value=False):
            generate.createProjectAndSolution(project)
        self.assertFalse(os.path.exists("FooTest/UnitTest1.cs"))
        self.assertFalse(os.path.exists("FooTest/Usings.cs"))


class CheckPrerequisitesTests(unittest.TestCase):
    def test_installs_avalonia_templates_when_missing(self):
        with mock.patch("scripts.generate.cmd.exist", return_value=False), \
                mock.patch("scripts.generate.cmd.exec") as run:
            generate.checkAndInstallPrerequisites()
        run.assert_called_once_with("dotnet new install Avalonia.Templates")

    def test_skips_install_when_present(self):
        with mock.patch("scripts.generate.cmd.exist", return_value=True), \
                mock.patch("scripts.generate.cmd.exec") as run:
            generate.checkAndInstallPrerequisites()
        run.assert_not_called()


class DoTests(TempDirTestCase):
    def test_do_updates_all_project_files(self):
        self.writeTypeO("proj", {
            "name": "Foo", "version": "1", "externals": ["a.txt", "m.png;test", "d.png;dev"],
            "project": [{"Name": "Foo"}, {"Name": "TypeDFoo", "isDev": True}, {"Name": "FooTest", "isTest": True}]})
        for name in ("Foo", "TypeDFoo", "FooTest"):
            self.write("proj/{0}/{0}.csproj".format(name), CSPROJ)
        self.write("proj/Foo.sln", "")
        project = self.path("proj")

        with mock.patch("scripts.generate.cmd.exec"), mock.patch("scripts.generate.cmd.exist", return_value=True):
            generate.do(argparse.Namespace(projectPath=project))

        self.assertEqual(os.getcwd(), project)
        main = xmler.load(os.path.join(project, "Foo", "Foo.csproj"))
        self.assertEqual(main.getElementsByTagName("GenerateDocumentationFile")[0].firstChild.data, "true")
        self.assertEqual(main.getElementsByTagName("Target")[0].getAttribute("Name"), "PreBuild")
        self.assertEqual([c.getAttribute("Include") for c in main.getElementsByTagName("Content")], ["a.txt"])

        dev = xmler.load(os.path.join(project, "TypeDFoo", "TypeDFoo.csproj"))
        self.assertEqual([c.getAttribute("Include") for c in dev.getElementsByTagName("Content")], ["a.txt", "d.png"])

        test = xmler.load(os.path.join(project, "FooTest", "FooTest.csproj"))
        self.assertEqual([c.getAttribute("Include") for c in test.getElementsByTagName("Content")], ["a.txt", "m.png"])


if __name__ == "__main__":
    unittest.main()
