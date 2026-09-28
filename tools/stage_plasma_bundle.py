#!/usr/bin/env python3
"""Stage the reviewed Plasma files for the bounded bundle producer."""
import argparse
from pathlib import Path
import shutil


def stage(repo, output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    files = {
        "plasma/session/forge-kwin-session": ("usr/libexec/forge-desktop/forge-kwin-session", 0o755),
        "plasma/session/forgedesktop-kwin.desktop": ("usr/share/wayland-sessions/forgedesktop-kwin.desktop", 0o644),
        "plasma/dependencies.json": ("usr/share/forge-desktop/plasma/dependencies.json", 0o644),
        "LICENSE-MIT": ("usr/share/licenses/forge-desktop/LICENSE", 0o644),
        "plasma/terminal/forge_terminal.py": ("usr/bin/forge-terminal", 0o755),
        "plasma/terminal/terminal_defaults.py": ("usr/libexec/forge-desktop/terminal-defaults", 0o755),
        "plasma/terminal/org.forge.RTerm.desktop": ("usr/share/applications/org.forge.RTerm.desktop", 0o644),
        "plasma/terminal/forge-terminal.desktop": ("usr/share/xfce4/helpers/forge-terminal.desktop", 0o644),
        "plasma/terminal/skel-kdeglobals": ("etc/skel/.config/kdeglobals", 0o644),
        "plasma/terminal/skel-kglobalshortcutsrc": ("etc/skel/.config/kglobalshortcutsrc", 0o644),
        "plasma/terminal/skel-helpers.rc": ("etc/skel/.config/xfce4/helpers.rc", 0o644),
    }
    for source, destination in (
        ("plasma/look-and-feel", "usr/share/plasma/look-and-feel/org.forge.desktop"),
        ("plasma/aurorae/ForgeDark", "usr/share/aurorae/themes/ForgeDark"),
        ("plasma/plasmoids/org.forge.windowcontrols", "usr/share/plasma/plasmoids/org.forge.windowcontrols"),
    ):
        root = repo / source
        for path in root.rglob("*"):
            if path.is_file() and "__pycache__" not in path.parts:
                files[path.relative_to(repo).as_posix()] = (destination + "/" + path.relative_to(root).as_posix(), 0o644)
    for source, (name, mode) in files.items():
        path = output / name
        path.parent.mkdir(parents=True, exist_ok=True)
        data = (repo / source).read_bytes()
        # This closed bundle contains text assets only. Normalize every asset
        # so Windows checkouts and Linux git archives produce identical bytes.
        data = data.replace(b"\r\n", b"\n")
        path.write_bytes(data)
        path.chmod(mode)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    stage(args.repo, args.output)


if __name__ == "__main__":
    main()
