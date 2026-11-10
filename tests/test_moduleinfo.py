import argparse, contextlib, io, json, unittest
from unittest import mock

from scripts import moduleinfo
from tests.support import TempDirTestCase


class Response:
    def __init__(self, ok=True, payload=None):
        self.ok = ok
        self.content = json.dumps(payload if payload is not None else {}).encode()


class ModuleInfoTests(TempDirTestCase):
    def test_arguments(self):
        p = argparse.ArgumentParser()
        moduleinfo.parse(p)
        args = p.parse_args(["-a", "Udrian", "-n", "TypeOCore", "-v", "0.1.0"])
        self.assertEqual((args.authorName, args.projectName, args.version, args.cachePath),
                         ("Udrian", "TypeOCore", "0.1.0", ""))
        with self.assertRaises(SystemExit):
            with mock.patch("sys.stderr"):
                p.parse_args(["-a", "Udrian", "-n", "TypeOCore"])

    def test_reads_cached_module_without_fetching(self):
        product = {"name": "TypeOCore", "version": "0.1.0", "dependencies": ["Udrian@TypeD-0.1.0;dev"]}
        self.write("cache/Udrian/TypeOCore/0.1.0/typeo.json", json.dumps(product))
        with mock.patch("scripts.moduleinfo.requests.get") as get:
            result = moduleinfo.fetch("Udrian", "TypeOCore", "0.1.0", self.path("cache"))
        get.assert_not_called()
        self.assertEqual(result, product)

    def test_fetches_uncached_module_from_github(self):
        product = {"name": "TypeOCore", "version": "0.2.0"}
        with mock.patch("scripts.moduleinfo.requests.get", return_value=Response(payload=product)) as get:
            result = moduleinfo.fetch("Udrian", "TypeOCore", "0.2.0", self.path("cache"))
        get.assert_called_once_with("https://raw.githubusercontent.com/Udrian/TypeOCore/0.2.0/typeo.json")
        self.assertEqual(result, product)

    def test_failed_fetch_returns_none(self):
        with mock.patch("scripts.moduleinfo.requests.get", return_value=Response(ok=False)):
            self.assertIsNone(moduleinfo.fetch("Udrian", "TypeOCore", "9.9.9", self.path("cache")))

    def test_do_prints_json(self):
        product = {"name": "TypeOCore", "version": "0.2.0"}
        out = io.StringIO()
        with mock.patch("scripts.moduleinfo.requests.get", return_value=Response(payload=product)), contextlib.redirect_stdout(out):
            moduleinfo.do(argparse.Namespace(authorName="Udrian", projectName="TypeOCore", version="0.2.0", cachePath=self.path("cache")))
        self.assertEqual(json.loads(out.getvalue()), product)

    def test_do_exits_when_unavailable(self):
        with mock.patch("scripts.moduleinfo.requests.get", return_value=Response(ok=False)):
            with self.assertRaises(SystemExit):
                moduleinfo.do(argparse.Namespace(authorName="Udrian", projectName="TypeOCore", version="9.9.9", cachePath=self.path("cache")))


if __name__ == "__main__":
    unittest.main()
