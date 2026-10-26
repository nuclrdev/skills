#!/usr/bin/env python3
"""Validate a Nuclr Commander plugin project and, optionally, its bundle ZIP."""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


VALID_TYPES = {"FilePanel", "QuickView", "Fullscreen"}
VALID_DEVELOPERS = {"Official", "Community"}
VALID_ROLES = {"Viewer", "Editor"}
TYPE_INTERFACES = {
    "FilePanel": "FilePanelNuclrPlugin",
    "QuickView": "QuickViewNuclrPlugin",
    "Fullscreen": "FullscreenNuclrPlugin",
}
REQUIRED_PLUGIN_FIELDS = ("class", "type", "id", "name", "author", "license", "developer")
MIN_JAVA_RELEASE = 25
PLACEHOLDER = re.compile(r"\$\{([^}]+)\}")


class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def error(self, message: str) -> None:
        self.errors.append(message)

    def warn(self, message: str) -> None:
        self.warnings.append(message)


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def child_text(element: ET.Element, name: str) -> str | None:
    for child in element:
        if local_name(child.tag) == name and child.text and child.text.strip():
            return child.text.strip()
    return None


def children(element: ET.Element, name: str) -> list[ET.Element]:
    return [child for child in element if local_name(child.tag) == name]


def parse_pom(project: Path, report: Report) -> tuple[ET.Element | None, dict[str, str]]:
    pom = project / "pom.xml"
    if not pom.is_file():
        report.error("pom.xml is missing")
        return None, {}
    try:
        root = ET.parse(pom).getroot()
    except ET.ParseError as exc:
        report.error(f"pom.xml is invalid XML: {exc}")
        return None, {}

    props: dict[str, str] = {}
    version = child_text(root, "version")
    if not version:
        # A module may inherit its version from a parent POM rather than declaring one.
        for parent in children(root, "parent"):
            version = child_text(parent, "version")
            if version:
                break
    if version:
        props["project.version"] = version
    for name in ("artifactId", "groupId", "name", "description"):
        value = child_text(root, name)
        if value is None:
            # groupId in particular is routinely inherited from the parent POM.
            for parent in children(root, "parent"):
                value = child_text(parent, name)
                if value:
                    break
        if value:
            props[f"project.{name}"] = value
    for prop_parent in children(root, "properties"):
        for prop in prop_parent:
            if prop.text and prop.text.strip():
                props[local_name(prop.tag)] = prop.text.strip()

    sdk_dependencies = []
    for deps in children(root, "dependencies"):
        for dep in children(deps, "dependency"):
            if child_text(dep, "groupId") == "dev.nuclr" and child_text(dep, "artifactId") == "platform-sdk":
                sdk_dependencies.append(dep)
    if not sdk_dependencies:
        report.error("pom.xml has no dev.nuclr:platform-sdk dependency")
    for dep in sdk_dependencies:
        if child_text(dep, "scope") != "provided":
            report.error("dev.nuclr:platform-sdk must use provided scope")

    release = props.get("maven.compiler.release") or props.get("maven.compiler.source")
    if release is None:
        report.warn("no maven.compiler.release/source is declared; SDK 4.x requires Java 25 or newer")
    else:
        try:
            if int(release) < MIN_JAVA_RELEASE:
                report.warn(
                    f"Java compiler release/source is {release}; SDK 4.x requires "
                    f"{MIN_JAVA_RELEASE} or newer. Ignore this when targeting an older SDK."
                )
        except ValueError:
            report.warn(f"could not resolve Java compiler level: {release!r}")
    return root, props


def expand_maven(value: object, props: dict[str, str]) -> object:
    if not isinstance(value, str):
        return value

    def replace(match: re.Match[str]) -> str:
        return props.get(match.group(1), match.group(0))

    return PLACEHOLDER.sub(replace, value)


def walk_strings(value: object, path: str = "") -> "list[tuple[str, str]]":
    """Every string in a JSON value, paired with its dotted path."""
    found: list[tuple[str, str]] = []
    if isinstance(value, dict):
        for key, item in value.items():
            found += walk_strings(item, f"{path}.{key}" if path else str(key))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found += walk_strings(item, f"{path}[{index}]")
    elif isinstance(value, str):
        found.append((path or "<root>", value))
    return found


