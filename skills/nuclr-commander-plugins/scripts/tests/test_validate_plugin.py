#!/usr/bin/env python3
"""Fixture-driven tests for validate_plugin.py.

Run from anywhere:  python3 scripts/tests/test_validate_plugin.py
"""

from __future__ import annotations

import contextlib
import copy
import io
import json
import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import validate_plugin  # noqa: E402


POM = """<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
  <modelVersion>4.0.0</modelVersion>
  <groupId>dev.example</groupId>
  <artifactId>plugin-demo</artifactId>
  <version>1.0.0</version>
  <properties>
    <maven.compiler.release>25</maven.compiler.release>
    <platform.sdk.version>4.0.0</platform.sdk.version>
  </properties>
  <dependencies>
    <dependency>
      <groupId>dev.nuclr</groupId>
      <artifactId>platform-sdk</artifactId>
      <version>${platform.sdk.version}</version>
      <scope>provided</scope>
    </dependency>
  </dependencies>
</project>
"""

ASSEMBLY = """<assembly>
  <id>plugin</id>
  <formats><format>zip</format></formats>
  <includeBaseDirectory>false</includeBaseDirectory>
</assembly>
"""

SOURCE_MANIFEST = {
    "schemaVersion": 1,
    "version": "${project.version}",
    "platformSdkVersion": "${platform.sdk.version}",
    "plugins": [
        {
            "class": "dev.example.demo.DemoQuickView",
            "type": "QuickView",
            "id": "dev.example.demo",
            "name": "Demo",
            "author": "Example",
            "license": "Apache-2.0",
            "developer": "Community",
            "singleton": False,
            "priority": 100,
            "version": "${project.version}",
        }
    ],
}

JAVA = """package dev.example.demo;

import dev.nuclr.platform.plugin.QuickViewNuclrPlugin;

public class DemoQuickView implements QuickViewNuclrPlugin {
}
"""


def write_project(root: Path, manifest: dict) -> Path:
    project = root / "plugin-demo"
    (project / "src" / "main" / "resources").mkdir(parents=True)
    (project / "src" / "main" / "java" / "dev" / "example" / "demo").mkdir(parents=True)
    (project / "src" / "assembly").mkdir(parents=True)
    (project / "pom.xml").write_text(POM, encoding="utf-8")
    (project / "src" / "assembly" / "plugin.xml").write_text(ASSEMBLY, encoding="utf-8")
    (project / "src" / "main" / "resources" / "plugin.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8")
    (project / "src" / "main" / "java" / "dev" / "example" / "demo" / "DemoQuickView.java").write_text(
        JAVA, encoding="utf-8")
    return project


def write_bundle(project: Path, manifest: dict, name: str = "plugin-demo-1.0.0.zip") -> Path:
    target = project / "target"
    target.mkdir(exist_ok=True)
    jar_bytes = io.BytesIO()
    with zipfile.ZipFile(jar_bytes, "w") as jar:
        jar.writestr("dev/example/demo/DemoQuickView.class", b"\xca\xfe\xba\xbe")
    archive = target / name
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("plugin.json", json.dumps(manifest, indent=2))
        bundle.writestr("plugin-demo.jar", jar_bytes.getvalue())
        bundle.writestr("lib/some-dependency.jar", b"")
    return archive


def packaged(manifest: dict) -> dict:
    """The manifest as Maven resource filtering would leave it."""
    resolved = copy.deepcopy(manifest)
    props = {"project.version": "1.0.0", "platform.sdk.version": "4.0.0"}
    resolved["version"] = validate_plugin.expand_maven(resolved["version"], props)
    resolved["platformSdkVersion"] = validate_plugin.expand_maven(resolved["platformSdkVersion"], props)
    for plugin in resolved["plugins"]:
        for key, value in list(plugin.items()):
            plugin[key] = validate_plugin.expand_maven(value, props)
    return resolved


def run(*argv: str) -> tuple[int, str]:
    out = io.StringIO()
    old = sys.argv
    sys.argv = ["validate_plugin.py", *argv]
    try:
        with contextlib.redirect_stdout(out):
            code = validate_plugin.main()
    finally:
        sys.argv = old
    return code, out.getvalue()


class ValidatorTest(unittest.TestCase):

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.project = write_project(self.tmp, SOURCE_MANIFEST)

    def test_valid_project_and_bundle_pass(self) -> None:
        archive = write_bundle(self.project, packaged(SOURCE_MANIFEST))
        code, output = run(str(self.project), "--archive", str(archive))
        self.assertEqual(0, code, output)
        self.assertNotIn("ERROR", output)

    def test_unresolved_placeholder_in_nested_bundle_field_is_an_error(self) -> None:
        manifest = packaged(SOURCE_MANIFEST)
        manifest["plugins"][0]["version"] = "${unresolved}"
        archive = write_bundle(self.project, manifest)
        code, output = run(str(self.project), "--archive", str(archive))
        self.assertEqual(1, code, output)
        self.assertIn("plugins[0].version has unresolved Maven placeholders: ${unresolved}", output)

    def test_unresolved_top_level_placeholder_in_bundle_is_an_error(self) -> None:
        manifest = packaged(SOURCE_MANIFEST)
        manifest["version"] = "${project.version}"
        archive = write_bundle(self.project, manifest)
        code, output = run(str(self.project), "--archive", str(archive))
        self.assertEqual(1, code, output)
        self.assertIn("version has unresolved Maven placeholders", output)

    def test_source_placeholders_resolve_from_the_pom(self) -> None:
        code, output = run(str(self.project))
        self.assertEqual(0, code, output)
        self.assertNotIn("unresolved Maven placeholders", output)

    def test_unknown_source_placeholder_is_a_warning_not_an_error(self) -> None:
        manifest = copy.deepcopy(SOURCE_MANIFEST)
        manifest["plugins"][0]["name"] = "${not.declared.anywhere}"
        project = write_project(self.tmp / "other", manifest)
        code, output = run(str(project))
        self.assertEqual(0, code, output)
        self.assertIn("WARNING", output)
        self.assertIn("${not.declared.anywhere}", output)

    def test_relative_archive_resolves_against_the_current_directory(self) -> None:
        archive = write_bundle(self.project, packaged(SOURCE_MANIFEST))
        cwd = Path.cwd()
        os.chdir(self.project)
        try:
            code, output = run(str(self.project), "--archive", "target/" + archive.name)
        finally:
            os.chdir(cwd)
        self.assertEqual(0, code, output)

    def test_relative_archive_falls_back_to_the_project_directory(self) -> None:
        archive = write_bundle(self.project, packaged(SOURCE_MANIFEST))
        cwd = Path.cwd()
        os.chdir(self.tmp)
        try:
            code, output = run(str(self.project), "--archive", "target/" + archive.name)
        finally:
            os.chdir(cwd)
        self.assertEqual(0, code, output)

    def test_declared_class_missing_from_the_jar_is_an_error(self) -> None:
        manifest = packaged(SOURCE_MANIFEST)
        manifest["plugins"][0]["class"] = "dev.example.demo.Missing"
        archive = write_bundle(self.project, manifest)
        code, output = run(str(self.project), "--archive", str(archive))
        self.assertEqual(1, code, output)
        self.assertIn("declared class is not in the plugin JAR", output)


if __name__ == "__main__":
    unittest.main()
