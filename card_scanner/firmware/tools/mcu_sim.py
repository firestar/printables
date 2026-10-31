#!/usr/bin/env python3
"""Run the firmware simulator behind a pseudo-terminal.

The simulator is the real sequencer (lib/cs_motion) on a physics model
(lib/cs_sim), so host software can be developed and tested without hardware.
The host opens the printed pty path exactly like /dev/ttyACM0.

    python3 tools/mcu_sim.py                         # builds with g++ if needed
    python3 tools/mcu_sim.py --link /tmp/cs_scanner  # stable symlink to the pty
    python3 tools/mcu_sim.py -- --speed 5 --double 0.1 --hopper 20

Options after `--` go to the simulator (see src/sim/main.cpp): --speed, --hopper,
--sleeves, --seed, --double, --pick-fail, --lift-fail, --exit-miss, --sleeve-pick-fail.
Sim control lines (start with '#', e.g. "#estop 1", "#lid 1", "#hopper 50") can be
written to the pty by the host for fault-injection tests.
"""
import argparse
import os
import pty
import subprocess
import sys
import tty

HERE = os.path.dirname(os.path.abspath(__file__))
FW = os.path.dirname(HERE)
CANDIDATES = [os.path.join(FW, ".pio", "build", "sim", "program"), os.path.join(FW, ".pio", "gxx", "cs_sim")]


def find_binary(rebuild=False):
    if not rebuild:
        for c in CANDIDATES:
            if os.path.exists(c):
                return c
    subprocess.run([sys.executable, os.path.join(HERE, "run_native_tests.py"), "--sim"], check=True,
                   stdout=subprocess.DEVNULL)
    return CANDIDATES[1]


def main():
    argv = sys.argv[1:]
    sim_args = []
    if "--" in argv:
        i = argv.index("--")
        argv, sim_args = argv[:i], argv[i + 1:]
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--link", help="create this symlink to the pty")
    ap.add_argument("--rebuild", action="store_true", help="rebuild the simulator with g++ first")
    a = ap.parse_args(argv)

    exe = find_binary(a.rebuild)
    master, slave = pty.openpty()
    tty.setraw(slave)  # no echo, no line editing: a byte pipe like USB CDC
    path = os.ttyname(slave)
    if a.link:
        if os.path.islink(a.link):
            os.unlink(a.link)
        os.symlink(path, a.link)
    print(f"card scanner sim on {path}" + (f" ({a.link})" if a.link else ""), flush=True)
    # Keep `slave` open here so the sim does not see a hangup when a host disconnects.
    proc = subprocess.Popen([exe, *sim_args], stdin=master, stdout=master)
    try:
        return proc.wait()
    except KeyboardInterrupt:
        proc.terminate()
        return 0
    finally:
        if a.link and os.path.islink(a.link):
            os.unlink(a.link)


if __name__ == "__main__":
    sys.exit(main())
