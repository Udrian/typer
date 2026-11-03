import argparse, io, json, os, unittest, zipfile
from unittest import mock

from scripts import dependency, product, xmler
from tests.support import CSPROJ, TempDirTestCase, parseXml


def dep(text):
    return product.Dependency(text)


class ParseTests(unittest.TestCase):
    def test_project_path_required_and_cache_default(self):
        p = argparse.ArgumentParser()
        dependency.parse(p)
        args = p.parse_args(["-p", "proj"])
        self.assertEqual((args.projectPath, args.cachePath), ("proj", ""))
        self.assertEqual(p.parse_args(["-p", "proj", "-c", "cache"]).cachePath, "cache")
        with self.assertRaises(SystemExit):
            with mock.patch("sys.stderr"):
                p.parse_args([])


class ManipulateProjectTests(unittest.TestCase):
    def call(self, dependency_, projectType=""):
        xml = parseXml()
        with mock.patch("scripts.dependency.resolveNuget") as nuget, \
                mock.patch("scripts.dependency.resolveTypeODep", return_value=True) as typeo:
            result = dependency.manipulateProject(xml, "a.csproj", "a.sln", "path.csproj", dependency_, projectType)
        return result, nuget, typeo

    def test_dev_dependency_skipped_for_non_dev_project(self):
        result, nuget, typeo = self.call(dep("A-1;dev"), "")
        self.assertFalse(result)
        nuget.assert_not_called()
        typeo.assert_not_called()

    def test_dev_dependency_used_for_dev_project(self):
        result, _, typeo = self.call(dep("A-1;dev"), "dev")
        self.assertTrue(result)
        typeo.assert_called_once()

    def test_test_dependency_skipped_for_non_test_project(self):
        result, _, typeo = self.call(dep("A-1;test"), "dev")
        self.assertFalse(result)
        typeo.assert_not_called()

    def test_test_dependency_used_for_test_project(self):
        result, _, typeo = self.call(dep("A-1;test"), "test")
        self.assertTrue(result)
        typeo.assert_called_once()

    def test_test_project_receives_dev_tagged_dependency(self):
        result, _, typeo = self.call(dep("A-1;dev"), "test")
        self.assertTrue(result)
        typeo.assert_called_once()

    def test_untagged_dependency_goes_to_every_project_type(self):
        for projectType in ("", "dev", "test"):
            result, _, _ = self.call(dep("Udrian@A-1.0"), projectType)
            self.assertTrue(result, projectType)

    def test_nuget_dependency_is_resolved_and_never_requires_save(self):
        result, nuget, typeo = self.call(dep("Pkg-1.0;nuget"))
        self.assertFalse(result)
        nuget.assert_called_once()
        typeo.assert_not_called()

    def test_plain_dependency_goes_to_typeo_resolution(self):
        result, nuget, typeo = self.call(dep("Udrian@A-1.0"))
        self.assertTrue(result)
        nuget.assert_not_called()
        typeo.assert_called_once()


class ResolveNugetTests(unittest.TestCase):
    PACKAGES = CSPROJ.replace("</Project>", '<ItemGroup><PackageReference Include="Pkg" Version="1.0"/></ItemGroup></Project>')

    def test_missing_package_is_added_through_dotnet(self):
        with mock.patch("scripts.dependency.os.system") as system:
            dependency.resolveNuget(parseXml(), "a.csproj", dep("Pkg-1.0;nuget"))
        system.assert_called_once_with("dotnet add a.csproj package Pkg -v 1.0")

    def test_existing_package_version_is_not_added_again(self):
        with mock.patch("scripts.dependency.os.system") as system:
            dependency.resolveNuget(parseXml(self.PACKAGES), "a.csproj", dep("Pkg-1.0;nuget"))
        system.assert_not_called()

    def test_different_version_is_added(self):
        with mock.patch("scripts.dependency.os.system") as system:
            dependency.resolveNuget(parseXml(self.PACKAGES), "a.csproj", dep("Pkg-2.0;nuget"))
        system.assert_called_once_with("dotnet add a.csproj package Pkg -v 2.0")


