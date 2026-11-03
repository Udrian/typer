import argparse, os, unittest
from unittest import mock

from scripts import build
from tests.support import TempDirTestCase


class ParseTests(unittest.TestCase):
    def parse(self, argv):
        p = argparse.ArgumentParser()
        build.parse(p)
        return p.parse_args(argv)

    def test_defaults(self):
        args = self.parse(["-p", "proj", "-b", "7"])
        self.assertEqual((args.projectPath, args.buildNumber, args.config, args.output),
                         ("proj", 7, "Release", "bin"))

    def test_build_number_is_int_and_required(self):
        with self.assertRaises(SystemExit):
            with mock.patch("sys.stderr"):
                self.parse(["-p", "proj"])
        with self.assertRaises(SystemExit):
            with mock.patch("sys.stderr"):
                self.parse(["-p", "proj", "-b", "x"])

    def test_config_choices(self):
        self.assertEqual(self.parse(["-p", "p", "-b", "1", "-c", "Debug"]).config, "Debug")
        with self.assertRaises(SystemExit):
            with mock.patch("sys.stderr"):
                self.parse(["-p", "p", "-b", "1", "-c", "Other"])


class BuildTests(TempDirTestCase):
    def test_publishes_project_with_versioned_command(self):
        with mock.patch("scripts.build.os.system") as system:
            build.build("Foo", "bin", "Release", 5, "0.1.0", "proj")
        system.assert_called_once_with(
            "dotnet publish proj/Foo/Foo.csproj --configuration Release --output bin/build/Foo/Release "
            "--verbosity n /property:Version=0.1.0.5")

    def test_existing_output_folder_is_cleaned(self):
        output = self.path("bin")
        stale = self.write("bin/build/Foo/Debug/stale.dll", "x")
        with mock.patch("scripts.build.os.system"):
            build.build("Foo", output, "Debug", 1, "0.1.0", "proj")
        self.assertFalse(os.path.exists(stale))

    def test_other_configurations_are_kept(self):
        keep = self.write("bin/build/Foo/Release/keep.dll", "x")
        with mock.patch("scripts.build.os.system"):
            build.build("Foo", self.path("bin"), "Debug", 1, "0.1.0", "proj")
        self.assertTrue(os.path.exists(keep))

    def run_do(self, data):
        self.writeTypeO("proj", data)
        args = argparse.Namespace(projectPath=self.path("proj"), buildNumber=3, config="Release", output="bin")
        with mock.patch("scripts.build.os.system") as system:
            build.do(args)
        return [call.args[0] for call in system.call_args_list]

    def test_do_builds_main_project_only(self):
        commands = self.run_do({"name": "Foo", "version": "1.0.0"})
        self.assertEqual(len(commands), 1)
        self.assertIn("Foo/Foo.csproj", commands[0])
        self.assertIn("Version=1.0.0.3", commands[0])

    def test_do_builds_dev_module_too(self):
        commands = self.run_do({"name": "Foo", "version": "1.0.0", "project": [
            {"Name": "Foo"}, {"Name": "TypeDFoo", "isDev": True}, {"Name": "FooTest", "isTest": True}]})
        self.assertEqual(len(commands), 2)
        self.assertIn("Foo/Foo.csproj", commands[0])
        self.assertIn("TypeDFoo/TypeDFoo.csproj", commands[1])
        self.assertFalse(any("FooTest" in c for c in commands))


if __name__ == "__main__":
    unittest.main()
