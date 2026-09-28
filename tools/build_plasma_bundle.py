#!/usr/bin/env python3
"""Publish a closed ForgeDesktop KWin/Plasma candidate directory.

The source commit and file hashes bind audited ForgeDesktop bytes. ForgeOS must
pin the receipt digest independently and verify its own signed Arch closure.
"""

import argparse
import configparser
import gettext
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import stat
import struct
import tempfile
import xml.etree.ElementTree as ET

if __package__:
    from tools.build_bundle import no_links, require, source_commit
else:
    from build_bundle import no_links, require, source_commit


ARCH_SNAPSHOT = "2026/08/01"
SESSION_SCRIPT = "usr/libexec/forge-desktop/forge-kwin-session"
SESSION_ENTRY = "usr/share/wayland-sessions/forgedesktop-kwin.desktop"
DEPENDENCIES = "usr/share/forge-desktop/plasma/dependencies.json"
LICENSE = "usr/share/licenses/forge-desktop/LICENSE"
REQUIRED = {SESSION_SCRIPT, SESSION_ENTRY, DEPENDENCIES, LICENSE}
LOOK_ROOT = "usr/share/plasma/look-and-feel/org.forge.desktop/"
LOOK_METADATA = LOOK_ROOT + "metadata.json"
LOOK_DEFAULTS = LOOK_ROOT + "contents/defaults"
LOOK_LAYOUT = LOOK_ROOT + "contents/layouts/org.kde.plasma.desktop-layout.js"
LOOK_WALLPAPER = LOOK_ROOT + "contents/wallpapers/forge.svg"
LOOK_REQUIRED = {LOOK_METADATA, LOOK_DEFAULTS, LOOK_LAYOUT, LOOK_WALLPAPER}
WINDOW_DECOR_ROOT = "usr/share/aurorae/themes/ForgeDark/"
WINDOW_DECOR_REQUIRED = {WINDOW_DECOR_ROOT + name for name in (
    "metadata.desktop", "ForgeDarkrc", "decoration.svg", "minimize.svg",
    "maximize.svg", "restore.svg", "close.svg")}
WINDOW_WIDGET_ROOT = "usr/share/plasma/plasmoids/org.forge.windowcontrols/"
WINDOW_WIDGET_METADATA = WINDOW_WIDGET_ROOT + "metadata.json"
WINDOW_WIDGET_QML = WINDOW_WIDGET_ROOT + "contents/ui/main.qml"
WINDOW_CATALOG = (WINDOW_WIDGET_ROOT + "contents/locale/zh_CN/LC_MESSAGES/"
                  "plasma_applet_org.forge.windowcontrols.mo")
WINDOW_REQUIRED = WINDOW_DECOR_REQUIRED | {WINDOW_WIDGET_METADATA, WINDOW_WIDGET_QML}
SCRIPT_BYTES = (b"#!/bin/sh\nset -eu\n"
                b'[ "$(/usr/bin/id -u)" -ne 0 ] || exit 1\n'
                b"export QT_QUICK_BACKEND=software\n"
                b"exec /usr/lib/plasma-dbus-run-session-if-needed "
                b"/usr/bin/startplasma-wayland\n")
MAX_RECEIPT = 256 * 1024
MAX_FILE = 16 * 1024 * 1024
MAX_TOTAL = 64 * 1024 * 1024
MAX_FILES = 256


def unique_pairs(pairs):
    result = {}
    for name, value in pairs:
        require(name not in result, "duplicate JSON field")
        result[name] = value
    return result


def eligible_path(name):
    if (not isinstance(name, str) or len(name) > 512
            or not re.fullmatch(r"[A-Za-z0-9_./+-]+", name)
            or any(part in ("", ".", "..") for part in name.split("/"))):
        return False
    return (name in REQUIRED
            or name in WINDOW_REQUIRED or name == WINDOW_CATALOG
            or name.startswith("usr/share/plasma/look-and-feel/org.forge.desktop/")
            or name.startswith("usr/share/plasma/desktoptheme/forge/")
            or name.startswith("usr/share/kwin/scripts/org.forge.desktop/"))


def validate_session_entry(data):
    try:
        parser = configparser.ConfigParser(interpolation=None, strict=True)
        parser.optionxform = str
        parser.read_string(data.decode("utf-8", errors="strict"))
        require(parser.sections() == ["Desktop Entry"] and not parser.defaults(),
                "unexpected session group or defaults")
        values = dict(parser.items("Desktop Entry"))
        for key in ("Name[zh_CN]", "Comment[zh_CN]"):
            if key in values:
                display = values.pop(key)
                require(0 < len(display) <= 512
                        and all(ord(char) >= 32 for char in display),
                        "invalid localized session display field")
        require(values == {
            "Name": "ForgeDesktop (KWin)",
            "Comment": "ForgeOS KWin and Plasma Wayland candidate",
            "Exec": "/usr/libexec/forge-desktop/forge-kwin-session",
            "TryExec": "/usr/bin/startplasma-wayland",
            "Type": "Application",
            "DesktopNames": "KDE;ForgeDesktop;",
        }, "session entry changes the login command or desktop identity")
    except (UnicodeError, configparser.Error, KeyError) as error:
        raise ValueError("invalid session entry") from error


