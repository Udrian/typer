import argparse, io, json, os, shlex, subprocess, unittest, zipfile
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
            result = dependency.manipulateProject(xml, "a.csproj", "path.csproj", dependency_, projectType)
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

    def test_adds_project_reference_for_solution_sync(self):
        xml = parseXml()
        with mock.patch("scripts.dependency.os.system") as system:
            result = dependency.resolveTypeODep(xml, "m/A/A.csproj", dep("A-1.0"))
        self.assertTrue(result)
        self.assertEqual(self.references(xml), [("A", "m/A/A.csproj")])
        group = xml.getElementsByTagName("ItemGroup")[0]
        self.assertEqual(group.getAttribute("Label"), "TypeOModules")
        system.assert_not_called()

    def test_second_call_is_a_no_op(self):
        xml = parseXml()
        with mock.patch("scripts.dependency.os.system") as system:
            dependency.resolveTypeODep(xml, "m/A/A.csproj", dep("A-1.0"))
            system.reset_mock()
            result = dependency.resolveTypeODep(xml, "m/A/A.csproj", dep("A-1.0"))
        self.assertFalse(result)
        system.assert_not_called()
        self.assertEqual(len(self.references(xml)), 1)

    def test_changed_path_replaces_reference(self):
        xml = parseXml()
        with mock.patch("scripts.dependency.os.system") as system:
            dependency.resolveTypeODep(xml, "old/A.csproj", dep("A-1.0"))
            system.reset_mock()
            result = dependency.resolveTypeODep(xml, "new/A.csproj", dep("A-2.0"))
        self.assertTrue(result)
        self.assertEqual(self.references(xml), [("A", "new/A.csproj")])
        system.assert_not_called()

    def test_multiple_dependencies_share_one_item_group(self):
        xml = parseXml()
        with mock.patch("scripts.dependency.os.system"):
            dependency.resolveTypeODep(xml, "m/A.csproj", dep("A-1"))
            dependency.resolveTypeODep(xml, "m/B.csproj", dep("B-1"))
        self.assertEqual(len(xml.getElementsByTagName("ItemGroup")), 1)
        self.assertEqual([n for n, _ in self.references(xml)], ["A", "B"])


