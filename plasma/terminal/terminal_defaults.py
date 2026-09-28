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
    lines = (raw or b"").decode("utf-8").splitlines(keepends=True)
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
        match = re.search(r"(?ms)^\[" + re.escape(group) + r"\]\n(.*?)(?=^\[|\Z)", text)
        if match and re.search(r"(?m)^_launch=Ctrl\+Alt\+T,", match.group(1)):
            text = ini_set(text.encode(), group, "_launch", "none,none,Terminal").decode()
    layout = before[CONFIGS[3]]
    if layout is not None:
        # Only launcher-list lines, never arbitrary applet settings or the whole layout.
        layout = re.sub(rb"(?m)^launchers=([^\r\n]*)", lambda m: m.group(0).replace(
            b"applications:xfce4-terminal.desktop", b"applications:org.forge.RTerm.desktop"), layout)
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


def restore(home):
    home = Path(home).absolute()
    ensure_offline(home)
    state = load_state(home)
    require(state is not None, "no terminal migration backup")
    if state["status"] == "restored":
        return
    for name, item in state["files"].items():
        old = None if item["before"] is None else base64.b64decode(item["before"], validate=True)
        current = read(home / name)
        require(sha(current) == item["afterSha256"] or current == old,
                "user settings changed after migration; preserve them and restore manually")
    for name, item in state["files"].items():
        put(home, home / name, None if item["before"] is None else base64.b64decode(item["before"], validate=True))
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
