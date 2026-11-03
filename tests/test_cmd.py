import contextlib, io, sys, unittest

from scripts import cmd


class CmdTests(unittest.TestCase):
    def test_exec_returns_stdout(self):
        self.assertEqual(cmd.exec("echo hello", False).strip(), "hello")

    def test_exec_prints_output_by_default(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            result = cmd.exec("echo hello")
        self.assertIn("hello", out.getvalue())
        self.assertEqual(result.strip(), "hello")

    def test_exec_can_suppress_printing(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            cmd.exec("echo hello", False)
        self.assertEqual(out.getvalue(), "")

    def test_exist_matches_line_start(self):
        self.assertTrue(cmd.exist("echo foo bar", "foo"))

    def test_exist_matches_line_end(self):
        self.assertTrue(cmd.exist("echo foo bar", "bar"))

    def test_exist_does_not_match_middle_of_line(self):
        self.assertFalse(cmd.exist("echo foo bar baz", "bar"))

    def test_exist_false_when_absent(self):
        self.assertFalse(cmd.exist("echo foo", "nope"))

    def test_exist_checks_every_line(self):
        command = '"{}" -c "print(\'one\\ntwo\\nthree\')"'.format(sys.executable)
        self.assertTrue(cmd.exist(command, "two"))
        self.assertFalse(cmd.exist(command, "four"))


if __name__ == "__main__":
    unittest.main()