class DoTests(TempDirTestCase):
    def setUp(self):
        super().setUp()
        self.cache = self.path("cache")
        self.proj = self.path("proj")

    def makeModule(self, name, version, devName=None, dependencies=()):
        data = {"name": name, "version": "0.1.0", "project": [{"Name": name}]}
        data["dependencies"] = list(dependencies)
        if devName:
            data["project"].append({"Name": devName, "type": "dev"})
        self.writeTypeO("cache/Udrian/{}/{}".format(name, version), data)
        for sub in data["project"]:
            self.write("cache/Udrian/{}/{}/{}/{}.csproj".format(name, version, sub["Name"], sub["Name"]), CSPROJ)

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
        self.assertEqual(include, "{}/Udrian/TypeOCore/0.1.0.dev/TypeOCore/TypeOCore.csproj".format(self.cache))

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
        self.assertEqual(localPath, "{}/Udrian/TypeOCore/0.1.0.dev".format(self.cache))

    def test_nuget_dependency_is_never_downloaded(self):
        self.makeProject({"name": "Foo", "version": "1", "dependencies": ["Pkg-1.0;nuget"]})
        system, download = self.run_do()
        download.assert_not_called()
        system.assert_called_once_with("dotnet add {} package Pkg -v 1.0".format(self.path("proj/Foo/Foo.csproj")))

    def test_dev_nuget_dependency_skipped_without_dev_project(self):
        self.makeProject({"name": "Foo", "version": "1", "dependencies": ["Pkg-1.0;nuget;dev"]})
        system, download = self.run_do()
        download.assert_not_called()
        system.assert_not_called()

    def test_dev_module_without_dev_project_goes_to_main_project_with_its_dev_projects(self):
        self.makeModule("TypeOCore", "0.1.0", devName="TypeDCore")
        self.makeProject({"name": "Foo", "version": "1", "dependencies": [
            "Udrian@TypeOCore-0.1.0", "Udrian@TypeOCore-0.1.0;dev"]})
        self.run_do()
        self.assertEqual(self.refs("Foo"), ["TypeOCore", "TypeDCore"])

    def test_dev_module_with_dev_project_still_only_goes_to_dev_project(self):
        self.makeModule("TypeD", "0.1.0")
        self.makeProject({"name": "Foo", "version": "1", "dependencies": ["Udrian@TypeD-0.1.0;dev"],
                          "project": [{"Name": "Foo"}, {"Name": "FooDev", "type": "dev"}]})
        self.run_do()
        self.assertEqual((self.refs("Foo"), self.refs("FooDev")), ([], ["TypeD"]))

    def test_references_survive_repeated_runs_for_plain_and_dev_override_pairs(self):
        self.makeModule("TypeOCore", "0.1.0", devName="TypeDCore")
        self.makeProject({"name": "Foo", "version": "1", "dependencies": []})
        self.write("proj/typeo_override.json", json.dumps([
            "Udrian@TypeOCore-0.1.0", "Udrian@TypeOCore-0.1.0;dev"]))
        for _ in range(2):
            system, _ = self.run_do()
            self.assertEqual(self.refs("Foo"), ["TypeOCore", "TypeDCore"])
            self.assertNotIn("remove", " ".join(c.args[0] for c in system.call_args_list))

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

    def csproj(self, name):
        return xmler.load(self.path("proj", name, name + ".csproj"))

    def packages(self, name):
        return [p.getAttribute("Include") for p in self.csproj(name).getElementsByTagName("PackageReference")]

    def test_removed_module_dependency_is_removed_from_project_and_solution(self):
        self.makeModule("TypeOCore", "0.1.0.dev")
        self.makeModule("Other", "1.0")
        self.makeProject({"name": "Foo", "version": "1", "dependencies": [
            "Udrian@TypeOCore-0.1.0.dev", "Udrian@Other-1.0"]})
        solution = self.write("proj/Foo.slnx", "<Solution />")
        self.run_do()
        self.assertEqual(self.refs("Foo"), ["TypeOCore", "Other"])
        self.assertEqual(len(xmler.load(solution).getElementsByTagName("Project")), 3)

        self.writeTypeO("proj", {"name": "Foo", "version": "1", "dependencies": ["Udrian@TypeOCore-0.1.0.dev"]})
        system, _ = self.run_do()
        self.assertEqual(self.refs("Foo"), ["TypeOCore"])
        solutionPaths = [p.getAttribute("Path") for p in xmler.load(solution).getElementsByTagName("Project")]
        self.assertEqual(len(solutionPaths), 2)
        self.assertTrue(any("/TypeOCore/0.1.0.dev/" in path for path in solutionPaths))
        self.assertTrue(any(path.endswith("/Foo/Foo.csproj") for path in solutionPaths))
        system.assert_not_called()

    def test_removing_all_dependencies_removes_the_module_group(self):
        self.makeModule("TypeOCore", "0.1.0.dev")
        self.makeProject({"name": "Foo", "version": "1", "dependencies": ["Udrian@TypeOCore-0.1.0.dev"]})
        self.run_do()
        self.writeTypeO("proj", {"name": "Foo", "version": "1", "dependencies": []})
        self.run_do()
        self.assertEqual(self.refs("Foo"), [])
        self.assertEqual(self.csproj("Foo").getElementsByTagName("ItemGroup"), [])

    def test_shared_module_stays_in_solution_while_another_project_uses_it(self):
        self.makeModule("TypeOCore", "0.1.0.dev")
        self.makeProject({"name": "Foo", "version": "1", "dependencies": ["Udrian@TypeOCore-0.1.0.dev;test"],
                          "project": [{"Name": "Foo"}, {"Name": "FooTest", "type": "test"}]})
        self.run_do()
        self.assertEqual((self.refs("Foo"), self.refs("FooTest")), ([], ["TypeOCore"]))
        self.writeTypeO("proj", {"name": "Foo", "version": "1", "dependencies": ["Udrian@TypeOCore-0.1.0.dev"],
                                 "project": [{"Name": "Foo"}, {"Name": "FooTest", "type": "test"}]})
        system, _ = self.run_do()
        self.assertEqual((self.refs("Foo"), self.refs("FooTest")), (["TypeOCore"], ["TypeOCore"]))
        self.assertNotIn("remove", " ".join(c.args[0] for c in system.call_args_list))

    def test_project_references_without_a_name_are_never_removed(self):
        self.makeProject({"name": "Foo", "version": "1", "dependencies": []})
        self.write("proj/Foo/Foo.csproj", CSPROJ.replace("</Project>",
                   '<ItemGroup><ProjectReference Include="../Bar/Bar.csproj"/></ItemGroup></Project>'))
        system, _ = self.run_do()
        system.assert_not_called()
        self.assertEqual(len(self.csproj("Foo").getElementsByTagName("ProjectReference")), 1)

    def test_stale_nuget_package_is_removed_through_dotnet(self):
        self.makeProject({"name": "Foo", "version": "1", "dependencies": ["Keep-1.0;nuget"]})
        self.write("proj/Foo/Foo.csproj", CSPROJ.replace("</Project>",
                   '<ItemGroup><PackageReference Include="Keep" Version="1.0"/>'
                   '<PackageReference Include="Old" Version="2.0"/></ItemGroup></Project>'))
        system, _ = self.run_do()
        system.assert_called_once_with("dotnet remove {}/Foo/Foo.csproj package Old".format(self.proj))

    def test_nuget_packages_are_kept_for_matching_project_types_only(self):
        self.makeProject({"name": "Foo", "version": "1", "dependencies": ["Dev-1.0;nuget;dev", "Tst-1.0;nuget;test"],
                          "project": [{"Name": "Foo"}, {"Name": "FooDev", "type": "dev"}, {"Name": "FooTest", "type": "test"}]})
        both = '<ItemGroup><PackageReference Include="Dev" Version="1.0"/><PackageReference Include="Tst" Version="1.0"/></ItemGroup>'
        for name in ("Foo", "FooDev", "FooTest"):
            self.write("proj/{0}/{0}.csproj".format(name), CSPROJ.replace("</Project>", both + "</Project>"))
        system, _ = self.run_do()
        commands = sorted(c.args[0].replace(self.proj, "") for c in system.call_args_list)
        self.assertEqual(commands, ["dotnet remove /Foo/Foo.csproj package Dev",
                                    "dotnet remove /Foo/Foo.csproj package Tst",
                                    "dotnet remove /FooDev/FooDev.csproj package Tst"])

    def test_no_dependencies_means_all_nuget_packages_are_removed(self):
        self.makeProject({"name": "Foo", "version": "1", "dependencies": []})
        self.write("proj/Foo/Foo.csproj", CSPROJ.replace("</Project>",
                   '<ItemGroup><PackageReference Include="A" Version="1"/></ItemGroup></Project>'))
        system, _ = self.run_do()
        system.assert_called_once_with("dotnet remove {}/Foo/Foo.csproj package A".format(self.proj))

    def test_default_cache_path_uses_environment(self):
        variable = "LOCALAPPDATA" if os.name == "nt" else "HOME"
        base = self.path("home")
        self.write("home/TypeO/ModulesCache/Udrian/TypeOCore/0.1.0.dev/typeo.json", "{}")
        self.makeProject({"name": "Foo", "version": "1", "dependencies": ["Udrian@TypeOCore-0.1.0.dev"]})
        with mock.patch.dict(os.environ, {variable: base}), \
                mock.patch("scripts.dependency.os.system"), \
                mock.patch("scripts.dependency.downloadAndExtractDependency") as download:
            dependency.do(argparse.Namespace(projectPath=self.proj, cachePath=""))
        download.assert_not_called()
        self.assertEqual(self.refs("Foo"), ["TypeOCore"])

    def writeResolvedModules(self, entries):
        return self.write("proj/TypeO/cache/modules.json", json.dumps({
            "ResolveStamp": "stamp", "BuildStamp": None,
            "Modules": [{"Author": author, "Name": name, "Version": version}
                        for author, name, version in entries]}))

    def test_cached_versions_are_used_across_transitive_modules_and_repeated_runs(self):
        self.makeModule("Core", "2.0")
        self.makeModule("Middle", "1.0", dependencies=["Udrian@Core-1.0"])
        self.makeModule("Top", "1.0", dependencies=["Udrian@Middle-0.5", "Udrian@Core-0.5"])
        self.makeProject({"name": "Foo", "version": "1", "dependencies": [
            "Udrian@Top-0.5", "Udrian@Core-1.0"]})
        self.writeResolvedModules([("Udrian", "Core", "2.0"), ("Udrian", "Middle", "1.0"), ("Udrian", "Top", "1.0")])

        for _ in range(2):
            _, download = self.run_do()
            download.assert_not_called()
            for path in ("proj/Foo/Foo.csproj", "cache/Udrian/Middle/1.0/Middle/Middle.csproj",
                         "cache/Udrian/Top/1.0/Top/Top.csproj"):
                refs = xmler.load(self.path(path)).getElementsByTagName("ProjectReference")
                core = next(r for r in refs if r.getAttribute("Name") == "Core")
                self.assertIn("/Core/2.0/", core.getAttribute("Include"))
        self.assertEqual(json.loads(self.read("cache/Udrian/Middle/1.0/typeo.json"))["dependencies"], ["Udrian@Core-1.0"])

    def test_cached_resolution_repairs_solution_when_project_reference_is_already_current(self):
        project = "project with spaces"
        cache = "module cache with spaces"
        moduleData = {"name": "Core", "version": "2.0", "type": "module", "project": [{"Name": "Core"}]}
        self.writeTypeO("{}/Udrian/Core/2.0".format(cache), moduleData)
        newProject = "{}/Udrian/Core/2.0/Core/Core.csproj".format(self.path(cache))
        oldProject = self.path(cache, "Udrian", "Core", "1.0", "Core", "Core.csproj")
        self.write("{}/Foo/Foo.csproj".format(project), CSPROJ.replace("</Project>",
                   '<ItemGroup Label="TypeOModules"><ProjectReference Name="Core" Include="{}"/></ItemGroup></Project>'.format(newProject)))
        self.write("{}/Udrian/Core/2.0/Core/Core.csproj".format(cache), CSPROJ)
        self.writeTypeO(project, {"name": "Foo", "version": "1", "dependencies": ["Udrian@Core-1.0"]})
        resolvedPath = self.write("{}/TypeO/cache/modules.json".format(project), json.dumps({
            "Modules": [{"Author": "Udrian", "Name": "Core", "Version": "2.0"}]}))
        solution = self.write("{}/Foo.slnx".format(project),
                              '<Solution><Project Path="{}" /></Solution>'.format(oldProject.replace("\\", "/")))

        with mock.patch("scripts.dependency.os.system") as system, \
                mock.patch("scripts.dependency.downloadAndExtractDependency") as download:
            dependency.do(argparse.Namespace(projectPath=self.path(project), cachePath=self.path(cache),
                                            resolvedModules=resolvedPath))

        solutionProjects = [p.getAttribute("Path") for p in xmler.load(solution).getElementsByTagName("Project")]
        self.assertEqual(set(solutionProjects), {
            newProject.replace("\\", "/"),
            self.path(project, "Foo", "Foo.csproj").replace("\\", "/")
        })
        system.assert_not_called()
        download.assert_not_called()

    def test_cached_module_solution_keeps_and_restores_its_own_projects(self):
        self.makeModule("Core", "2.0")
        self.makeModule("Top", "1.0", devName="TopDev", dependencies=["Udrian@Core-1.0"])
        self.makeProject({"name": "Foo", "version": "1", "dependencies": ["Udrian@Top-1.0"]})
        self.writeResolvedModules([("Udrian", "Core", "2.0"), ("Udrian", "Top", "1.0")])
        solution = self.write("cache/Udrian/Top/1.0/Top.slnx", """<Solution>
  <Folder Name="/Module/">
    <Project Path="Top/Top.csproj" Build="false"/>
  </Folder>
</Solution>""")

        for _ in range(2):
            self.run_do()
            xml = xmler.load(solution)
            projects = {os.path.basename(p.getAttribute("Path")).removesuffix(".csproj"): p
                        for p in xml.getElementsByTagName("Project")}
            self.assertEqual(set(projects), {"Top", "TopDev", "Core"})
            self.assertEqual(projects["Top"].parentNode.tagName, "Folder")
            self.assertEqual(projects["Top"].getAttribute("Build"), "false")
            self.assertIn("/Core/2.0/", projects["Core"].getAttribute("Path"))

    def test_selected_versions_preserve_dependency_tags_and_nuget_versions(self):
        self.makeModule("Core", "2.0", devName="CoreDev")
        self.makeProject({"name": "Foo", "version": "1", "dependencies": [
            "Udrian@Core-1.0;dev", "Core-4.0;nuget"],
            "project": [{"Name": "Foo"}, {"Name": "FooDev", "type": "dev"}, {"Name": "FooTest", "type": "test"}]})
        self.writeResolvedModules([("Udrian", "Core", "2.0")])
        system, download = self.run_do()
        download.assert_not_called()
        self.assertEqual(self.refs("Foo"), [])
        self.assertEqual(self.refs("FooDev"), ["Core", "CoreDev"])
        self.assertEqual(self.refs("FooTest"), ["Core"])
        packageCommands = [c.args[0] for c in system.call_args_list if " package " in c.args[0]]
        self.assertEqual(len(packageCommands), 3)
        self.assertTrue(all(command.endswith("package Core -v 4.0") for command in packageCommands))

    def test_cached_local_selection_replaces_module_manifest_paths(self):
        local = self.writeTypeO("local module", {"name": "Core", "version": "2.0"})
        self.write("local module/Core/Core.csproj", CSPROJ)
        self.makeModule("Top", "1.0", dependencies=["Udrian@Core-1.0"])
        self.makeProject({"name": "Foo", "version": "1", "dependencies": ["Udrian@Top-1.0"]})
        self.writeResolvedModules([("Udrian", "Top", "1.0"), ("Udrian", "Core", "../local module;local")])
        _, download = self.run_do()
        download.assert_not_called()
        refs = xmler.load(self.path("cache/Udrian/Top/1.0/Top/Top.csproj")).getElementsByTagName("ProjectReference")
        self.assertEqual(refs[0].getAttribute("Include"), "{}/Core/Core.csproj".format(local))

    def test_module_prebuild_uses_main_typer_and_project_resolution_context(self):
        self.makeModule("Core", "2.0")
        self.makeModule("Top", "1.0", dependencies=["Udrian@Core-1.0"])
        moduleProject = "cache/Udrian/Top/1.0/Top/Top.csproj"
        self.write(moduleProject, CSPROJ.replace("</Project>", """
<Target Name="PreBuild" BeforeTargets="PreBuildEvent">
  <Exec Condition="windows" Command="typer/typer.bat dependency -p .."/>
  <Exec Condition="unix" Command="bash typer/typer.sh dependency -p .."/>
  <Exec Command="echo custom"/>
</Target></Project>"""))
        self.makeProject({"name": "Foo", "version": "1", "dependencies": ["Udrian@Top-1.0"]})
        resolvedPath = self.writeResolvedModules([("Udrian", "Core", "2.0"), ("Udrian", "Top", "1.0")])
        self.run_do()
        commands = [e.getAttribute("Command") for e in xmler.load(self.path(moduleProject)).getElementsByTagName("Exec")]
        self.assertEqual(commands[0], commands[1])
        self.assertEqual(commands[2], "echo custom")
        argv = shlex.split(commands[0])
        self.assertEqual(argv[1], os.path.join(os.path.dirname(os.path.dirname(dependency.__file__)), "typer.py"))
        parser = argparse.ArgumentParser()
        dependency.parse(parser)
        args = parser.parse_args(argv[3:])
        self.assertEqual(args.resolvedModules, os.path.abspath(resolvedPath))
        with mock.patch("scripts.dependency.os.system"), mock.patch("scripts.dependency.downloadAndExtractDependency") as download:
            dependency.do(args)
        download.assert_not_called()
        completed = subprocess.run(commands[0], shell=True, capture_output=True, text=True, timeout=30)
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertNotIn("error", completed.stderr.lower())
        refs = xmler.load(self.path(moduleProject)).getElementsByTagName("ProjectReference")
        self.assertIn("/Core/2.0/", refs[0].getAttribute("Include"))

    def test_selected_download_receives_root_cache_context(self):
        self.makeProject({"name": "Foo", "version": "1", "dependencies": ["Udrian@Core-1.0"]})
        resolvedPath = self.writeResolvedModules([("Udrian", "Core", "2.0")])
        def download(selected, modulePath, context, cachePath):
            self.makeModule(selected.name, selected.version)

        with mock.patch("scripts.dependency.os.system"), \
                mock.patch("scripts.dependency.downloadAndExtractDependency", side_effect=download) as fetch:
            dependency.do(argparse.Namespace(projectPath=self.proj, cachePath=self.cache))
        selected, modulePath, context, cachePath = fetch.call_args.args
        self.assertEqual(selected.version, "2.0")
        self.assertEqual(modulePath, "{}/Udrian/Core/2.0".format(self.cache))
        self.assertEqual(context, os.path.abspath(resolvedPath))
        self.assertEqual(cachePath, self.cache)
        self.assertEqual(self.refs("Foo"), ["Core"])

    def test_prepared_msbuild_skips_dependency_hook_but_preserves_custom_tasks(self):
        projectPath = self.write("prepared/Mod/Mod.csproj", """<Project>
<Target Name="PreBuild">
  <Exec Command="typer dependency -p .."/>
  <Message Text="custom-task-ran" Importance="high"/>
</Target></Project>""")
        missingCache = self.path("missing modules.json")
        dependency.updateResolutionHook(projectPath, self.path("prepared"), self.cache, missingCache)
        dependency.updateResolutionHook(projectPath, self.path("prepared"), self.cache, missingCache)
        condition = xmler.load(projectPath).getElementsByTagName("Exec")[0].getAttribute("Condition")
        self.assertEqual(condition.count("$(TypeODependenciesResolved)"), 1)

        command = ["dotnet", "msbuild", projectPath, "-t:PreBuild", "-v:minimal", "-nologo"]
        ordinary = subprocess.run(command, capture_output=True, text=True, timeout=30)
        self.assertNotEqual(ordinary.returncode, 0)
        self.assertIn("FileNotFoundError", ordinary.stdout + ordinary.stderr)
        prepared = subprocess.run(command + ["-p:TypeODependenciesResolved=true"],
                                  capture_output=True, text=True, timeout=30)
        self.assertEqual(prepared.returncode, 0, prepared.stdout + prepared.stderr)
        self.assertIn("custom-task-ran", prepared.stdout)

    def test_cycles_are_resolved_once_per_module(self):
        self.makeModule("A", "2.0", dependencies=["Udrian@B-1.0"])
        self.makeModule("B", "2.0", dependencies=["Udrian@A-1.0"])
        self.makeProject({"name": "Foo", "version": "1", "dependencies": ["Udrian@A-1.0"]})
        self.writeResolvedModules([("Udrian", "A", "2.0"), ("Udrian", "B", "2.0")])
        _, download = self.run_do()
        download.assert_not_called()
        self.assertEqual(self.refs("Foo"), ["A"])
        for name, other in (("A", "B"), ("B", "A")):
            refs = xmler.load(self.path("cache/Udrian/{}/2.0/{}/{}.csproj".format(name, name, name))).getElementsByTagName("ProjectReference")
            self.assertIn("/{}/2.0/".format(other), refs[0].getAttribute("Include"))

    def test_conflicting_cache_versions_fail_before_changing_project(self):
        self.makeProject({"name": "Foo", "version": "1", "dependencies": ["Udrian@Core-1.0"]})
        self.writeResolvedModules([("Udrian", "Core", "1.0"), ("Udrian", "Core", "2.0")])
        before = self.read("proj/Foo/Foo.csproj")
        with self.assertRaisesRegex(ValueError, "Conflicting resolved versions"):
            self.run_do()
        self.assertEqual(self.read("proj/Foo/Foo.csproj"), before)

    def test_explicit_missing_resolution_cache_fails(self):
        with self.assertRaises(FileNotFoundError):
            dependency.do(argparse.Namespace(projectPath=self.proj, cachePath=self.cache,
                                            resolvedModules=self.path("missing.json")))


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

    def test_project_context_bootstraps_with_main_typer_without_module_submodule(self):
        target = self.path("cache with spaces", "TypeOCore", "0.1.0")
        resolvedPath = self.path("project with spaces", "TypeO", "cache", "modules.json")
        with mock.patch("scripts.dependency.urllib.request.urlretrieve", side_effect=self.fakeDownload), \
                mock.patch("scripts.dependency.os.system") as system, \
                mock.patch("scripts.dependency.subprocess.run") as run:
            dependency.downloadAndExtractDependency(dep("Udrian@TypeOCore-0.1.0"), target, resolvedPath, self.tmp)
        system.assert_not_called()
        argv = run.call_args.args[0]
        self.assertEqual(argv[1], os.path.join(os.path.dirname(os.path.dirname(dependency.__file__)), "typer.py"))
        self.assertEqual(argv[2:], ["generate", "-p", target, "-c", self.tmp, "--resolvedModules", resolvedPath])
        self.assertTrue(run.call_args.kwargs["check"])


if __name__ == "__main__":
    unittest.main()