def check_placeholders(manifest: dict, source: str, props: dict[str, str], packaged: bool,
                       report: Report) -> None:
    """Flag Maven placeholders anywhere in the manifest, not just in the top-level fields.

    A packaged manifest has already been through resource filtering, so any placeholder
    left in it is an error. In the source manifest only the POM's own properties can be
    resolved here, so an unknown placeholder is reported as a warning: Maven may still
    supply it from a profile, the settings, or the command line.
    """
    for path, value in walk_strings(manifest):
        candidate = value if packaged else expand_maven(value, props)
        remaining = sorted({match.group(0) for match in PLACEHOLDER.finditer(str(candidate))})
        if not remaining:
            continue
        detail = f"{source}: {path} has unresolved Maven placeholders: {', '.join(remaining)}"
        if packaged:
            report.error(detail)
        else:
            report.warn(f"{detail}; verify that the build supplies them")


def load_manifest(data: bytes, source: str, report: Report) -> dict | None:
    try:
        value = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        report.error(f"{source} is not valid UTF-8 JSON: {exc}")
        return None
    if not isinstance(value, dict):
        report.error(f"{source} must contain a JSON object")
        return None
    return value


def declared_classes(manifest: dict) -> list[str]:
    plugins = manifest.get("plugins")
    if not isinstance(plugins, list):
        return []
    return [p["class"] for p in plugins
            if isinstance(p, dict) and isinstance(p.get("class"), str) and p["class"].strip()]


def jar_class_entries(bundle: zipfile.ZipFile, jar_name: str, report: Report) -> set[str] | None:
    """Return the class names inside a JAR stored in the bundle, or None if unreadable."""
    try:
        with zipfile.ZipFile(io.BytesIO(bundle.read(jar_name))) as jar:
            return {
                name[: -len(".class")].replace("/", ".")
                for name in jar.namelist()
                if name.endswith(".class")
            }
    except (zipfile.BadZipFile, KeyError) as exc:
        report.warn(f"could not read {jar_name} to verify declared classes: {exc}")
        return None


def validate_manifest(manifest: dict, source: str, props: dict[str, str], project: Path | None,
                      report: Report, packaged: bool = False) -> None:
    if manifest.get("schemaVersion") != 1:
        report.error(f"{source}: schemaVersion must be 1")
    for field in ("version", "platformSdkVersion"):
        value = manifest.get(field) if packaged else expand_maven(manifest.get(field), props)
        if not isinstance(value, str) or not value.strip():
            report.error(f"{source}: {field} is missing or blank")
    check_placeholders(manifest, source, props, packaged, report)

    plugins = manifest.get("plugins")
    if not isinstance(plugins, list) or not plugins:
        report.error(f"{source}: plugins must be a non-empty array")
        return
    ids: set[str] = set()
    classes: set[str] = set()
    for index, plugin in enumerate(plugins):
        where = f"{source}: plugins[{index}]"
        if not isinstance(plugin, dict):
            report.error(f"{where} must be an object")
            continue
        for field in REQUIRED_PLUGIN_FIELDS:
            if not isinstance(plugin.get(field), str) or not plugin[field].strip():
                report.error(f"{where}.{field} is required and must be nonblank")
        plugin_type = plugin.get("type")
        if plugin_type not in VALID_TYPES:
            report.error(f"{where}.type must be one of {sorted(VALID_TYPES)}")
        if plugin.get("developer") not in VALID_DEVELOPERS:
            report.error(f"{where}.developer must be Official or Community")
        if "singleton" not in plugin or not isinstance(plugin.get("singleton"), bool):
            report.warn(f"{where}.singleton should be declared explicitly as a boolean")
        if plugin_type == "QuickView":
            if "priority" not in plugin or isinstance(plugin.get("priority"), bool) or not isinstance(plugin.get("priority"), int):
                report.error(f"{where}.priority must be an integer for QuickView")
        elif "priority" in plugin:
            report.warn(f"{where}.priority is ignored for {plugin_type}")
        if "connections" in plugin:
            if not isinstance(plugin.get("connections"), bool):
                report.error(f"{where}.connections must be a boolean")
            elif plugin_type != "FilePanel":
                report.warn(f"{where}.connections is ignored for {plugin_type}")
        if plugin_type == "Fullscreen":
            if plugin.get("role") not in VALID_ROLES:
                report.error(f"{where}.role must be Viewer or Editor for Fullscreen")
        elif "role" in plugin:
            report.warn(f"{where}.role is ignored for {plugin_type}")

        plugin_id = plugin.get("id")
        class_name = plugin.get("class")
        if isinstance(plugin_id, str):
            if plugin_id in ids:
                report.error(f"{where}: duplicate plugin id {plugin_id}")
            ids.add(plugin_id)
        if isinstance(class_name, str):
            if class_name in classes:
                report.error(f"{where}: duplicate plugin class {class_name}")
            classes.add(class_name)
            if project is not None:
                java = project / "src" / "main" / "java" / Path(*class_name.split(".")).with_suffix(".java")
                if not java.is_file():
                    report.error(f"{where}: declared class source is missing: {java.relative_to(project)}")
                elif plugin_type in TYPE_INTERFACES:
                    source_text = java.read_text(encoding="utf-8", errors="replace")
                    expected = TYPE_INTERFACES[plugin_type]
                    if expected not in source_text:
                        report.warn(
                            f"{where}: source does not directly reference {expected}; "
                            "verify that it inherits the interface from a superclass"
                        )