def validate_dependencies(data):
    require(len(data) <= 16 * 1024, "dependency inventory exceeds limit")
    try:
        value = json.loads(data, object_pairs_hook=unique_pairs)
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ValueError("invalid dependency inventory") from error
    require(type(value) is dict and set(value) == {
        "schemaVersion", "archSnapshot", "runtimePackages", "assetLicenses"}
            and type(value["schemaVersion"]) is int and value["schemaVersion"] == 1
            and value["archSnapshot"] == ARCH_SNAPSHOT,
            "dependency inventory has wrong schema or Arch snapshot")
    packages = value["runtimePackages"]
    licenses = value["assetLicenses"]
    require(type(packages) is list and 1 <= len(packages) <= 64
            and all(type(name) is str and re.fullmatch(r"[a-z0-9][a-z0-9+_.-]{0,79}", name)
                    for name in packages)
            and packages == sorted(set(packages)),
            "runtime package names must be bounded, sorted and unique")
    require(type(licenses) is dict and len(licenses) <= MAX_FILES
            and all(eligible_path(name) and name not in REQUIRED
                    and type(license_name) is str
                    and 1 <= len(license_name) <= 80
                    for name, license_name in licenses.items()),
            "asset license records are invalid")
    return value


def validate_visual_assets(payloads):
    visual = {name for name in payloads if name.startswith(LOOK_ROOT)}
    if not visual:
        return
    require(visual == LOOK_REQUIRED, "Forge visual theme has missing or extra files")
    metadata = json.loads(payloads[LOOK_METADATA][0], object_pairs_hook=unique_pairs)
    require(type(metadata) is dict and set(metadata) == {"KPackageStructure", "KPlugin"}
            and metadata["KPackageStructure"] == "Plasma/LookAndFeel"
            and type(metadata["KPlugin"]) is dict
            and metadata["KPlugin"].get("Id") == "org.forge.desktop"
            and metadata["KPlugin"].get("License") == "MIT",
            "Forge visual theme metadata differs")
    defaults = payloads[LOOK_DEFAULTS][0].decode("utf-8", errors="strict")
    require("ColorScheme=BreezeDark\n" in defaults
            and "name=breeze-dark\n" in defaults
            and len(defaults) <= 4096,
            "Forge visual theme defaults differ")
    layout = payloads[LOOK_LAYOUT][0].decode("utf-8", errors="strict")
    require(len(layout) <= 16 * 1024
            and "org.kde.plasma.icontasks" in layout
            and "org.kde.plasma.systemtray" in layout
            and "file:///" + LOOK_WALLPAPER in layout
            and not re.search(r"WindowHeap|runCommand|openUrlExternally|\beval\s*\(|\bimport\b", layout),
            "Forge visual theme uses unsupported or private scripting")
    wallpaper = payloads[LOOK_WALLPAPER][0]
    require(len(wallpaper) <= 1024 * 1024, "Forge wallpaper exceeds limit")
    try:
        tree = ET.fromstring(wallpaper)
    except ET.ParseError as error:
        raise ValueError("invalid Forge wallpaper SVG") from error
    allowed_tags = {"svg", "defs", "linearGradient", "stop", "rect", "g", "text"}
    require(all(element.tag in {"{http://www.w3.org/2000/svg}" + tag
                                for tag in allowed_tags}
                and not any(key.startswith("on") or "href" in key.lower()
                            for key in element.attrib)
                for element in tree.iter()),
            "Forge wallpaper contains unsupported SVG elements")


