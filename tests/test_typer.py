import contextlib, io, sys, unittest
from unittest import mock

import typer


class MainTests(unittest.TestCase):
    def run_main(self, *argv):
        with mock.patch.object(sys, "argv", ["typer.py", *argv]):
            typer.main()

    def assert_dispatch(self, command, argv, expectedAttributes):
        with mock.patch("scripts.{}.do".format(command)) as target:
            self.run_main(command, *argv)
        target.assert_called_once()
        args = target.call_args.args[0]
        self.assertEqual(args.command, command)
        for key, value in expectedAttributes.items():
            self.assertEqual(getattr(args, key), value, key)

    def test_build(self):
        self.assert_dispatch("build", ["-p", "proj", "-b", "4"], {"projectPath": "proj", "buildNumber": 4, "config": "Release"})

    def test_pack(self):
        self.assert_dispatch("pack", ["-p", "proj", "-c", "Debug"], {"projectPath": "proj", "config": "Debug"})

    def test_upload(self):
        self.assert_dispatch("upload", ["-p", "proj"], {"projectPath": "proj"})

    def test_dependency(self):
        self.assert_dispatch("dependency", ["-p", "proj", "-c", "cache"], {"projectPath": "proj", "cachePath": "cache"})

    def test_new(self):
        self.assert_dispatch("new", ["-n", "Foo", "-o", "out", "-t", "exe"], {"name": "Foo", "output": "out", "type": "exe"})

    def test_generate(self):
        self.assert_dispatch("generate", ["-p", "proj"], {"projectPath": "proj"})

    def test_list(self):
        self.assert_dispatch("list", ["-a", "Udrian", "-n", "TypeOCore"], {"authorName": "Udrian", "projectName": "TypeOCore"})

    def test_addproject(self):
        self.assert_dispatch("addproject", ["-p", "proj", "-n", "Bar", "-t", "test", "--depends_on", "Foo"],
                             {"projectPath": "proj", "name": "Bar", "type": "test", "depends_on": ["Foo"]})

    def test_removeproject(self):
        self.assert_dispatch("removeproject", ["-p", "proj", "-n", "Bar"], {"projectPath": "proj", "name": "Bar"})

    def test_only_the_selected_command_runs(self):
        patches = {name: mock.patch("scripts.{}.do".format(name)) for name in
                   ("build", "pack", "upload", "dependency", "new", "generate", "list", "addproject", "removeproject")}
        mocks = {name: p.start() for name, p in patches.items()}
        self.addCleanup(lambda: [p.stop() for p in patches.values()])
        self.run_main("upload", "-p", "proj")
        for name, m in mocks.items():
            self.assertEqual(m.called, name == "upload", name)

    def test_no_command_prints_help(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.run_main()
        text = out.getvalue()
        self.assertIn("usage", text.lower())
        for name in ("build", "pack", "upload", "dependency", "new", "generate", "list", "addproject", "removeproject"):
            self.assertIn(name, text)

    def test_unknown_command_exits_with_error(self):
        with self.assertRaises(SystemExit) as raised, mock.patch("sys.stderr"):
            self.run_main("bogus")
        self.assertEqual(raised.exception.code, 2)

    def test_missing_required_argument_exits_with_error(self):
        with self.assertRaises(SystemExit) as raised, mock.patch("sys.stderr"):
            self.run_main("build", "-p", "proj")
        self.assertEqual(raised.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
