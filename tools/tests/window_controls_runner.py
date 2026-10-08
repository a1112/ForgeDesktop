"""Run the actual window-control QML with test-only KDE import fixtures.

This is a QtQuick unit harness, not a Plasma integration qualification. Qt is
supplied by the caller and is never downloaded or installed by this runner.
"""
import argparse
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def positive_seconds(value):
    seconds = float(value)
    if not math.isfinite(seconds) or seconds <= 0:
        raise argparse.ArgumentTypeError("timeout must be a finite positive number of seconds")
    return seconds


def redact_environment_output(output):
    # vcvars prints the complete inherited environment for parsing. Keep values
    # in memory only, including when a failed or timed-out setup is logged.
    lines = []
    for line in output.splitlines(keepends=True):
        key, separator, _ = line.partition(b"=")
        if line.startswith(b"=") or separator:
            lines.append(key + b"=<environment value redacted>\n")
        else:
            lines.append(line)
    return b"".join(lines)


def run_bounded(command, environment, directory, timeout_seconds, log, environment_output=False):
    """Retain diagnostics; subprocess.run kills and waits for its timed-out child."""
    log.extend(("COMMAND " + json.dumps(command) + f" TIMEOUT {timeout_seconds}s\n").encode())
    try:
        completed = subprocess.run(command, env=environment, cwd=directory,
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   timeout=timeout_seconds)
    except subprocess.TimeoutExpired as error:
        partial = error.stdout or b""
        if isinstance(partial, str):
            partial = partial.encode()
        log.extend(redact_environment_output(partial) if environment_output else partial)
        log.extend(f"\nHARNESS TIMEOUT after {timeout_seconds}s; owned child killed and waited\n".encode())
        raise RuntimeError(f"child command exceeded {timeout_seconds}s") from error
    if not environment_output:
        log.extend(completed.stdout)
    elif completed.returncode:
        log.extend(redact_environment_output(completed.stdout))
    log.extend(f"EXIT {completed.returncode}\n".encode())
    return completed