def validate_source(project: Path, props: dict[str, str], report: Report) -> dict | None:
    path = project / "src" / "main" / "resources" / "plugin.json"
    if not path.is_file():
        report.error("src/main/resources/plugin.json is missing")
        return None
    manifest = load_manifest(path.read_bytes(), str(path.relative_to(project)), report)
    if manifest is not None:
        validate_manifest(manifest, str(path.relative_to(project)), props, project, report)
    descriptor = project / "src" / "assembly" / "plugin.xml"
    if not descriptor.is_file():
        report.warn("src/assembly/plugin.xml is missing; verify that another build path creates the flat ZIP")
    else:
        text = descriptor.read_text(encoding="utf-8", errors="replace")
        if not re.search(r"<includeBaseDirectory>\s*false\s*</includeBaseDirectory>", text):
            report.error("assembly descriptor must set includeBaseDirectory to false")
    return manifest


def validate_archive(path: Path, props: dict[str, str], report: Report) -> None:
    if not path.is_file():
        report.error(f"archive does not exist: {path}")
        return
    try:
        with zipfile.ZipFile(path) as bundle:
            names = [name.replace("\\", "/") for name in bundle.namelist() if not name.endswith("/")]
            if "plugin.json" not in names:
                report.error(f"{path.name}: plugin.json is not at the ZIP root")
                return
            root_jars = [name for name in names if "/" not in name and name.endswith(".jar")]
            if not root_jars:
                report.error(f"{path.name}: no plugin JAR is present at the ZIP root")
            sdk_jars = [name for name in names if re.search(r"(^|/)platform-sdk[^/]*\.jar$", name)]
            if sdk_jars:
                report.error(f"{path.name}: platform-sdk must not be bundled: {sdk_jars}")
            lib_jars = [name for name in names if name.startswith("lib/") and name.endswith(".jar")]
            for root_jar in root_jars:
                if f"lib/{root_jar}" in lib_jars:
                    report.warn(f"{path.name}: the plugin JAR is also copied into lib/: {root_jar}")

            manifest = load_manifest(bundle.read("plugin.json"), f"{path.name}!/plugin.json", report)
            if manifest is not None:
                validate_manifest(manifest, f"{path.name}!/plugin.json", props, None, report,
                                  packaged=True)

                declared = declared_classes(manifest)
                if declared and root_jars:
                    packaged: set[str] = set()
                    unreadable = False
                    for root_jar in root_jars:
                        entries = jar_class_entries(bundle, root_jar, report)
                        if entries is None:
                            unreadable = True
                        else:
                            packaged |= entries
                    if not unreadable:
                        for class_name in declared:
                            if class_name not in packaged:
                                report.error(
                                    f"{path.name}: declared class is not in the plugin JAR: {class_name}"
                                )

                pom_version = props.get("project.version")
                bundle_version = manifest.get("version")
                if pom_version and isinstance(bundle_version, str) and bundle_version != pom_version:
                    report.warn(
                        f"{path.name}: bundle version {bundle_version!r} does not match the "
                        f"project version {pom_version!r}"
                    )
    except zipfile.BadZipFile as exc:
        report.error(f"{path} is not a valid ZIP: {exc}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path, help="plugin project directory")
    parser.add_argument("--archive", type=Path, help="packaged plugin ZIP to inspect")
    args = parser.parse_args()
    project = args.project.resolve()
    report = Report()
    _, props = parse_pom(project, report)
    validate_source(project, props, report)
    if args.archive:
        # A relative path is what the caller typed, so honour the current directory
        # first and fall back to the project directory only when nothing is there.
        archive = args.archive
        if not archive.is_absolute() and not archive.exists():
            archive = project / archive
        validate_archive(archive.resolve(), props, report)

    for warning in report.warnings:
        print(f"WARNING: {warning}")
    for error in report.errors:
        print(f"ERROR: {error}")
    if report.errors:
        print(f"FAILED: {len(report.errors)} error(s), {len(report.warnings)} warning(s)")
        return 1
    print(f"OK: Nuclr plugin checks passed with {len(report.warnings)} warning(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
