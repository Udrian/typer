import argparse, os, unittest, zipfile

from scripts import pack
from tests.support import TempDirTestCase


class NamingTests(unittest.TestCase):
    def test_output_path(self):
        self.assertEqual(pack.getOutputPath("bin", "Foo"), "bin/package/Foo")

    def test_zip_path_name(self):
        self.assertEqual(pack.getZipPathName("bin/package/Foo", "Foo", "1.2.3"), "bin/package/Foo/Foo-1.2.3.zip")


class ParseTests(unittest.TestCase):
    def test_defaults_and_choices(self):
        p = argparse.ArgumentParser()
        pack.parse(p)
        args = p.parse_args(["-p", "proj"])
        self.assertEqual((args.projectPath, args.config, args.output), ("proj", "Release", "bin"))
        self.assertEqual(p.parse_args(["-p", "x", "-c", "Debug"]).config, "Debug")


class AddFileToZipTests(TempDirTestCase):
    def test_adds_existing_file_at_root_of_zip(self):
        source = self.write("sub/a.txt", "data")
        zipPath = self.path("out.zip")
        with zipfile.ZipFile(zipPath, "w") as z:
            self.assertTrue(pack.addFileToZip(z, source, ""))
        with zipfile.ZipFile(zipPath) as z:
            self.assertEqual(z.namelist(), ["a.txt"])
            self.assertEqual(z.read("a.txt"), b"data")

    def test_adds_file_into_zip_subfolder(self):
        source = self.write("a.txt", "data")
        zipPath = self.path("out.zip")
        with zipfile.ZipFile(zipPath, "w") as z:
            pack.addFileToZip(z, source, "lib")
        with zipfile.ZipFile(zipPath) as z:
            self.assertEqual(z.namelist(), ["lib/a.txt"])

    def test_missing_file_returns_false_and_adds_nothing(self):
        zipPath = self.path("out.zip")
        with zipfile.ZipFile(zipPath, "w") as z:
            self.assertFalse(pack.addFileToZip(z, self.path("missing.txt"), ""))
        with zipfile.ZipFile(zipPath) as z:
            self.assertEqual(z.namelist(), [])


class PackTests(TempDirTestCase):
    def setUp(self):
        super().setUp()
        self.out = self.path("out")
        self.projectDir = self.path("proj")

    def makeProject(self, data, buildFiles=(), projectFiles=()):
        data.setdefault("version", "0.1.0")
        self.writeTypeO("proj", data)
        self.write("proj/Readme-TypeO.txt", "readme")
        self.write("proj/ReleaseNotes-{}.txt".format(data["name"]), "notes")
        for name in buildFiles:
            self.write("out/build/{}".format(name), "x")
        for name in projectFiles:
            self.write("proj/{}".format(name), "x")

    def run_pack(self):
        pack.do(argparse.Namespace(projectPath=self.projectDir, config="Release", output=self.out))

    def zipNames(self, name="Foo", version="0.1.0"):
        zipPath = os.path.join(self.out, "package", name, "{}-{}.zip".format(name, version))
        self.assertTrue(os.path.isfile(zipPath), zipPath)
        with zipfile.ZipFile(zipPath) as z:
            return sorted(z.namelist())

    def test_packs_build_output_docs_and_typeo_json(self):
        self.makeProject({"name": "Foo"}, buildFiles=[
            "Foo/Release/Foo.dll", "Foo/Release/Foo.xml", "Foo/Release/Foo.exe",
            "Foo/Release/Foo.runtimeconfig.json", "Foo/Release/Other.dll"])
        self.run_pack()
        self.assertEqual(self.zipNames(), sorted([
            "Foo.dll", "Foo.xml", "Foo.exe", "Foo.runtimeconfig.json",
            "Readme-TypeO.txt", "ReleaseNotes-Foo.txt", "typeo.json"]))

    def test_legacy_product_file_is_not_packed(self):
        self.makeProject({"name": "Foo"}, buildFiles=["Foo/Release/Foo.dll"], projectFiles=["product"])
        self.run_pack()
        self.assertNotIn("product", self.zipNames())

    def test_uses_version_in_zip_name(self):
        self.makeProject({"name": "Foo", "version": "2.5.0"}, buildFiles=["Foo/Release/Foo.dll"])
        self.run_pack()
        self.assertIn("Foo.dll", self.zipNames(version="2.5.0"))

    def test_missing_build_output_still_packs_docs(self):
        self.makeProject({"name": "Foo"})
        self.run_pack()
        self.assertEqual(self.zipNames(), ["Readme-TypeO.txt", "ReleaseNotes-Foo.txt", "typeo.json"])

    def test_includes_dev_module_build_output(self):
        self.makeProject({"name": "Foo", "project": [
            {"Name": "Foo"}, {"Name": "TypeDFoo", "isDev": True}]},
            buildFiles=["Foo/Release/Foo.dll", "TypeDFoo/Release/TypeDFoo.dll", "TypeDFoo/Release/TypeDFoo.xml"])
        self.run_pack()
        names = self.zipNames()
        self.assertIn("TypeDFoo.dll", names)
        self.assertIn("TypeDFoo.xml", names)

    def test_dev_module_is_ignored_when_not_declared(self):
        self.makeProject({"name": "Foo"}, buildFiles=["Foo/Release/Foo.dll", "TypeDFoo/Release/TypeDFoo.dll"])
        self.run_pack()
        self.assertNotIn("TypeDFoo.dll", self.zipNames())

    def test_externals_from_project_root_are_packed(self):
        self.makeProject({"name": "Foo", "externals": ["Shaders/a.frag"]}, projectFiles=["Shaders/a.frag"])
        self.run_pack()
        self.assertIn("a.frag", self.zipNames())

    def test_externals_from_project_module_folder_are_packed(self):
        self.makeProject({"name": "Foo", "externals": ["data.bin"]}, projectFiles=["Foo/data.bin"])
        self.run_pack()
        self.assertIn("data.bin", self.zipNames())

    def test_externals_from_build_output_are_packed(self):
        self.makeProject({"name": "Foo", "externals": ["res.txt"]}, buildFiles=["Foo/Release/res.txt"])
        self.run_pack()
        self.assertIn("res.txt", self.zipNames())

    def test_external_directory_contents_are_packed(self):
        self.makeProject({"name": "Foo", "externals": ["Shaders"]},
                         projectFiles=["Shaders/a.frag", "Shaders/b.vert"])
        self.run_pack()
        names = self.zipNames()
        self.assertIn("a.frag", names)
        self.assertIn("b.vert", names)

    def test_missing_external_is_reported_not_fatal(self):
        self.makeProject({"name": "Foo", "externals": ["nope.txt"]})
        self.run_pack()
        self.assertNotIn("nope.txt", self.zipNames())


if __name__ == "__main__":
    unittest.main()