def build_attached_stub(suite, executable, build_directory, environment, vcvars, log, timeout_seconds):
    """Build only the attached-property fixture; production source stays intact."""
    prefix = executable.parent.parent
    source = suite / "window_controls_plasmoid_plugin.cpp"
    shutil.copytree(suite / "imports", build_directory / "imports", dirs_exist_ok=True)
    output = build_directory / "imports/org/kde/plasma/plasmoid"
    output.mkdir(parents=True, exist_ok=True)
    fixtures = suite / "imports/org/kde/plasma/plasmoid"
    for name in ("qmldir", "PlasmoidItem.qml"):
        shutil.copyfile(fixtures / name, output / name)
    if vcvars:
        environment_batch = build_directory / "window_controls_environment.cmd"
        environment_batch.write_text(f'@echo off\ncall "{vcvars}" >nul\nif errorlevel 1 exit /b %errorlevel%\nset\n', encoding="utf-8")
        completed = run_bounded(["cmd.exe", "/d", "/c", str(environment_batch)],
                                environment, build_directory, timeout_seconds, log, environment_output=True)
        if completed.returncode:
            raise RuntimeError("compiler environment setup failed")
        for line in completed.stdout.decode(errors="replace").splitlines():
            if "=" in line and not line.startswith("="):
                key, value = line.split("=", 1)
                environment[key.upper() if os.name == "nt" else key] = value
    moc_name = "moc.exe" if os.name == "nt" else "moc"
    moc = next((path for path in (prefix / "bin" / moc_name, prefix / "libexec" / moc_name)
                if path.is_file()), None)
    if moc is None:
        raise RuntimeError("the matching Qt moc tool is required")
    include_directories = [prefix / "include", prefix / "include/QtCore", prefix / "include/QtQml", prefix / "include/QtGui", build_directory]
    includes = ["-I" + str(path) for path in include_directories]
    commands = [[str(moc), "-DQT_NO_DEBUG", *includes, str(source), "-o", str(build_directory / "window_controls_plasmoid_plugin.moc")]]
    if os.name == "nt":
        compiler = shutil.which("cl.exe", path=environment.get("PATH"))
        if compiler is None:
            raise RuntimeError("MSVC cl.exe is required; supply --vcvars for the installed toolchain")
        commands.append([compiler, "/nologo", "/LD", "/EHsc", "/std:c++17", "/Zc:__cplusplus", "/permissive-", "/MD",
                         "/DQT_NO_DEBUG", *["/I" + str(path) for path in include_directories], str(source),
                         "/Fo" + str(build_directory / "plugin.obj"), "/link",
                         "/OUT:" + str(output / "window_controls_plasmoid_plugin.dll"),
                         "/LIBPATH:" + str(prefix / "lib"), "Qt6Qml.lib", "Qt6Core.lib", "Qt6Gui.lib"])
    else:
        compiler = os.environ.get("CXX", "c++")
        commands.append([compiler, "-shared", "-fPIC", "-std=c++17", "-DQT_NO_DEBUG", *includes, str(source),
                         "-L" + str(prefix / "lib"), "-Wl,-rpath," + str(prefix / "lib"),
                         "-lQt6Qml", "-lQt6Core", "-lQt6Gui", "-o", str(output / "libwindow_controls_plasmoid_plugin.so")])
    for command in commands:
        completed = run_bounded(command, environment, build_directory, timeout_seconds, log)
        if completed.returncode:
            raise RuntimeError("test-only attached-property fixture build failed")
    return build_directory / "imports"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qmltestrunner", default=os.environ.get("QMLTESTRUNNER"))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--build-dir", type=Path)
    parser.add_argument("--vcvars", type=Path)
    parser.add_argument("--timeout-seconds", type=positive_seconds, default=120.0,
                        help="finite positive timeout for each child command (default: 120 seconds)")
    arguments = parser.parse_args()
    if not arguments.qmltestrunner:
        parser.error("provide --qmltestrunner or QMLTESTRUNNER; the real Qt runtime is required")
    executable = Path(arguments.qmltestrunner).resolve()
    if not executable.is_file():
        parser.error(f"qmltestrunner does not exist: {executable}")
    suite = Path(__file__).resolve().with_name("window_controls")
    environment = {key.upper() if os.name == "nt" else key: value for key, value in os.environ.items()}
    environment["PATH"] = str(executable.parent) + os.pathsep + environment.get("PATH", "")
    environment["QT_QPA_PLATFORM"] = "offscreen"
    environment["QT_LOGGING_RULES"] = "*.debug=false"
    environment["QT_FORCE_STDERR_LOGGING"] = "1"
    environment["QT_QUICK_CONTROLS_STYLE"] = "Basic"
    if os.name == "nt":
        environment["QT_QPA_FONTDIR"] = str(Path(environment.get("WINDIR", "C:/Windows")) / "Fonts")
    log = bytearray()
    with tempfile.TemporaryDirectory(prefix="window-controls-test-") as temporary:
        build_directory = (arguments.build_dir or Path(temporary)).resolve()
        build_directory.mkdir(parents=True, exist_ok=True)
        try:
            generated_import = build_attached_stub(suite, executable, build_directory, environment, arguments.vcvars,
                                                   log, arguments.timeout_seconds)
            command = [str(executable), "-input", str(suite), "-import", str(generated_import), "-o", "-,txt"]
            completed = run_bounded(command, environment, build_directory, arguments.timeout_seconds, log)
            log.extend(f"qmltestrunner exit code: {completed.returncode}\n".encode())
            result = completed.returncode
        except (OSError, RuntimeError) as error:
            log.extend(f"HARNESS ERROR: {error}\n".encode())
            result = 2
    if arguments.output:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_bytes(log)
    sys.stdout.buffer.write(log)
    sys.stdout.buffer.flush()
    return result


if __name__ == "__main__":
    raise SystemExit(main())
