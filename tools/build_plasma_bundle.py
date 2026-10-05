#!/usr/bin/env python3
"""Publish a closed ForgeDesktop KWin/Plasma candidate directory.

The source commit and file hashes bind audited ForgeDesktop bytes. ForgeOS must
pin the receipt digest independently and verify its own signed Arch closure.
"""

import argparse
import ast
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
ARCH_PROFILE = "arch-2026-08-01"
UBUNTU_PROFILE = "ubuntu-26.04"
UBUNTU_HELPER = "usr/libexec/forge-desktop/ubuntu-desktop"
SESSION_SCRIPT = "usr/libexec/forge-desktop/forge-kwin-session"
SESSION_ENTRY = "usr/share/wayland-sessions/forgedesktop-kwin.desktop"
DEPENDENCIES = "usr/share/forge-desktop/plasma/dependencies.json"
LICENSE = "usr/share/licenses/forge-desktop/LICENSE"
REQUIRED = {SESSION_SCRIPT, SESSION_ENTRY, DEPENDENCIES, LICENSE}
COMPAT_SCRIPT = "usr/libexec/forge-desktop/compatforge-desktop-sync"
COMPAT_SERVICE = "usr/lib/systemd/user/forge-compatforge-desktop-sync.service"
COMPAT_TIMER = "usr/lib/systemd/user/forge-compatforge-desktop-sync.timer"
COMPAT_REQUIRED = {COMPAT_SCRIPT, COMPAT_SERVICE, COMPAT_TIMER}
COMPAT_SERVICE_BYTES = (b"[Unit]\nDescription=Synchronize CompatForge application launchers\n"
                       b"After=compatforge.service\nRequisite=compatforge.service\nPartOf=graphical-session.target\nConditionPathExists=/usr/bin/compatforge-cli\n\n"
                       b"[Service]\nType=oneshot\nExecStart=/usr/libexec/forge-desktop/compatforge-desktop-sync\n"
                       b"TimeoutStartSec=90\nNoNewPrivileges=true\n")
COMPAT_TIMER_BYTES = (b"[Unit]\nDescription=Keep CompatForge launchers synchronized with installed applications\n"
                     b"PartOf=graphical-session.target\nAfter=graphical-session.target\n\n"
                     b"[Timer]\nOnStartupSec=10\nOnUnitInactiveSec=15\nAccuracySec=1\n"
                     b"Unit=forge-compatforge-desktop-sync.service\n\n[Install]\nWantedBy=graphical-session.target\n")
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
UBUNTU_LAYOUT_SOURCE = "plasma/look-and-feel-ubuntu/contents/layouts/org.kde.plasma.desktop-layout.js"
SCRIPT_BYTES = (b"#!/bin/sh\nset -eu\n"
                b'[ "$(/usr/bin/id -u)" -ne 0 ] || exit 1\n'
                b"export QT_QUICK_BACKEND=software\n"
                b"export XMODIFIERS=@im=fcitx\n"
                b"exec /usr/lib/plasma-dbus-run-session-if-needed "
                b"/usr/bin/startplasma-wayland\n")