def validate_window_assets(payloads):
    present = set(payloads) & WINDOW_REQUIRED
    if not present:
        return
    require(present == WINDOW_REQUIRED, "incomplete Forge window-control assets")
    metadata = payloads[WINDOW_DECOR_ROOT + "metadata.desktop"][0].decode("utf-8")
    require(metadata.startswith("[Desktop Entry]\n")
            and re.search(r"(?m)^X-KDE-PluginInfo-Name=ForgeDark$", metadata)
            and re.search(r"(?m)^X-KDE-PluginInfo-License=MIT$", metadata)
            and len(metadata) <= 4096,
            "invalid Forge decoration metadata")
    config = payloads[WINDOW_DECOR_ROOT + "ForgeDarkrc"][0].decode("utf-8")
    require("RightButtons=IAX\n" in config
            and "TitleHeight=32\n" in config
            and "ButtonWidth=48\n" in config
            and len(config) <= 4096,
            "invalid Forge decoration layout")
    expected_frame = {"decoration-" + part for part in (
        "center", "top", "bottom", "left", "right", "topleft",
        "topright", "bottomleft", "bottomright")}
    for name in ("decoration", "minimize", "maximize", "restore", "close"):
        raw = payloads[WINDOW_DECOR_ROOT + name + ".svg"][0]
        require(len(raw) <= 1024 * 1024 and b"<!DOCTYPE" not in raw
                and b"<!ENTITY" not in raw, "unsafe Forge decoration SVG")
        try:
            svg = ET.fromstring(raw)
        except ET.ParseError as error:
            raise ValueError("invalid Forge decoration SVG") from error
        require(svg.tag == "{http://www.w3.org/2000/svg}svg",
                "invalid Forge decoration root")
        ids = {element.attrib.get("id") for element in svg.iter()}
        require((expected_frame if name == "decoration" else
                 {"active-center", "hover-center", "inactive-center"}) <= ids,
                "Forge decoration SVG misses required states")
        allowed = {"svg", "g", "rect", "path", "line"}
        require(all(element.tag in {"{http://www.w3.org/2000/svg}" + tag
                                    for tag in allowed}
                    and all(not key.lower().startswith("on")
                            and "href" not in key.lower()
                            and not re.search(r"url\s*\(|https?://|file://",
                                              value, re.IGNORECASE)
                            for key, value in element.attrib.items())
                    for element in svg.iter()),
                "Forge decoration SVG contains external or active content")
    widget = json.loads(payloads[WINDOW_WIDGET_METADATA][0],
                        object_pairs_hook=unique_pairs)
    require(type(widget) is dict and widget.get("KPackageStructure") == "Plasma/Applet"
            and widget.get("X-Plasma-API-Minimum-Version") == "6.0"
            and type(widget.get("KPlugin")) is dict
            and widget["KPlugin"].get("Id") == "org.forge.windowcontrols"
            and widget["KPlugin"].get("License") == "MIT",
            "invalid Forge window-control widget metadata")
    qml = payloads[WINDOW_WIDGET_QML][0].decode("utf-8")
    messages = set(re.findall(r'\bi18n\("([^"\n]+)"', qml))
    if messages:
        require(WINDOW_CATALOG in payloads, "Chinese window-control catalogue missing")
        raw = payloads[WINDOW_CATALOG][0]
        require(len(raw) <= 64 * 1024, "window-control catalogue exceeds limit")
        try:
            catalog = gettext.GNUTranslations(io.BytesIO(raw))
        except (OSError, UnicodeError, ValueError, IndexError, struct.error) as error:
            raise ValueError("invalid window-control catalogue") from error
        require(catalog.info().get("language") == "zh_CN", "wrong catalogue language")
        for message in messages:
            translated = catalog.gettext(message)
            require(translated != message and bool(translated.strip())
                    and sorted(re.findall(r"%[1-9][0-9]*", message))
                    == sorted(re.findall(r"%[1-9][0-9]*", translated)),
                    "missing translation or changed placeholder")
    require(len(qml) <= 32 * 1024
            and "TaskManager.TasksModel" in qml
            and "requestToggleMinimized" in qml
            and "requestToggleMaximized" in qml
            and "requestClose" in qml
            and not re.search(r"\b(?:Process|Qt\.openUrlExternally|DBus|eval)\b", qml),
            "Forge window-control widget uses unreviewed controls")


def collect_files(root, *, receipt=False):
    root = Path(root).absolute()
    no_links(root)
    require(root.is_dir(), "bundle tree missing")
    result = {}
    total = 0
    for directory, dirs, files in os.walk(root, followlinks=False):
        for name in dirs + files:
            no_links(Path(directory) / name)
        for name in files:
            path = Path(directory) / name
            relative = path.relative_to(root).as_posix()
            if receipt and relative == "bundle.json":
                continue
            require(eligible_path(relative), "file outside Plasma bundle scope")
            metadata = path.stat()
            require(stat.S_ISREG(metadata.st_mode) and metadata.st_nlink == 1
                    and metadata.st_size <= MAX_FILE,
                    "bundle input is not a bounded singly linked regular file")
            mode = 0o755 if relative == SESSION_SCRIPT else 0o644
            if os.name != "nt":
                require(stat.S_IMODE(metadata.st_mode) == mode,
                        "bundle input mode mismatch")
            data = path.read_bytes()
            require(len(data) == metadata.st_size and len(data) <= MAX_FILE,
                    "bundle input changed while reading")
            total += len(data)
            require(total <= MAX_TOTAL and len(result) < MAX_FILES,
                    "bundle exceeds file-count or byte limit")
            if relative == SESSION_SCRIPT:
                require(data == SCRIPT_BYTES, "unreviewed session script body")
            elif relative == SESSION_ENTRY:
                require(len(data) <= 16 * 1024, "session entry exceeds limit")
                validate_session_entry(data)
            elif relative == DEPENDENCIES:
                validate_dependencies(data)
            elif relative == LICENSE:
                require(bool(data.strip()), "project license notice is empty")
            result[relative] = (data, mode)
    require(REQUIRED <= set(result), "required Plasma session file missing")
    dependencies = validate_dependencies(result[DEPENDENCIES][0])
    assets = set(result) - REQUIRED
    require(set(dependencies["assetLicenses"]) == assets,
            "asset license records differ from bundled assets")
    validate_visual_assets(result)
    validate_window_assets(result)
    return result


