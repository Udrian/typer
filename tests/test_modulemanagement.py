import argparse, contextlib, io, json, os, unittest
from unittest import mock

from scripts import addoverride, product, removeoverride, dependencies, modules, update
from scripts import list as listing
from tests.support import TempDirTestCase


def tag(version):
    return {"version": version, "zip": "zip/" + version}


class ModulesTests(TempDirTestCase):
    def test_lists_registered_modules_with_versions(self):
        registry = self.write("modules.json", json.dumps(["Udrian/A", "Other/B"]))
        tags = {"A": [tag("0.2.0"), tag("0.1.0")], "B": None}
        with mock.patch.object(listing, "fetch", side_effect=lambda a, n: tags[n]):
            result = modules.modules(registry)
        self.assertEqual(result, [
            {"author": "Udrian", "name": "A", "versions": tags["A"]},
            {"author": "Other", "name": "B", "versions": []}])

    def test_default_registry_exists(self):
        with open(modules.defaultRegistry()) as f:
            self.assertTrue(all("/" in entry for entry in json.load(f)))

    def test_do_prints_json(self):
        registry = self.write("modules.json", "[]")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            modules.do(argparse.Namespace(registry=registry))
        self.assertEqual(json.loads(out.getvalue()), [])


class DependenciesTests(TempDirTestCase):
    def test_flags_overridden_dependencies_with_declared_version(self):
        root = self.writeTypeO("p", {"name": "P", "version": "1", "dependencies": [
            "Udrian@TypeOCore-0.1.0", "Pkg-1.0;nuget", "Udrian@TypeD-0.1.0;dev"]},
            override=["Udrian@TypeOCore-C:/dev/my-core;local"])
        result = {(d["name"], tuple(d["tags"])): d for d in dependencies.dependencies(root)}
        core = result[("TypeOCore", ())]
        self.assertEqual((core["version"], core["overridden"], core["localPath"]), ("0.1.0", True, "C:/dev/my-core"))
        self.assertTrue(result[("Pkg", ())]["nuget"])
        self.assertFalse(result[("TypeD", ("dev",))]["overridden"])

    def test_relative_local_paths_are_resolved_from_main_project_folder(self):
        root = self.writeTypeO("p", {"name": "P", "version": "1", "dependencies": ["Udrian@TypeOTK-0.1.0"],
            "project": [{"Name": "P", "type": ""}]}, override=["Udrian@TypeOTK-../../typeotk;local"])
        os.makedirs(os.path.join(root, "P"))
        self.assertEqual(dependencies.dependencies(root)[0]["localPath"],
                         os.path.normpath(os.path.join(root, "..", "typeotk")).replace("\\", "/"))


class OverrideTests(TempDirTestCase):
    def setUp(self):
        super().setUp()
        self.root = self.writeTypeO("p", {"name": "P", "version": "1", "dependencies": ["Udrian@TypeOCore-0.1.0", "Udrian@TypeD-0.1.0;dev"]})
        self.local = self.writeTypeO("core", {"name": "TypeOCore", "version": "9"})

    def overrides(self):
        with open(os.path.join(self.root, "typeo_override.json")) as f:
            return json.load(f)

    def test_adds_local_override_and_keeps_author_and_tags(self):
        addoverride.addOverride(self.root, "TypeD", self.local)
        self.assertEqual(self.overrides(), ["Udrian@TypeD-{};local;dev".format(self.local.replace("\\", "/"))])

    def test_replaces_existing_override(self):
        addoverride.addOverride(self.root, "TypeOCore", self.local)
        addoverride.addOverride(self.root, "TypeOCore", self.local)
        self.assertEqual(len(self.overrides()), 1)

    def test_rejects_unknown_dependency_and_non_typeo_path(self):
        with self.assertRaises(SystemExit):
            addoverride.addOverride(self.root, "Nope", self.local)
        with self.assertRaises(SystemExit):
            addoverride.addOverride(self.root, "TypeOCore", self.path("missing"))

    def test_override_resolves_through_product(self):
        addoverride.addOverride(self.root, "TypeOCore", self.local)
        core = next(d for d in product.load(self.root).dependencies if d.name == "TypeOCore")
        self.assertTrue(core.local)
        self.assertEqual(core.version, self.local.replace("\\", "/"))

    def test_remove_override(self):
        addoverride.addOverride(self.root, "TypeOCore", self.local)
        removeoverride.removeOverride(self.root, "TypeOCore")
        self.assertEqual(self.overrides(), [])
        with self.assertRaises(SystemExit):
            removeoverride.removeOverride(self.root, "TypeOCore")


class UpdateTests(TempDirTestCase):
    def setUp(self):
        super().setUp()
        self.root = self.writeTypeO("p", {"name": "P", "version": "1", "dependencies": [
            "Udrian@TypeOCore-0.1.0", "Udrian@TypeD-0.1.0;dev", "Pkg-1.0;nuget", "Udrian@Loc-C:/x;local"]})

    def dependencies(self):
        with open(os.path.join(self.root, "typeo.json")) as f:
            return json.load(f)["dependencies"]

    def fetch(self, *versions):
        return mock.patch.object(listing, "fetch", return_value=[tag(v) for v in versions])

    def test_updates_to_latest_release_keeping_tags(self):
        with self.fetch("0.10.0", "0.9.0", "0.1.0", "0.11.0.feature"):
            update.updateDependencies(self.root)
        self.assertEqual(self.dependencies(), ["Udrian@TypeOCore-0.10.0", "Udrian@TypeD-0.10.0;dev", "Pkg-1.0;nuget", "Udrian@Loc-C:/x;local"])

    def test_named_update_to_given_version_needs_no_fetch(self):
        with mock.patch.object(listing, "fetch") as fetch:
            update.updateDependencies(self.root, "TypeOCore", "0.0.5")
        fetch.assert_not_called()
        self.assertEqual(self.dependencies()[0], "Udrian@TypeOCore-0.0.5")

    def test_up_to_date_changes_nothing(self):
        with self.fetch("0.1.0"):
            self.assertEqual(update.updateDependencies(self.root), [])

    def test_errors(self):
        for args in (("Nope", ""), ("Pkg", ""), ("Loc", ""), ("", "1.0")):
            with self.assertRaises(SystemExit), self.fetch("1.0"):
                update.updateDependencies(self.root, *args)
        with self.assertRaises(SystemExit), mock.patch.object(listing, "fetch", return_value=None):
            update.updateDependencies(self.root, "TypeOCore")


if __name__ == "__main__":
    unittest.main()
