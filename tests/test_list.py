import argparse, contextlib, io, json, unittest
from unittest import mock

from scripts import list as listing


class Response:
    def __init__(self, ok=True, payload=None):
        self.ok = ok
        self.content = json.dumps(payload if payload is not None else []).encode()


class ParseTests(unittest.TestCase):
    def test_arguments(self):
        p = argparse.ArgumentParser()
        listing.parse(p)
        args = p.parse_args(["-a", "Udrian", "-n", "TypeOCore"])
        self.assertEqual((args.authorName, args.projectName), ("Udrian", "TypeOCore"))
        with self.assertRaises(SystemExit):
            with mock.patch("sys.stderr"):
                p.parse_args(["-a", "Udrian"])


class ListTests(unittest.TestCase):
    def run_list(self, response):
        out = io.StringIO()
        with mock.patch("scripts.list.requests.get", return_value=response) as get, contextlib.redirect_stdout(out):
            listing.list("Udrian", "TypeOCore")
        return get, out.getvalue()

    def test_requests_github_tags_for_project(self):
        get, _ = self.run_list(Response())
        get.assert_called_once_with("https://api.github.com/repos/Udrian/TypeOCore/tags")

    def test_prints_versions_and_zip_urls_as_json(self):
        _, out = self.run_list(Response(payload=[
            {"name": "0.2.0", "zipball_url": "https://example/0.2.0", "extra": 1},
            {"name": "0.1.0", "zipball_url": "https://example/0.1.0"}]))
        self.assertEqual(json.loads(out), [
            {"version": "0.2.0", "zip": "https://example/0.2.0"},
            {"version": "0.1.0", "zip": "https://example/0.1.0"}])

    def test_no_tags_prints_empty_list(self):
        _, out = self.run_list(Response(payload=[]))
        self.assertEqual(json.loads(out), [])

    def test_failed_request_prints_nothing(self):
        _, out = self.run_list(Response(ok=False))
        self.assertEqual(out, "")

    def test_do_forwards_arguments(self):
        with mock.patch("scripts.list.list") as inner:
            listing.do(argparse.Namespace(authorName="A", projectName="P"))
        inner.assert_called_once_with("A", "P")


if __name__ == "__main__":
    unittest.main()
