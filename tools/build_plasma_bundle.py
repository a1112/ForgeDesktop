#!/usr/bin/env python3
"""Publish a closed ForgeDesktop KWin/Plasma candidate directory.

The source commit and file hashes bind audited ForgeDesktop bytes. ForgeOS must
pin the receipt digest independently and verify its own signed Arch closure.
"""

import argparse
import configparser
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import tempfile

from tools.build_bundle import no_links, require, source_commit


ARCH_SNAPSHOT = "2026/08/01"
SESSION_SCRIPT = "usr/libexec/forge-desktop/forge-kwin-session"
SESSION_ENTRY = "usr/share/wayland-sessions/forgedesktop-kwin.desktop"
DEPENDENCIES = "usr/share/forge-desktop/plasma/dependencies.json"
LICENSE = "usr/share/licenses/forge-desktop/LICENSE"
REQUIRED = {SESSION_SCRIPT, SESSION_ENTRY, DEPENDENCIES, LICENSE}
SCRIPT_BYTES = (b"#!/bin/sh\nset -eu\n"
                b'[ "$(/usr/bin/id -u)" -ne 0 ] || exit 1\n'
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
