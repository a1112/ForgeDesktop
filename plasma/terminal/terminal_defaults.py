#!/usr/bin/python3
"""One-time, reversible terminal preference migration; run with Plasma stopped."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile

STATE = ".local/state/forge-desktop/rterm-defaults-v1.json"
CONFIGS = (".config/kdeglobals", ".config/xfce4/helpers.rc", ".config/kglobalshortcutsrc",
           ".config/plasma-org.kde.plasma.desktop-appletsrc")
LIMIT = 4 * 1024 * 1024
STATE_LIMIT = 48 * 1024 * 1024  # Four files, before/after, base64 plus metadata.


def require(condition, message):
    if not condition:
        raise ValueError(message)


def safe(path, limit=LIMIT):
    require(not any(p.is_symlink() for p in (path, *path.parents)), "terminal settings path contains symlink")
    if path.exists():
        require(path.is_file() and path.stat().st_nlink == 1 and path.stat().st_size <= limit,
                "terminal settings file is invalid or too large")


def read(path, limit=LIMIT):
    safe(path, limit)
    return path.read_bytes() if path.exists() else None


def sha(raw):
    return hashlib.sha256(raw).hexdigest() if raw is not None else None


def put(home, path, raw):
    limit = STATE_LIMIT if path == home / STATE else LIMIT
    safe(path, limit)
    require(raw is None or len(raw) <= limit, "terminal configuration output exceeds limit")
    if raw is None:
        path.unlink(missing_ok=True)
        return
    created = []
    parent = path.parent
    while not parent.exists():
        created.append(parent)
        parent = parent.parent
    identity = home.stat()
    for parent in reversed(created):
        parent.mkdir(mode=0o700)
        if os.name == "posix" and os.geteuid() == 0:
            os.chown(parent, identity.st_uid, identity.st_gid)
    fd, name = tempfile.mkstemp(prefix=".rterm-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(name, 0o600)
        if os.name == "posix" and os.geteuid() == 0:
            os.chown(name, identity.st_uid, identity.st_gid)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def ini_set(raw, group, key, value):
    """Change only the chosen entry, retaining other lines and comments."""
    lines, _, _ = ini_entry(raw, group, key)
    header = "[" + group + "]" if group else None
    start = 0 if header is None else next((i + 1 for i, line in enumerate(lines) if line.strip() == header), None)
    if start is None:
        if lines and not lines[-1].endswith("\n"):
            lines[-1] += "\n"
        lines.extend([header + "\n", key + "=" + value + "\n"])
        return "".join(lines).encode()
    end = next((i for i in range(start, len(lines)) if lines[i].startswith("[")), len(lines))
    found = [i for i in range(start, end) if lines[i].split("=", 1)[0].strip() == key]
    require(len(found) <= 1, "duplicate terminal configuration key")
    if found:
        lines[found[0]] = key + "=" + value + "\n"
    else:
        if end and not lines[end - 1].endswith("\n"):
            lines[end - 1] += "\n"
        lines.insert(end, key + "=" + value + "\n")
    return "".join(lines).encode()


def updates(before):
    kde = ini_set(before[CONFIGS[0]], "General", "TerminalApplication", "forge-terminal")
    kde = ini_set(kde, "General", "TerminalService", "org.forge.RTerm.desktop")
    helpers = ini_set(before[CONFIGS[1]], "", "TerminalEmulator", "forge-terminal")
    shortcuts = ini_set(before[CONFIGS[2]], "org.forge.RTerm.desktop", "_launch",
                        "Ctrl+Alt+T,Ctrl+Alt+T,R-Term")
    shortcuts = ini_set(shortcuts, "org.forge.RTerm.desktop", "_k_friendly_name", "R-Term")
    # Release this exact shortcut from previous terminal launchers only.
    text = shortcuts.decode()
    for group in ("xfce4-terminal.desktop", "org.kde.konsole.desktop"):
        ini_entry(shortcuts, group, "_launch")
        match = re.search(r"(?ms)^\[" + re.escape(group) + r"\]\n(.*?)(?=^\[|\Z)", text)
        if match and re.search(r"(?m)^_launch=Ctrl\+Alt\+T,", match.group(1)):
            text = ini_set(text.encode(), group, "_launch", "none,none,Terminal").decode()
    layout = before[CONFIGS[3]]
    if layout is not None:
        # Only launcher-list lines, never arbitrary applet settings or the whole layout.
        lines = layout.splitlines(keepends=True)
        group = ""
        old_id, new_id = b"applications:xfce4-terminal.desktop", b"applications:org.forge.RTerm.desktop"
        for index, line in enumerate(lines):
            if line.startswith(b"["):
                group = line.decode().strip().split("[$", 1)[0][1:-1]
            key, separator, value = line.partition(b"=")
            if key != b"launchers" and not key.startswith(b"launchers["):
                continue
            content = value.rstrip(b"\r\n")
            tokens = content.split(b",")
            if separator and old_id in tokens:
                ini_entry(layout, group, "launchers")
                lines[index] = key + separator + b",".join(
                    new_id if token == old_id else token for token in tokens) + value[len(content):]
        layout = b"".join(lines)
    return dict(zip(CONFIGS, (kde, helpers, text.encode(), layout)))


def load_state(home):
    raw = read(home / STATE, STATE_LIMIT)
    if raw is None:
        return None
    value = json.loads(raw)
    require(type(value) is dict and value.get("schemaVersion") == 1
            and value.get("status") in ("prepared", "applied", "restored")
            and set(value.get("files", {})) == set(CONFIGS), "invalid terminal migration receipt")
    for item in value["files"].values():
        require(type(item) is dict and set(item) == {"before", "after", "afterSha256"},
                "invalid terminal backup entry")
        for key in ("before", "after"):
            raw = None if item[key] is None else base64.b64decode(item[key], validate=True)
            require(raw is None or len(raw) <= LIMIT, "terminal backup entry exceeds limit")
            if key == "after":
                require(sha(raw) == item["afterSha256"], "terminal backup entry digest mismatch")
    return value


def save_state(home, state):
    put(home, home / STATE, (json.dumps(state, sort_keys=True, indent=2) + "\n").encode())


def apply(home):
    home = Path(home).absolute()
    require(home.is_dir() and not home.is_symlink(), "user home missing or symlinked")
    ensure_offline(home)
    before = {name: read(home / name) for name in CONFIGS}
    state = load_state(home)
    if state is not None and state["status"] in ("applied", "restored"):
        return state
    if state is None:
        after = updates(before)
        require(all(raw is None or len(raw) <= LIMIT for raw in after.values()),
                "terminal configuration output exceeds limit")
        state = {"schemaVersion": 1, "status": "prepared", "files": {
            name: {"before": None if before[name] is None else base64.b64encode(before[name]).decode(),
                   "after": None if after[name] is None else base64.b64encode(after[name]).decode(),
                   "afterSha256": sha(after[name])} for name in CONFIGS}}
        save_state(home, state)  # Durable backup precedes every settings mutation.
    for name, item in state["files"].items():
        old = None if item["before"] is None else base64.b64decode(item["before"], validate=True)
        new = None if item["after"] is None else base64.b64decode(item["after"], validate=True)
        require(before[name] in (old, new), "settings changed during terminal migration")
    for name, item in state["files"].items():
        put(home, home / name, None if item["after"] is None else base64.b64decode(item["after"], validate=True))
    state["status"] = "applied"
    save_state(home, state)
    return state


def ini_entry(raw, group, key):
    """Locate one owned key without normalizing unrelated KConfig text."""
    lines = (raw or b"").decode("utf-8").splitlines(keepends=True)
    if group:
        require(not any(line.strip().startswith("[" + group + "][$") for line in lines),
                "modified terminal configuration group flags")
        starts = [i + 1 for i, line in enumerate(lines) if line.strip() == "[" + group + "]"]
        require(len(starts) <= 1, "duplicate terminal configuration group")
        if not starts:
            return lines, None, None
        start = starts[0]
    else:
        start = 0
    end = next((i for i in range(start, len(lines)) if lines[i].startswith("[")), len(lines))
    found = []
    for i in range(start, end):
        name = lines[i].split("=", 1)[0].strip()
        require(not name.startswith(key + "["), "modified terminal configuration key flags")
        if name == key:
            require("=" in lines[i], "invalid terminal configuration key")
            found.append(i)
    require(len(found) <= 1, "duplicate terminal configuration key")
    index = found[0] if found else None
    value = None if index is None else lines[index].split("=", 1)[1].rstrip("\r\n")
    return lines, index, value


def ini_restore_entry(raw, group, key, value):
    if value is not None:
        return ini_set(raw, group, key, value)
    lines, index, _ = ini_entry(raw, group, key)
    if index is not None:
        del lines[index]
    return "".join(lines).encode()


def restore_launcher_list(old, new, current):
    if current in (old, new):
        return old
    require(old is not None and new is not None and current is not None,
            "terminal Dock launcher was removed after migration")
    old_id, new_id = "applications:xfce4-terminal.desktop", "applications:org.forge.RTerm.desktop"
    before, after, now = old.split(","), new.split(","), current.split(",")
    require(before.count(old_id) == 1 and before.count(new_id) == 0
            and after == [new_id if item == old_id else item for item in before],
            "ambiguous terminal Dock backup; restore manually")
    if now.count(old_id) == 1 and now.count(new_id) == 0:
        return current  # This exact launcher has already been restored.
    require(now.count(new_id) == 1 and now.count(old_id) == 0,
            "terminal Dock launcher changed after migration")
    return ",".join(old_id if item == new_id else item for item in now)


def semantic_restore(name, old, new, current):
    if old == new or current == old:
        return current
    if current == new:
        return old  # Preserve the original exact-byte rollback when possible.
    keys = {
        CONFIGS[0]: [("General", "TerminalApplication"), ("General", "TerminalService")],
        CONFIGS[1]: [("", "TerminalEmulator")],
        CONFIGS[2]: [("org.forge.RTerm.desktop", "_launch"),
                     ("org.forge.RTerm.desktop", "_k_friendly_name"),
                     ("xfce4-terminal.desktop", "_launch"), ("org.kde.konsole.desktop", "_launch")],
    }.get(name)
    if keys is None:
        groups = set(re.findall(r"(?m)^\[([^\r\n]+)\]\s*$", (new or b"").decode()))
        keys = [(group, "launchers") for group in sorted(groups)]
    result = current
    for group, key in keys:
        old_value = ini_entry(old, group, key)[2]
        new_value = ini_entry(new, group, key)[2]
        if old_value == new_value:
            continue  # A pre-existing R-Term preference is not ours to undo.
        current_value = ini_entry(current, group, key)[2]
        if name == CONFIGS[3]:
            restored = restore_launcher_list(old_value, new_value, current_value)
        else:
            require(current_value in (old_value, new_value),
                    "terminal preference changed after migration: " + name + " [" + group + "] " + key)
            restored = old_value
        if current_value != restored:
            result = ini_restore_entry(result, group, key, restored)
    return result


def restore(home):
    home = Path(home).absolute()
    ensure_offline(home)
    state = load_state(home)
    require(state is not None, "no terminal migration backup")
    if state["status"] == "restored":
        return
    restored, observed = {}, {}
    for name, item in state["files"].items():
        old = None if item["before"] is None else base64.b64decode(item["before"], validate=True)
        new = None if item["after"] is None else base64.b64decode(item["after"], validate=True)
        current = read(home / name)
        observed[name] = current
        restored[name] = semantic_restore(name, old, new, current)
        require(restored[name] is None or len(restored[name]) <= LIMIT,
                "terminal configuration output exceeds limit")
    # Resolve every conflict before the first write. The durable original
    # before/after receipt also makes an interrupted restore retryable.
    require(all(read(home / name) == raw for name, raw in observed.items()),
            "settings changed during terminal restore")
    for name, raw in restored.items():
        if observed[name] != raw:
            put(home, home / name, raw)
    state["status"] = "restored"
    save_state(home, state)


def ensure_offline(home):
    if os.name != "posix":
        return
    import pwd
    owner = home.stat().st_uid
    # An offline image has a different root, and cannot have an active session here.
    try:
        login_home = Path(pwd.getpwuid(owner).pw_dir)
    except KeyError:
        return
    if login_home != home:
        return
    for process in Path("/proc").glob("[0-9]*"):
        try:
            if process.stat().st_uid == owner and (process / "comm").read_text().strip() == "plasmashell":
                raise ValueError("stop Plasma before migrating terminal preferences")
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            continue


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("apply", "restore"))
    parser.add_argument("--home", type=Path, default=Path.home())
    args = parser.parse_args()
    if args.operation == "restore":
        restore(args.home)
    else:
        apply(args.home)


if __name__ == "__main__":
    main()
