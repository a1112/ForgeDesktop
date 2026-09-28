#!/usr/bin/env python3
"""Reconcile entries from the authenticated, fixed CompatForge desktop client.

No MIME defaults, prefix files or foreign desktop entries are changed. A failed
query is never interpreted as an empty catalogue (which would uninstall entries).
"""
import contextlib
import hashlib
import json
import os
from pathlib import Path
import re
import selectors
import stat
import subprocess
import sys
import tempfile
import time

CLIENT = "/usr/bin/compatforge-cli"
MAX_EXPORT = 16 * 1024 * 1024
MAX_ENTRY = 16 * 1024
MAX_MANIFEST = 256 * 1024
MAX_INTENT = 8 * 1024 * 1024
MAX_ENTRIES = 256
OWNER = "ForgeDesktop.CompatForge.v1"
ENTRY = re.compile(r"org\.forgeos\.CompatForge\.([a-z0-9][a-z0-9-]{0,127})\.([a-z0-9][a-z0-9-]{0,127})\.desktop")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def unique(pairs):
    value = {}
    for key, item in pairs:
        require(key not in value, "duplicate JSON field")
        value[key] = item
    return value


def identity(name):
    require(type(name) is str and len(name.encode("utf-8")) <= 255, "invalid or oversized entry identity")
    match = ENTRY.fullmatch(name)
    require(match is not None, "invalid entry identity")
    for token in match.groups():
        require(not token.startswith("gen-") and token not in {"con", "aux", "prn", "nul"}
                and not re.fullmatch(r"(?:com|lpt)[1-9]", token), "reserved entry identity")
    return match.groups()


def validate_export(export):
    require(type(export) is dict and set(export) == {"schemaVersion", "entries"}
            and export["schemaVersion"] == "1", "invalid desktop export")
    require(type(export["entries"]) is list and len(export["entries"]) <= MAX_ENTRIES,
            "desktop export exceeds 256 entries")
    entries = {}
    for entry in export["entries"]:
        require(type(entry) is dict and set(entry) == {
            "entryId", "applicationId", "generationId", "desktopEntry"}, "invalid launcher record")
        app, launcher = identity(entry["entryId"])
        require(app == entry["applicationId"] and entry["entryId"] not in entries,
                "duplicate or mismatched launcher identity")
        require(type(entry["generationId"]) is str and re.fullmatch(r"gen-job-[a-z0-9-]{1,110}", entry["generationId"]),
                "invalid generation identity")
        content = entry["desktopEntry"]
        require(type(content) is str and len(content.encode("utf-8")) <= MAX_ENTRY
                and content.endswith("\n") and not any(ord(c) < 32 and c != "\n" for c in content),
                "invalid desktop entry text")
        lines = content.splitlines()
        require(lines[0] == "[Desktop Entry]", "invalid desktop group")
        fields = {}
        for line in lines[1:]:
            key, separator, value = line.partition("=")
            require(separator and key not in fields, "invalid or duplicate desktop key")
            fields[key] = value
        require(set(fields) <= {"Type", "Version", "Name", "Exec", "TryExec", "Icon", "Terminal", "Categories",
                               "X-Forge-Managed", "StartupWMClass", "MimeType"}, "unknown desktop key")
        require(fields.get("Exec") == f"{CLIENT} desktop-launch {app} {launcher} -- %F"
                and fields.get("TryExec") == CLIENT and fields.get("Type") == "Application"
                and fields.get("Terminal") == "false" and fields.get("X-Forge-Managed") == "true"
                and fields.get("Name") and fields.get("Icon"), "desktop command differs from fixed client contract")
        entries[entry["entryId"]] = (content.encode("utf-8"), entry["generationId"])
    return entries


def directory(path):
    require(path.is_absolute(), "directory must be absolute")
    for ancestor in reversed((path, *path.parents)):
        if not ancestor.exists() and not ancestor.is_symlink():
            ancestor.mkdir(mode=0o700)
        metadata = ancestor.lstat()
        require(stat.S_ISDIR(metadata.st_mode) and not stat.S_ISLNK(metadata.st_mode),
                "linked or non-directory desktop path")
    metadata = path.stat()
    if os.name == "posix":
        require(metadata.st_uid == os.geteuid() and metadata.st_mode & 0o022 == 0,
                "desktop directory must be user-owned and not writable by others")