UBUNTU_SCRIPT_BYTES = (b"#!/bin/sh\nset -eu\n"
                       b'[ "$(/usr/bin/id -u)" -ne 0 ] || exit 1\n'
                       b"exec /usr/bin/python3 /usr/libexec/forge-desktop/ubuntu-desktop session\n")
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
    return (name in REQUIRED or name == UBUNTU_HELPER
            or name in COMPAT_REQUIRED
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


def validate_dependencies(data, profile=ARCH_PROFILE):
    require(profile in (ARCH_PROFILE, UBUNTU_PROFILE), "unknown runtime profile")
    require(len(data) <= 16 * 1024, "dependency inventory exceeds limit")
    try:
        value = json.loads(data, object_pairs_hook=unique_pairs)
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ValueError("invalid dependency inventory") from error
    identity = ({"schemaVersion": 1, "archSnapshot": ARCH_SNAPSHOT}
                if profile == ARCH_PROFILE else
                {"schemaVersion": 2, "runtimeProfile": UBUNTU_PROFILE})
    require(type(value) is dict and set(value) == set(identity) | {
        "runtimePackages", "assetLicenses"}
            and type(value["schemaVersion"]) is int
            and all(value[key] == expected for key, expected in identity.items()),
            "dependency inventory has wrong schema or runtime profile")
    packages = value["runtimePackages"]
    licenses = value["assetLicenses"]
    require(type(packages) is list and 1 <= len(packages) <= 64
            and all(type(name) is str and re.fullmatch(r"[a-z0-9][a-z0-9+_.-]{0,79}", name)
                    for name in packages)
            and packages == sorted(set(packages))
            and ({"fcitx5", "fcitx5-chinese-addons", "fcitx5-gtk", "fcitx5-qt"}
                 if profile == ARCH_PROFILE else
                 {"fcitx5", "fcitx5-chinese-addons", "fcitx5-frontend-gtk3",
                  "fcitx5-frontend-qt6", "kwin-wayland", "plasma-workspace",
                  "python3", "libkf6service-bin"})
            <= set(packages),
            "runtime package names must be bounded, sorted and unique")
    require(type(licenses) is dict and len(licenses) <= MAX_FILES
            and all(eligible_path(name) and name not in REQUIRED
                    and type(license_name) is str
                    and 1 <= len(license_name) <= 80
                    for name, license_name in licenses.items()),
            "asset license records are invalid")
    return value


def validate_compatforge_assets(payloads, dependencies, profile=ARCH_PROFILE):
    present = set(payloads) & COMPAT_REQUIRED
    if not present:
        return
    require(present == COMPAT_REQUIRED, "incomplete CompatForge desktop integration")
    require(payloads[COMPAT_SERVICE][0] == COMPAT_SERVICE_BYTES
            and payloads[COMPAT_TIMER][0] == COMPAT_TIMER_BYTES,
            "CompatForge unit changes fixed command or scheduling contract")
    require({"python" if profile == ARCH_PROFILE else "python3", "desktop-file-utils"}
            <= set(dependencies["runtimePackages"]),
            "CompatForge desktop integration dependencies are missing")
    source = payloads[COMPAT_SCRIPT][0]
    require(len(source) <= 64 * 1024 and source.startswith(b"#!/usr/bin/env python3\n"),
            "invalid CompatForge desktop consumer")
    try:
        ast.parse(source)
    except (SyntaxError, UnicodeError) as error:
        raise ValueError("invalid CompatForge desktop consumer syntax") from error


def validate_visual_assets(payloads, profile=ARCH_PROFILE):
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
    require("[kwinrc][Wayland]\n"
            "InputMethod[$e]=/usr/share/applications/org.fcitx.Fcitx5.desktop\n"
            in defaults, "Forge virtual keyboard default differs")
    layout = payloads[LOOK_LAYOUT][0].decode("utf-8", errors="strict")
    require(len(layout) <= 16 * 1024
            and "org.kde.plasma.icontasks" in layout
            and "org.kde.plasma.systemtray" in layout
            and "file:///" + LOOK_WALLPAPER in layout
            and not re.search(r"WindowHeap|runCommand|openUrlExternally|\beval\s*\(|\bimport\b", layout),
            "Forge visual theme uses unsupported or private scripting")
    if profile == UBUNTU_PROFILE:
        require(re.findall(r'"([A-Za-z0-9_.-]+\.desktop)"', layout) == [
                    "org.kde.dolphin.desktop", "org.kde.konsole.desktop",
                    "forge-store.desktop", "systemsettings.desktop"]
                and "applicationExists(ubuntuFavorites[j])" in layout,
                "Ubuntu first-login favorites differ or miss installed-entry filtering")
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


def collect_files(root, *, receipt=False, profile=ARCH_PROFILE):
    require(profile in (ARCH_PROFILE, UBUNTU_PROFILE), "unknown runtime profile")
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
            mode = 0o755 if relative in (SESSION_SCRIPT, COMPAT_SCRIPT, UBUNTU_HELPER) else 0o644
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
                require(data == (SCRIPT_BYTES if profile == ARCH_PROFILE else UBUNTU_SCRIPT_BYTES),
                        "unreviewed session script body")
            elif relative == SESSION_ENTRY:
                require(len(data) <= 16 * 1024, "session entry exceeds limit")
                validate_session_entry(data)
            elif relative == DEPENDENCIES:
                validate_dependencies(data, profile)
            elif relative == LICENSE:
                require(bool(data.strip()), "project license notice is empty")
            result[relative] = (data, mode)
    require(REQUIRED <= set(result), "required Plasma session file missing")
    dependencies = validate_dependencies(result[DEPENDENCIES][0], profile)
    if profile == UBUNTU_PROFILE:
        require(UBUNTU_HELPER in result, "Ubuntu desktop helper missing")
        source = result[UBUNTU_HELPER][0]
        require(len(source) <= 64 * 1024 and source.startswith(b"#!/usr/bin/env python3\n"),
                "invalid Ubuntu desktop helper")
        try:
            ast.parse(source)
        except (SyntaxError, UnicodeError) as error:
            raise ValueError("invalid Ubuntu desktop helper syntax") from error
    else:
        require(UBUNTU_HELPER not in result, "Ubuntu helper in Arch bundle")
    assets = set(result) - REQUIRED
    require(set(dependencies["assetLicenses"]) == assets,
            "asset license records differ from bundled assets")
    validate_visual_assets(result, profile)
    validate_window_assets(result)
    validate_compatforge_assets(result, dependencies, profile)
    return result


def receipt_bytes(payloads, version, source, profile=ARCH_PROFILE):
    entries = {name: {"sha256": hashlib.sha256(data).hexdigest(),
                      "size": len(data), "mode": mode}
               for name, (data, mode) in sorted(payloads.items())}
    require(profile in (ARCH_PROFILE, UBUNTU_PROFILE), "unknown runtime profile")
    value = {"schemaVersion": 1, "kind": "plasma-session",
             "target": "x86_64-linux-gnu", "version": version,
             "sourceCommit": source, "archSnapshot": ARCH_SNAPSHOT,
             "files": entries}
    if profile == UBUNTU_PROFILE:
        value.pop("archSnapshot")
        value.update(schemaVersion=2, runtimeProfile=UBUNTU_PROFILE)
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def create_bundle(staging, output, version, source, *, profile=ARCH_PROFILE):
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
    payloads = collect_files(staging, profile=profile)
    raw = receipt_bytes(payloads, version, source, profile)
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
    require(type(value) is dict, "invalid Plasma bundle receipt")
    profile = UBUNTU_PROFILE if value.get("schemaVersion") == 2 else ARCH_PROFILE
    identity = ({"schemaVersion": 1, "archSnapshot": ARCH_SNAPSHOT}
                if profile == ARCH_PROFILE else
                {"schemaVersion": 2, "runtimeProfile": UBUNTU_PROFILE})
    require(set(value) == set(identity) | {
        "schemaVersion", "kind", "target", "version", "sourceCommit",
        "files"}, "invalid Plasma bundle receipt fields")
    require(type(value["schemaVersion"]) is int
            and all(value[key] == expected for key, expected in identity.items())
            and value["kind"] == "plasma-session"
            and value["target"] == "x86_64-linux-gnu"
            and type(value["version"]) is str
            and re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+(?:-[A-Za-z0-9.-]+)?", value["version"])
            and type(value["sourceCommit"]) is str
            and re.fullmatch(r"[0-9a-f]{40}", value["sourceCommit"])
            and type(value["files"]) is dict,
            "invalid Plasma bundle receipt identity")
    payloads = collect_files(bundle, receipt=True, profile=profile)
    require(set(payloads) == set(value["files"]),
            "Plasma bundle file set differs from receipt")
    require(raw == receipt_bytes(payloads, value["version"], value["sourceCommit"], profile),
            "Plasma bundle file metadata or canonical receipt differs")
    return value


def repository_asset_sources(repo, *, profile=ARCH_PROFILE):
    """Closed source mapping; profile choice never edits the Arch source tree."""
    require(profile in (ARCH_PROFILE, UBUNTU_PROFILE), "unknown runtime profile")
    repo = Path(repo).absolute()
    sources = {
        SESSION_SCRIPT: "plasma/session/forge-kwin-session" + ("-ubuntu" if profile == UBUNTU_PROFILE else ""),
        SESSION_ENTRY: "plasma/session/forgedesktop-kwin.desktop",
        DEPENDENCIES: "plasma/dependencies" + ("-ubuntu" if profile == UBUNTU_PROFILE else "") + ".json",
        LICENSE: "LICENSE-MIT",
        COMPAT_SCRIPT: "tools/compatforge_desktop.py",
        COMPAT_SERVICE: "services/compatforge/forge-compatforge-desktop-sync.service",
        COMPAT_TIMER: "services/compatforge/forge-compatforge-desktop-sync.timer",
    }
    sources.update({name: "plasma/look-and-feel/" + name[len(LOOK_ROOT):]
                    for name in LOOK_REQUIRED})
    sources.update({name: "plasma/aurorae/ForgeDark/" + name[len(WINDOW_DECOR_ROOT):]
                    for name in WINDOW_DECOR_REQUIRED})
    sources.update({name: "plasma/plasmoids/org.forge.windowcontrols/" + name[len(WINDOW_WIDGET_ROOT):]
                    for name in (WINDOW_WIDGET_METADATA, WINDOW_WIDGET_QML, WINDOW_CATALOG)})
    if profile == UBUNTU_PROFILE:
        sources[UBUNTU_HELPER] = "tools/ubuntu_desktop.py"
        sources[LOOK_LAYOUT] = UBUNTU_LAYOUT_SOURCE
    return {name: repo / relative for name, relative in sources.items()}


def stage_repository_assets(repo, staging, *, profile=ARCH_PROFILE):
    """Stage audited repository assets into a new directory with exact modes."""
    staging = Path(staging).absolute()
    no_links(staging.parent)
    require(staging.parent.is_dir() and not os.path.lexists(staging),
            "repository staging requires a new directory")
    sources = repository_asset_sources(repo, profile=profile)
    payloads = {}
    for name, source in sources.items():
        no_links(source)
        metadata = source.stat()
        require(stat.S_ISREG(metadata.st_mode) and metadata.st_nlink == 1
                and metadata.st_size <= MAX_FILE, "repository asset must be bounded and regular")
        data = source.read_bytes()
        require(len(data) == metadata.st_size, "repository asset changed while reading")
        payloads[name] = data if name.endswith(".mo") else data.replace(b"\r\n", b"\n")
    staging.mkdir(mode=0o700)
    for name, data in payloads.items():
        target = staging / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(data)
        target.chmod(0o755 if name in (SESSION_SCRIPT, COMPAT_SCRIPT, UBUNTU_HELPER) else 0o644)
    collect_files(staging, profile=profile)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--staging", type=Path)
    inputs.add_argument("--repository-assets", action="store_true")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--version", required=True)
    parser.add_argument("--profile", choices=(ARCH_PROFILE, UBUNTU_PROFILE), default=ARCH_PROFILE)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    source = source_commit(args.repo)
    if args.repository_assets:
        with tempfile.TemporaryDirectory(prefix="forge-plasma-repository-") as temporary:
            staging = Path(temporary) / "stage"
            stage_repository_assets(args.repo, staging, profile=args.profile)
            pin = create_bundle(staging, args.output, args.version, source, profile=args.profile)
    else:
        pin = create_bundle(args.staging, args.output, args.version, source, profile=args.profile)
    print(pin)


if __name__ == "__main__":
    main()
