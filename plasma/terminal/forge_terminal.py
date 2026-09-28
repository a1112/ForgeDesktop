#!/usr/bin/python3
"""Forge VM terminal entry: preserve argv and require the session's backend."""
import os
import sys


def command(arguments, environment):
    if environment.get("WAYLAND_DISPLAY"):
        backend = "wayland"
    elif environment.get("DISPLAY"):
        backend = "x11"
    else:
        raise ValueError("R-Term needs an active graphical session")
    return ["/usr/bin/rterm", "window", "--renderer", "cpu", "--display-backend", backend,
            "--class", "org.forge.RTerm", *arguments]


def main():
    try:
        # File managers and Terminal=true launchers communicate their directory
        # through the process cwd. R-Term otherwise starts its configured home.
        # An explicit later --cwd still takes precedence in R-Term's parser.
        arguments = command(["--cwd", os.getcwd(), *sys.argv[1:]], os.environ)
        os.execv(arguments[0], arguments)
    except (ValueError, OSError) as error:
        print(f"R-Term: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