def read_regular(path, maximum):
    try:
        # Type validation happens on the opened descriptor. A foreign FIFO must
        # not block open waiting for a writer before fstat can reject it.
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NONBLOCK", 0)
                             | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0))
    except FileNotFoundError:
        return None
    with os.fdopen(descriptor, "rb") as handle:
        metadata = os.fstat(handle.fileno())
        require(stat.S_ISREG(metadata.st_mode) and metadata.st_nlink == 1 and metadata.st_size <= maximum
                and not path.is_symlink(), "desktop record is linked, oversized or non-regular")
        if os.name == "posix":
            require(metadata.st_uid == os.geteuid(), "desktop record belongs to another user")
        data = handle.read(maximum + 1)
        require(len(data) <= maximum, "desktop record exceeds limit")
        return data


def digest(data):
    return hashlib.sha256(data).hexdigest()


def encoded_json(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def validate_manifest(value):
    require(type(value) is dict and set(value) == {"owner", "revision", "entries"} and value["owner"] == OWNER
            and type(value["revision"]) is int and 0 <= value["revision"] < 2**53
            and type(value["entries"]) is dict and len(value["entries"]) <= MAX_ENTRIES, "invalid ownership manifest")
    for name, record in value["entries"].items():
        identity(name)
        require(type(record) is dict and set(record) == {"sha256", "generationId"}
                and type(record["sha256"]) is str and re.fullmatch(r"[0-9a-f]{64}", record["sha256"])
                and type(record["generationId"]) is str and len(record["generationId"]) <= 128, "invalid ownership record")
    require(len(encoded_json(value)) <= MAX_MANIFEST, "ownership manifest exceeds byte limit")
    return value


def sync_directory(path):
    if os.name == "posix":
        fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def atomic_write(path, data, previous):
    descriptor, temporary = tempfile.mkstemp(prefix=".compatforge-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        require(read_regular(path, max(MAX_ENTRY, MAX_MANIFEST)) == previous,
                "desktop file changed during reconciliation")
        os.replace(temporary, path)
        sync_directory(path.parent)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@contextlib.contextmanager
def ownership_lock(state):
    path = state / "owner.lock"
    fd = os.open(path, os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(fd, "r+b") as handle:
        metadata = os.fstat(handle.fileno())
        require(stat.S_ISREG(metadata.st_mode) and metadata.st_nlink == 1 and not path.is_symlink(), "invalid ownership lock")
        if os.name == "posix":
            import fcntl
            require(metadata.st_uid == os.geteuid() and metadata.st_mode & 0o077 == 0, "ownership lock is not private")
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        else:
            import msvcrt
            if metadata.st_size == 0:
                handle.write(b"0")
                handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        yield


def recover_intent(applications, state):
    """Finish a durable transaction only at known before/after file digests.

    Divergent bytes are user-owned conflicts, never overwritten. Publishing the
    intended digest cannot adopt them because later reconciliation checks bytes.
    """
    path = state / "intent-v1.json"
    raw = read_regular(path, MAX_INTENT)
    if raw is None:
        return
    intent = json.loads(raw, object_pairs_hook=unique)
    require(type(intent) is dict and set(intent) == {"owner", "beforeManifest", "afterManifest", "changes"}
            and intent["owner"] == OWNER and type(intent["changes"]) is list
            and len(intent["changes"]) <= MAX_ENTRIES * 2, "invalid desktop transaction")
    before = intent["beforeManifest"]
    require(before is None or type(before) is str and re.fullmatch(r"[0-9a-f]{64}", before), "invalid previous manifest digest")
    after = encoded_json(validate_manifest(intent["afterManifest"]))
    previous = read_regular(state / "launchers-v1.json", MAX_MANIFEST)
    require(previous == after or (digest(previous) if previous is not None else None) == before,
            "manifest changed during interrupted transaction")
    changes = []
    names = set()
    for change in intent["changes"]:
        require(type(change) is dict and set(change) == {"entryId", "beforeSha256", "afterContent"}, "invalid transaction change")
        name = change["entryId"]
        app, _ = identity(name)
        require(name not in names, "duplicate transaction target")
        names.add(name)
        expected = change["beforeSha256"]
        require(expected is None or type(expected) is str and re.fullmatch(r"[0-9a-f]{64}", expected), "invalid before digest")
        content = change["afterContent"]
        if content is not None:
            record = intent["afterManifest"]["entries"].get(name)
            require(record is not None, "new transaction entry is not owned")
            validate_export({"schemaVersion": "1", "entries": [{"entryId": name, "applicationId": app,
                             "generationId": record["generationId"], "desktopEntry": content}]})
            content = content.encode("utf-8")
            require(digest(content) == record["sha256"], "transaction content digest differs")
        else:
            require(name not in intent["afterManifest"]["entries"], "removed entry is still owned")
        changes.append((name, expected, content))
    if previous != after:
        for name, expected, content in changes:
            target = applications / name
            try:
                current = read_regular(target, MAX_ENTRY)
            except (ValueError, OSError):
                continue  # preserve linked, foreign, or edited targets
            if current == content:
                continue  # this step committed before interruption
            if (digest(current) if current is not None else None) != expected:
                continue  # new user content must never be replaced
            if content is None:
                require(read_regular(target, MAX_ENTRY) == current, "entry changed during recovery")
                target.unlink()
                sync_directory(applications)
            else:
                atomic_write(target, content, current)
        atomic_write(state / "launchers-v1.json", after, previous)
    path.unlink()
    sync_directory(state)


def reconcile(export, applications, state):
    desired = validate_export(export)
    directory(applications)
    directory(state)
    with ownership_lock(state):
        recover_intent(applications, state)
        manifest = state / "launchers-v1.json"
        previous = read_regular(manifest, MAX_MANIFEST)
        value = json.loads(previous, object_pairs_hook=unique) if previous is not None else {"owner": OWNER, "revision": 0, "entries": {}}
        validate_manifest(value)
        owned = value["entries"]
        result = {"written": [], "removed": [], "conflicts": []}
        updated = dict(owned)
        changes = []
        for name in sorted(set(owned) | set(desired)):
            path = applications / name
            try:
                current = read_regular(path, MAX_ENTRY)
            except (OSError, ValueError):
                result["conflicts"].append(name)
                continue
            if current is not None and (name not in owned or digest(current) != owned[name]["sha256"]):
                result["conflicts"].append(name)
                continue
            if name in desired:
                content, generation = desired[name]
                if current != content:
                    changes.append((path, content, current))
                    result["written"].append(name)
                updated[name] = {"sha256": digest(content), "generationId": generation}
            else:
                if current is not None:
                    changes.append((path, None, current))
                    result["removed"].append(name)
                updated.pop(name, None)
        require(len(updated) <= MAX_ENTRIES, "ownership manifest exceeds entry limit")
        next_manifest = {"owner": OWNER, "revision": value["revision"] + int(bool(changes) or updated != owned), "entries": updated}
        validate_manifest(next_manifest)
        encoded = encoded_json(next_manifest)
        require(len(encoded) <= MAX_MANIFEST, "ownership manifest exceeds byte limit")
        if encoded != previous:
            intent = {"owner": OWNER, "beforeManifest": digest(previous) if previous is not None else None,
                      "afterManifest": next_manifest, "changes": [{"entryId": path.name,
                       "beforeSha256": digest(current) if current is not None else None,
                       "afterContent": content.decode("utf-8") if content is not None else None}
                      for path, content, current in changes]}
            pending = encoded_json(intent)
            require(len(pending) <= MAX_INTENT, "desktop transaction exceeds byte limit")
            atomic_write(state / "intent-v1.json", pending, None)
            recover_intent(applications, state)
        return result


def query_export():
    """Bound subprocess output while reading it; communicate alone is unbounded."""
    process = subprocess.Popen([CLIENT, "desktop-export"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                               stdin=subprocess.DEVNULL, close_fds=True)
    output = bytearray()
    deadline = time.monotonic() + 70
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            while True:
                remaining = deadline - time.monotonic()
                require(remaining > 0, "CompatForge desktop query timed out")
                if not selector.select(remaining):
                    raise ValueError("CompatForge desktop query timed out")
                chunk = os.read(process.stdout.fileno(), 65536)
                if not chunk:
                    break
                require(len(output) + len(chunk) <= MAX_EXPORT, "CompatForge desktop export exceeds limit")
                output.extend(chunk)
        require(process.wait(timeout=max(0.001, deadline - time.monotonic())) == 0,
                "CompatForge desktop query failed; existing launchers retained")
        return json.loads(output, object_pairs_hook=unique)
    finally:
        if process.poll() is None:
            process.kill()
        process.wait()
        process.stdout.close()


def main():
    require(os.name == "posix" and os.geteuid() != 0, "desktop integration requires an ordinary Linux user")
    require(len(sys.argv) == 1, "desktop sync accepts no command or path arguments")
    home = Path.home()
    data = Path(os.environ.get("XDG_DATA_HOME", home / ".local/share"))
    state = Path(os.environ.get("XDG_STATE_HOME", home / ".local/state")) / "forge-desktop/compatforge"
    result = reconcile(query_export(), data / "applications", state)
    cache = data / "applications/mimeinfo.cache"
    manifest = state / "launchers-v1.json"
    if (result["written"] or result["removed"] or not cache.is_file()
            or cache.stat().st_mtime_ns < manifest.stat().st_mtime_ns):
        # Refresh MIME support declarations. This command does not choose defaults.
        subprocess.run(["/usr/bin/update-desktop-database", str(data / "applications")],
                       check=True, timeout=10, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        print(f"ForgeDesktop: {error}", file=sys.stderr)
        raise SystemExit(1)
