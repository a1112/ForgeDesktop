#!/usr/bin/env python3
"""Build the bounded, deterministic ForgeDesktop bundle consumed by ForgeOS.

The staged tree is prepared from audited build outputs. This tool records their
exact bytes; it does not establish completeness of the dependency/license audit.
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
import subprocess
import tempfile


ARCH_SNAPSHOT = "2026/08/01"
ELF_BINARIES = {"usr/bin/forge-compositor", "usr/libexec/forge-desktop/forge-shell",
                "usr/libexec/forge-desktop/forge-notificationd"}
SESSION_SCRIPT = "usr/libexec/forge-desktop/forge-session"
SESSION_ENTRY = "usr/share/wayland-sessions/forgedesktop.desktop"
EXECUTABLES = ELF_BINARIES | {SESSION_SCRIPT}
REQUIRED = EXECUTABLES | {SESSION_ENTRY,
    "usr/share/forge-desktop/dependencies.json",
    "usr/share/licenses/forge-desktop/LICENSE",
}
MAX_FILE = 64 * 1024 * 1024
MAX_TOTAL = 256 * 1024 * 1024


def require(condition, message):
    if not condition:
        raise ValueError(message)


def no_links(path):
    require(not any(part.is_symlink() for part in (path, *path.parents)),
            "bundle path contains symlink")


def unique_pairs(pairs):
    value = {}
    for key, item in pairs:
        require(key not in value, "duplicate dependency field")
        value[key] = item
    return value


def validate_session_entry(data):
    try:
        parser = configparser.ConfigParser(interpolation=None, strict=True)
        parser.optionxform = str
        parser.read_string(data.decode("utf-8", errors="strict"))
        require(parser.sections() == ["Desktop Entry"], "unexpected session group")
        values = parser["Desktop Entry"]
        require({"Name", "Exec", "TryExec", "Type", "DesktopNames"} <= set(values)
                and set(values) <= {"Name", "Comment", "Exec", "TryExec", "Type", "DesktopNames"}
                and 0 < len(values["Name"]) <= 64
                and len(values.get("Comment", "")) <= 256
                and values["Exec"] == "/usr/libexec/forge-desktop/forge-session"
                and values["TryExec"] == "/usr/bin/forge-compositor"
                and values["Type"] == "Application"
                and values["DesktopNames"] == "ForgeDesktop",
                "session entry changes the login command")
    except (UnicodeError, configparser.Error, KeyError) as error:
        raise ValueError("invalid session entry") from error


def eligible_path(name):
    if (len(name) > 512 or not re.fullmatch(r"[A-Za-z0-9_./+-]+", name)
            or any(part in ("", ".", "..") for part in name.split("/"))
            or name == "usr/share/forge-desktop/bundle.json"
            or name.startswith("usr/share/forge-desktop/bundle.json/")):
        return False
    return (name in EXECUTABLES or name == SESSION_ENTRY
            or name.startswith("usr/share/forge-desktop/")
            or name.startswith("usr/share/licenses/forge-desktop/"))


def frozen_files(staging):
    staging = Path(staging).absolute()
    no_links(staging)
    require(staging.is_dir(), "staged bundle tree missing")
    payloads = {}
    total = 0
    for directory, dirs, files in os.walk(staging, followlinks=False):
        for name in dirs + files:
            no_links(Path(directory) / name)
        for name in files:
            path = Path(directory) / name
            relative = path.relative_to(staging).as_posix()
            require(eligible_path(relative), "file outside ForgeDesktop bundle scope")
            metadata = path.stat()
            require(stat.S_ISREG(metadata.st_mode) and metadata.st_nlink == 1
                    and metadata.st_size <= MAX_FILE,
                    "bundle input is not a bounded singly linked regular file")
            mode = 0o755 if relative in EXECUTABLES else 0o644
            if os.name != "nt":
                require(stat.S_IMODE(metadata.st_mode) == mode, "bundle input mode mismatch")
            data = path.read_bytes()
            require(len(data) == metadata.st_size and len(data) <= MAX_FILE,
                    "bundle input changed or grew while reading")
            total += len(data)
            require(total <= MAX_TOTAL and len(payloads) < 4096,
                    "bundle exceeds bounded file count or size")
            if relative in ELF_BINARIES:
                require(len(data) >= 64 and data[:7] == b"\x7fELF\x02\x01\x01"
                        and data[16:18] in (b"\x02\x00", b"\x03\x00")
                        and data[18:20] == b"\x3e\x00",
                        "binary is not x86_64 little-endian ELF")
            elif relative == SESSION_SCRIPT:
                require(len(data) <= 64 * 1024 and data.startswith(b"#!/bin/sh\n")
                        and b"\x00" not in data, "invalid session script")
            elif relative == SESSION_ENTRY:
                require(len(data) <= 16 * 1024, "session entry is too large")
                validate_session_entry(data)
            payloads[relative] = (data, mode)
    require(REQUIRED <= set(payloads), "required binary or inventory missing")
    dependencies = json.loads(payloads["usr/share/forge-desktop/dependencies.json"][0],
                              object_pairs_hook=unique_pairs)
    require(type(dependencies) is dict and dependencies.get("schemaVersion") == 1
            and type(dependencies.get("schemaVersion")) is int
            and dependencies.get("archSnapshot") == ARCH_SNAPSHOT,
            "dependency inventory has wrong schema or Arch snapshot")
    require(payloads["usr/share/licenses/forge-desktop/LICENSE"][0].strip(),
            "project license notice is empty")
    return payloads


def create_bundle(staging, output, version, source_commit):
    """Publish one new bundle directory and return the SHA-256 of bundle.json."""
    require(type(version) is str and len(version) <= 64 and
            re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+(?:-[A-Za-z0-9.-]+)?", version),
            "invalid bundle version")
    require(type(source_commit) is str and re.fullmatch(r"[0-9a-f]{40}", source_commit),
            "invalid source commit")
    staging, output = Path(staging).absolute(), Path(output).absolute()
    require(output != staging and staging not in output.parents,
            "bundle output must be outside staged input")
    no_links(output.parent)
    require(output.parent.is_dir(), "bundle output parent missing")
    if os.path.lexists(output):
        raise FileExistsError(output)
    payloads = frozen_files(staging)
    entries = {name: {"sha256": hashlib.sha256(data).hexdigest(),
                      "size": len(data), "mode": mode}
               for name, (data, mode) in sorted(payloads.items())}
    receipt = {"schemaVersion": 1, "target": "x86_64-linux-gnu",
               "version": version, "sourceCommit": source_commit,
               "archSnapshot": ARCH_SNAPSHOT, "files": entries}
    raw = (json.dumps(receipt, sort_keys=True, separators=(",", ":")) + "\n").encode()
    temporary = Path(tempfile.mkdtemp(prefix=".forge-bundle-", dir=output.parent))
    try:
        for name, (data, mode) in payloads.items():
            destination = temporary / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)
            destination.chmod(mode)
        (temporary / "bundle.json").write_bytes(raw)
        if os.path.lexists(output):
            raise FileExistsError(output)
        temporary.rename(output)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
    return hashlib.sha256(raw).hexdigest()


def source_commit(repo):
    repo = Path(repo).absolute()
    status = subprocess.check_output(["git", "-C", str(repo), "status", "--porcelain"],
                                     text=True)
    require(not status.strip(), "source repository must be clean before release")
    return subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"],
                                   text=True).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staging", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--version", required=True)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    pin = create_bundle(args.staging, args.output, args.version, source_commit(args.repo))
    print(pin)


if __name__ == "__main__":
    main()
