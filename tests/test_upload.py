import argparse, unittest
from unittest import mock

from scripts import upload
from tests.support import TempDirTestCase


class ParseTests(unittest.TestCase):
    def test_project_path_required(self):
        p = argparse.ArgumentParser()
        upload.parse(p)
        self.assertEqual(p.parse_args(["-p", "x"]).projectPath, "x")
        with self.assertRaises(SystemExit):
            with mock.patch("sys.stderr"):
                p.parse_args([])


class DoTests(TempDirTestCase):
    def run_do(self, branch, version="1.2.3"):
        self.writeTypeO("proj", {"name": "Foo", "version": version})
        popen = mock.Mock()
        popen.return_value.read.return_value = branch
        with mock.patch("scripts.upload.os.popen", popen), mock.patch("scripts.upload.os.system") as system:
            upload.do(argparse.Namespace(projectPath=self.path("proj")))
        return popen, [c.args[0] for c in system.call_args_list]

    def test_main_branch_tags_plain_version(self):
        popen, commands = self.run_do("main\n")
        self.assertIn("git branch --show-current", popen.call_args.args[0])
        self.assertEqual(commands, [
            "cd {} && git tag -f 1.2.3".format(self.path("proj")),
            "cd {} && git push -f origin 1.2.3".format(self.path("proj"))])

    def test_master_branch_tags_plain_version(self):
        _, commands = self.run_do("master\n")
        self.assertTrue(commands[0].endswith("git tag -f 1.2.3"))

    def test_other_branch_appends_branch_name(self):
        _, commands = self.run_do("feature\n", version="0.1.0")
        self.assertTrue(commands[0].endswith("git tag -f 0.1.0.feature"))
        self.assertTrue(commands[1].endswith("git push -f origin 0.1.0.feature"))

    def test_missing_typeo_json_raises(self):
        with self.assertRaises(FileNotFoundError):
            upload.do(argparse.Namespace(projectPath=self.tmp))


if __name__ == "__main__":
    unittest.main()
