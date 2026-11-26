#!/usr/bin/env python3
"""Build and run the hardware-free serial core tests with g++ on this machine.

ArduinoJson and the Improv SDK come from .pio/libdeps, the same copies the
firmware builds against, so run `pio run` or `pio pkg install` once first.
Builds go into .pio/native-tests.

    python3 tools/run_native_tests.py
"""
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
LIBDEPS = ROOT / ".pio" / "libdeps" / "esp32dev"
OUT = ROOT / ".pio" / "native-tests"

SOURCES = [
    ROOT / "test" / "test_serial_core.cpp",
    ROOT / "src" / "serial_core.cpp",
    LIBDEPS / "Improv" / "src" / "improv.cpp",
]
INCLUDES = [ROOT / "include", LIBDEPS / "ArduinoJson" / "src", LIBDEPS / "Improv" / "src"]

# gnu++11 is what this Arduino core builds with. Sanitizers catch any overflow.
VARIANTS = {
    "gnu11-sanitized": ["-std=gnu++11", "-g", "-O1", "-fsanitize=address,undefined", "-fno-sanitize-recover=all"],
    "cpp17": ["-std=c++17", "-O2"],
}


def main() -> int:
    missing = [str(p) for p in SOURCES + INCLUDES if not p.exists()]
    if missing:
        print("missing, run `pio pkg install` first:\n  " + "\n  ".join(missing))
        return 2
    OUT.mkdir(parents=True, exist_ok=True)
    for name, flags in VARIANTS.items():
        exe = OUT / f"test_serial_core-{name}"
        cmd = ["g++", *flags, "-Wall", "-Wextra"]
        cmd += [f"-I{p}" for p in INCLUDES]
        cmd += [str(p) for p in SOURCES] + ["-o", str(exe)]
        print(f"== {name}: building", flush=True)
        if subprocess.run(cmd).returncode != 0:
            return 1
        print(f"== {name}: running", flush=True)
        if subprocess.run([str(exe)]).returncode != 0:
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