class ResolveTypeODepTests(unittest.TestCase):
    def references(self, xml):
        return [(r.getAttribute("Name"), r.getAttribute("Include")) for r in xml.getElementsByTagName("ProjectReference")]

    def test_adds_reference_and_solution_entry(self):
        xml = parseXml()
        with mock.patch("scripts.dependency.os.system") as system:
            result = dependency.resolveTypeODep(xml, "a.sln", "m/A/A.csproj", dep("A-1.0"))
        self.assertTrue(result)
        self.assertEqual(self.references(xml), [("A", "m/A/A.csproj")])
        group = xml.getElementsByTagName("ItemGroup")[0]
        self.assertEqual(group.getAttribute("Label"), "TypeOModules")
        system.assert_called_once_with("dotnet sln a.sln add m/A/A.csproj")

    def test_second_call_is_a_no_op(self):
        xml = parseXml()
        with mock.patch("scripts.dependency.os.system") as system:
            dependency.resolveTypeODep(xml, "a.sln", "m/A/A.csproj", dep("A-1.0"))
            system.reset_mock()
            result = dependency.resolveTypeODep(xml, "a.sln", "m/A/A.csproj", dep("A-1.0"))
        self.assertFalse(result)
        system.assert_not_called()
        self.assertEqual(len(self.references(xml)), 1)

    def test_changed_path_replaces_reference(self):
        xml = parseXml()
        with mock.patch("scripts.dependency.os.system") as system:
            dependency.resolveTypeODep(xml, "a.sln", "old/A.csproj", dep("A-1.0"))
            system.reset_mock()
            result = dependency.resolveTypeODep(xml, "a.sln", "new/A.csproj", dep("A-2.0"))
        self.assertTrue(result)
        self.assertEqual(self.references(xml), [("A", "new/A.csproj")])
        system.assert_has_calls([mock.call("dotnet sln a.sln remove old/A.csproj"),
                                 mock.call("dotnet sln a.sln add new/A.csproj")])

    def test_multiple_dependencies_share_one_item_group(self):
        xml = parseXml()
        with mock.patch("scripts.dependency.os.system"):
            dependency.resolveTypeODep(xml, "a.sln", "m/A.csproj", dep("A-1"))
            dependency.resolveTypeODep(xml, "a.sln", "m/B.csproj", dep("B-1"))
        self.assertEqual(len(xml.getElementsByTagName("ItemGroup")), 1)
        self.assertEqual([n for n, _ in self.references(xml)], ["A", "B"])


