#!/usr/bin/env python3
"""Stage optional R-OS theme files into a fresh directory, never install them."""
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROS_FILES = {
    "plasma/ros-theme/ForgeROS.colors": "usr/share/color-schemes/ForgeROS.colors",
    "docs/design/r-os-tokens-v1.json": "usr/share/forge-desktop/plasma/r-os-tokens-v1.json",
    "plasma/ros-theme/shell/metadata.json": "usr/share/plasma/shells/org.forge.ros/metadata.json",
    "plasma/ros-theme/shell/contents/lockscreen/LockScreen.qml": "usr/share/plasma/shells/org.forge.ros/contents/lockscreen/LockScreen.qml",
}


def stage_theme(output):
    output = Path(output).absolute()
    # Check parent chain before creating or reading an output artifact.
    for ancestor in (output, *output.parents):
        if ancestor.is_symlink():
            raise ValueError("theme output cannot traverse symlinks")
    if output.exists():
        raise FileExistsError(output)
    output.mkdir(parents=True)
    payloads = {}
    for source, relative in ROS_FILES.items():
        data = (ROOT / source).read_bytes()
        destination = output / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
        destination.chmod(0o644)
        payloads[relative] = (data, 0o644)
    return payloads


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    stage_theme(parser.parse_args().output)
