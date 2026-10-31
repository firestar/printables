#!/usr/bin/env python3
"""Build and run the native unit tests (and the simulator) with plain g++.

For machines without PlatformIO.  `pio test -e native` is the normal way and
uses the real Unity; this uses tools/unity_shim/unity.h instead.

    python3 tools/run_native_tests.py          # tests
    python3 tools/run_native_tests.py --sim    # also build .pio/cs_sim (see tools/mcu_sim.py)
"""
import glob
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
FW = os.path.dirname(HERE)
OUT = os.path.join(FW, ".pio", "gxx")
CXX = os.environ.get("CXX", "g++")
FLAGS = ["-std=gnu++17", "-Wall", "-Wextra", "-O1", "-g"]
LIBS = sorted(glob.glob(os.path.join(FW, "lib", "*", "src")))


def lib_sources():
    return sorted(s for d in LIBS for s in glob.glob(os.path.join(d, "*.cpp")))


def build(name, sources, extra_inc=()):
    os.makedirs(OUT, exist_ok=True)
    exe = os.path.join(OUT, name)
    inc = [f"-I{d}" for d in list(LIBS) + list(extra_inc)]
    cmd = [CXX, *FLAGS, *inc, *sources, "-o", exe]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        sys.stdout.write(r.stdout + r.stderr)
        raise SystemExit(f"build failed: {name}")
    if r.stderr.strip():
        sys.stdout.write(r.stderr)  # warnings
    return exe


def main():
    failed = []
    for tdir in sorted(glob.glob(os.path.join(FW, "test", "test_*"))):
        name = os.path.basename(tdir)
        exe = build(name, sorted(glob.glob(os.path.join(tdir, "*.cpp"))) + lib_sources(),
                    [os.path.join(HERE, "unity_shim"), tdir])
        print(f"== {name}")
        r = subprocess.run([exe])
        if r.returncode:
            failed.append(name)
    if "--sim" in sys.argv:
        exe = build("cs_sim", sorted(glob.glob(os.path.join(FW, "src", "sim", "*.cpp"))) + lib_sources(),
                    [os.path.join(FW, "include")])
        print(f"== built {os.path.relpath(exe, FW)}")
    print("FAILED: " + ", ".join(failed) if failed else "ALL PASSED")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