class DoTests(TempDirTestCase):
    def setUp(self):
        super().setUp()
        self.cache = self.path("cache")
        self.proj = self.path("proj")

    def makeModule(self, name, version, devName=None):
        data = {"name": name, "version": "0.1.0", "project": [{"Name": name}]}
        if devName:
            data["project"].append({"Name": devName, "type": "dev"})
        self.writeTypeO("cache/{}/{}".format(name, version), data)

    def makeProject(self, data):
        self.writeTypeO("proj", data)
        for entry in data.get("project", [{"Name": data["name"]}]):
            self.write("proj/{0}/{0}.csproj".format(entry["Name"]), CSPROJ)

    def run_do(self):
        with mock.patch("scripts.dependency.os.system") as system, \
                mock.patch("scripts.dependency.downloadAndExtractDependency") as download:
            dependency.do(argparse.Namespace(projectPath=self.proj, cachePath=self.cache))
        return system, download

    def refs(self, name):
        xml = xmler.load(self.path("proj", name, name + ".csproj"))
        return [r.getAttribute("Name") for r in xml.getElementsByTagName("ProjectReference")]

    def test_adds_typeo_dependency_reference_to_main_project(self):
        self.makeModule("TypeOCore", "0.1.0.dev")
        self.makeProject({"name": "Foo", "version": "1", "dependencies": ["Udrian@TypeOCore-0.1.0.dev"]})
        system, download = self.run_do()
        download.assert_not_called()
        self.assertEqual(self.refs("Foo"), ["TypeOCore"])
        include = xmler.load(self.path("proj/Foo/Foo.csproj")).getElementsByTagName("ProjectReference")[0].getAttribute("Include")
        self.assertEqual(include, "{}/TypeOCore/0.1.0.dev/TypeOCore/TypeOCore.csproj".format(self.cache))

    def test_second_run_does_not_duplicate(self):
        self.makeModule("TypeOCore", "0.1.0.dev")
        self.makeProject({"name": "Foo", "version": "1", "dependencies": ["Udrian@TypeOCore-0.1.0.dev"]})
        self.run_do()
        self.run_do()
        self.assertEqual(self.refs("Foo"), ["TypeOCore"])

    def test_missing_dependency_is_downloaded(self):
        self.makeProject({"name": "Foo", "version": "1", "dependencies": ["Udrian@TypeOCore-0.1.0.dev"]})
        _, download = self.run_do()
        download.assert_called_once()
        called, localPath = download.call_args.args
        self.assertEqual(called.name, "TypeOCore")
        self.assertEqual(localPath, "{}/TypeOCore/0.1.0.dev".format(self.cache))

    def test_nuget_dependency_is_never_downloaded(self):
        self.makeProject({"name": "Foo", "version": "1", "dependencies": ["Pkg-1.0;nuget"]})
        system, download = self.run_do()
        download.assert_not_called()
        system.assert_called_once_with("dotnet add {} package Pkg -v 1.0".format(self.path("proj/Foo/Foo.csproj")))

    def test_dev_dependency_skipped_without_dev_project(self):
        self.makeProject({"name": "Foo", "version": "1", "dependencies": ["Udrian@TypeD-0.1.0.dev;dev"]})
        _, download = self.run_do()
        download.assert_not_called()
        self.assertEqual(self.refs("Foo"), [])

    def test_test_dependency_skipped_without_test_project(self):
        self.makeProject({"name": "Foo", "version": "1", "dependencies": ["Udrian@Mocks-0.1.0;test"]})
        _, download = self.run_do()
        download.assert_not_called()

    def test_local_dependency_uses_version_as_path(self):
        local = self.path("elsewhere")
        self.write("elsewhere/TypeOCore/TypeOCore.csproj", CSPROJ)
        self.makeProject({"name": "Foo", "version": "1", "dependencies": []})
        self.write("typeo_override.json", "[]")
        self.writeTypeO("proj", {"name": "Foo", "version": "1", "dependencies": []},
                        override=["Udrian@TypeOCore-{};local".format(local)])
        _, download = self.run_do()
        download.assert_not_called()
        include = xmler.load(self.path("proj/Foo/Foo.csproj")).getElementsByTagName("ProjectReference")[0].getAttribute("Include")
        self.assertEqual(include, "{}/TypeOCore/TypeOCore.csproj".format(local))

    def test_override_changes_resolved_dependency(self):
        self.makeModule("TypeOCore", "9.9.9")
        self.makeProject({"name": "Foo", "version": "1", "dependencies": ["Udrian@TypeOCore-0.1.0"]})
        self.write("proj/typeo_override.json", json.dumps(["Udrian@TypeOCore-9.9.9"]))
        _, download = self.run_do()
        download.assert_not_called()
        include = xmler.load(self.path("proj/Foo/Foo.csproj")).getElementsByTagName("ProjectReference")[0].getAttribute("Include")
        self.assertIn("/TypeOCore/9.9.9/", include)

    def test_dev_project_receives_dev_and_normal_dependencies(self):
        self.makeModule("TypeOCore", "0.1.0.dev", devName="TypeDCore")
        self.makeModule("TypeD", "0.1.0.dev")
        self.makeProject({"name": "Foo", "version": "1", "dependencies": [
            "Udrian@TypeOCore-0.1.0.dev", "Udrian@TypeD-0.1.0.dev;dev"],
            "project": [{"Name": "Foo"}, {"Name": "TypeDFoo", "type": "dev"}]})
        self.run_do()
        self.assertEqual(self.refs("Foo"), ["TypeOCore"])
        self.assertEqual(self.refs("TypeDFoo"), ["TypeOCore", "TypeDCore", "TypeD"])

    def test_test_project_receives_dependencies(self):
        self.makeModule("TypeOCore", "0.1.0.dev")
        self.makeModule("Mocks", "0.1.0")
        self.makeProject({"name": "Foo", "version": "1", "dependencies": [
            "Udrian@TypeOCore-0.1.0.dev", "Udrian@Mocks-0.1.0;test"],
            "project": [{"Name": "Foo"}, {"Name": "FooTest", "type": "test"}]})
        self.run_do()
        self.assertEqual(self.refs("Foo"), ["TypeOCore"])
        self.assertEqual(self.refs("FooTest"), ["TypeOCore", "Mocks"])

    def test_dependency_goes_to_every_project_of_matching_type(self):
        self.makeModule("TypeOCore", "0.1.0.dev")
        self.makeModule("TypeD", "0.1.0.dev")
        self.makeProject({"name": "Foo", "version": "1", "dependencies": [
            "Udrian@TypeOCore-0.1.0.dev", "Udrian@TypeD-0.1.0.dev;dev"],
            "project": [{"Name": "Foo"}, {"Name": "Extra"}, {"Name": "DevA", "type": "dev"},
                        {"Name": "DevB", "type": "dev"}, {"Name": "FooTest", "type": "test"}]})
        self.run_do()
        self.assertEqual(self.refs("Foo"), ["TypeOCore"])
        self.assertEqual(self.refs("Extra"), ["TypeOCore"])
        self.assertEqual(self.refs("DevA"), ["TypeOCore", "TypeD"])
        self.assertEqual(self.refs("DevB"), ["TypeOCore", "TypeD"])
        self.assertEqual(self.refs("FooTest"), ["TypeOCore", "TypeD"])

    def test_default_cache_path_uses_environment(self):
        variable = "LOCALAPPDATA" if os.name == "nt" else "HOME"
        base = self.path("home")
        self.write("home/TypeO/ModulesCache/TypeOCore/0.1.0.dev/typeo.json", "{}")
        self.makeProject({"name": "Foo", "version": "1", "dependencies": ["Udrian@TypeOCore-0.1.0.dev"]})
        with mock.patch.dict(os.environ, {variable: base}), \
                mock.patch("scripts.dependency.os.system"), \
                mock.patch("scripts.dependency.downloadAndExtractDependency") as download:
            dependency.do(argparse.Namespace(projectPath=self.proj, cachePath=""))
        download.assert_not_called()
        self.assertEqual(self.refs("Foo"), ["TypeOCore"])