def receipt_bytes(payloads, version, source):
    entries = {name: {"sha256": hashlib.sha256(data).hexdigest(),
                      "size": len(data), "mode": mode}
               for name, (data, mode) in sorted(payloads.items())}
    value = {"schemaVersion": 1, "kind": "plasma-session",
             "target": "x86_64-linux-gnu", "version": version,
             "sourceCommit": source, "archSnapshot": ARCH_SNAPSHOT,
             "files": entries}
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def create_bundle(staging, output, version, source):
    require(type(version) is str and len(version) <= 64 and
            re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+(?:-[A-Za-z0-9.-]+)?", version),
            "invalid bundle version")
    require(type(source) is str and re.fullmatch(r"[0-9a-f]{40}", source),
            "invalid source commit")
    staging, output = Path(staging).absolute(), Path(output).absolute()
    require(output != staging and staging not in output.parents,
            "bundle output must be outside staged input")
    no_links(output.parent)
    require(output.parent.is_dir(), "bundle output parent missing")
    if os.path.lexists(output):
        raise FileExistsError(output)
    payloads = collect_files(staging)
    raw = receipt_bytes(payloads, version, source)
    temporary = Path(tempfile.mkdtemp(prefix=".forge-plasma-", dir=output.parent))
    require(temporary.resolve().parent == output.parent.resolve(),
            "temporary output escaped parent")
    try:
        for name, (data, mode) in payloads.items():
            target = temporary / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            target.chmod(mode)
        (temporary / "bundle.json").write_bytes(raw)
        if os.path.lexists(output):
            raise FileExistsError(output)
        temporary.rename(output)
    finally:
        if temporary.exists():
            require(temporary.resolve().parent == output.parent.resolve(),
                    "temporary cleanup escaped parent")
            shutil.rmtree(temporary)
    return hashlib.sha256(raw).hexdigest()


def verify_bundle(bundle, expected_sha256):
    require(type(expected_sha256) is str and
            re.fullmatch(r"[0-9a-f]{64}", expected_sha256),
            "invalid expected receipt digest")
    bundle = Path(bundle).absolute()
    no_links(bundle)
    path = bundle / "bundle.json"
    no_links(path)
    require(path.is_file(), "missing receipt")
    metadata = path.stat()
    require(stat.S_ISREG(metadata.st_mode) and metadata.st_nlink == 1
            and metadata.st_size <= MAX_RECEIPT,
            "receipt is not a bounded singly linked regular file")
    raw = path.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == expected_sha256,
            "Plasma bundle receipt digest mismatch")
    try:
        value = json.loads(raw, object_pairs_hook=unique_pairs)
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ValueError("invalid Plasma bundle receipt") from error
    require(type(value) is dict and set(value) == {
        "schemaVersion", "kind", "target", "version", "sourceCommit",
        "archSnapshot", "files"}, "invalid Plasma bundle receipt fields")
    require(type(value["schemaVersion"]) is int and value["schemaVersion"] == 1
            and value["kind"] == "plasma-session"
            and value["target"] == "x86_64-linux-gnu"
            and value["archSnapshot"] == ARCH_SNAPSHOT
            and type(value["version"]) is str
            and re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+(?:-[A-Za-z0-9.-]+)?", value["version"])
            and type(value["sourceCommit"]) is str
            and re.fullmatch(r"[0-9a-f]{40}", value["sourceCommit"])
            and type(value["files"]) is dict,
            "invalid Plasma bundle receipt identity")
    payloads = collect_files(bundle, receipt=True)
    require(set(payloads) == set(value["files"]),
            "Plasma bundle file set differs from receipt")
    require(raw == receipt_bytes(payloads, value["version"], value["sourceCommit"]),
            "Plasma bundle file metadata or canonical receipt differs")
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staging", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--version", required=True)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    print(create_bundle(args.staging, args.output, args.version,
                        source_commit(args.repo)))


if __name__ == "__main__":
    main()
