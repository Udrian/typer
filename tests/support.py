import json, os, shutil, tempfile, unittest
from xml.dom import minidom

CSPROJ = """<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>net8.0</TargetFramework>
    <Nullable>enable</Nullable>
  </PropertyGroup>
</Project>
"""


class TempDirTestCase(unittest.TestCase):
    """Gives each test an isolated temp directory and restores the working directory afterwards."""

    def setUp(self):
        self._cwd = os.getcwd()
        self.tmp = os.path.realpath(tempfile.mkdtemp(prefix="typertest_"))
        self.addCleanup(self._cleanup)

    def _cleanup(self):
        os.chdir(self._cwd)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def path(self, *parts):
        return os.path.join(self.tmp, *parts)

    def write(self, relativePath, content=""):
        full = self.path(relativePath)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w") as f:
            f.write(content)
        return full

    def read(self, relativePath):
        with open(self.path(relativePath)) as f:
            return f.read()

    def writeTypeO(self, relativeDir, data, override=None):
        base = relativeDir.strip("/\\")
        prefix = base + "/" if base else ""
        self.write(prefix + "typeo.json", json.dumps(data))
        if override is not None:
            self.write(prefix + "typeo_override.json", json.dumps(override))
        return self.path(base) if base else self.tmp


def parseXml(text=CSPROJ):
    return minidom.parseString(text)