class DownloadTests(TempDirTestCase):
    def fakeDownload(self, url, destination):
        with zipfile.ZipFile(destination, "w") as z:
            z.writestr("typeocore-0.1.0/typeo.json", json.dumps({"name": "TypeOCore", "version": "0.1.0"}))
            z.writestr("typeocore-0.1.0/TypeOCore/TypeOCore.csproj", CSPROJ)

    def test_downloads_extracts_flattens_and_bootstraps(self):
        target = self.path("cache", "TypeOCore", "0.1.0")
        with mock.patch("scripts.dependency.urllib.request.urlretrieve", side_effect=self.fakeDownload) as fetch, \
                mock.patch("scripts.dependency.os.system") as system:
            dependency.downloadAndExtractDependency(dep("Udrian@TypeOCore-0.1.0"), target)
        fetch.assert_called_once()
        self.assertEqual(fetch.call_args.args[0], "https://github.com/Udrian/TypeOCore/archive/refs/tags/0.1.0.zip")
        self.assertTrue(os.path.isfile(os.path.join(target, "typeo.json")))
        self.assertTrue(os.path.isfile(os.path.join(target, "TypeOCore", "TypeOCore.csproj")))
        self.assertFalse(os.path.exists(os.path.join(target, "0.1.0.zip")))
        self.assertFalse(os.path.exists(os.path.join(target, "typeocore-0.1.0")))
        commands = [c.args[0] for c in system.call_args_list]
        self.assertEqual(commands[0], "git clone https://github.com/Udrian/typer.git {}/typer".format(target))
        self.assertIn("create_project_files", commands[1])

    def test_restores_working_directory(self):
        before = os.getcwd()
        with mock.patch("scripts.dependency.urllib.request.urlretrieve", side_effect=self.fakeDownload), \
                mock.patch("scripts.dependency.os.system"):
            dependency.downloadAndExtractDependency(dep("Udrian@TypeOCore-0.1.0"), self.path("c", "TypeOCore", "0.1.0"))
        self.assertEqual(os.getcwd(), before)


if __name__ == "__main__":
    unittest.main()
