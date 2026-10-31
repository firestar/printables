#!/usr/bin/env python3
"""End-to-end: cs_host.Link against the simulator binary (real sequencer code).

    python3 tools/run_native_tests.py --sim && python3 -m unittest tools/test_cs_host.py
"""
import os
import pty
import subprocess
import sys
import tty
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cs_host  # noqa: E402
import mcu_sim  # noqa: E402


class SimRun:
    def __init__(self, *args):
        self.events = []
        self.proc = subprocess.Popen([mcu_sim.find_binary(), "--speed", "50", *args], stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        self.link = cs_host.Link(rfd=self.proc.stdout.fileno(), wfd=self.proc.stdin.fileno(),
                                 on_event=self.events.append)

    def close(self):
        self.proc.stdin.close()
        self.proc.wait(5)
        self.proc.stdout.close()


class TestHostLink(unittest.TestCase):
    def setUp(self):
        self.sim = SimRun()
        self.link = self.sim.link

    def tearDown(self):
        self.sim.close()

    def test_ping_and_status(self):
        self.assertTrue(self.link.call("ping")["fw"].endswith("-sim"))
        st = self.link.call("status")
        self.assertEqual(st["state"], "unhomed")
        for k in ("hopper_empty", "magazine_empty", "sensors", "vacuum_kpa"):
            self.assertIn(k, st)
        self.assertEqual(set(st["sensors"]), {
            "stack_top", "double_feed", "scan_stop", "sleeve_mouth", "sleeve_present", "exit", "elev_home",
            "elev_limit", "pick_home", "tongue_home", "mag_low", "mag_empty", "estop", "lid_open"})

    def test_errors(self):
        with self.assertRaises(cs_host.CsError) as e:
            self.link.call("feed")
        self.assertEqual(e.exception.err, "not_homed")
        self.link.send_line("garbage")
        self.assertEqual(self.link.read_msg(2), {"id": -1, "ok": False, "err": "bad_cmd", "msg": "malformed json"})
        with self.assertRaises(cs_host.CsError) as e:
            self.link.call("nope")
        self.assertEqual(e.exception.err, "bad_cmd")

    def test_cycle(self):
        cs_host.cycle(self.link, 3, [0, 1, 2])
        self.assertEqual(self.link.call("status")["state"], "idle")

    def test_estop_event(self):
        self.link.call("home")
        self.link.send_line("#estop 1")
        msg = self.link.read_msg(2)
        self.assertEqual(msg, {"evt": "estop", "source": "input"})
        with self.assertRaises(cs_host.CsError) as e:
            self.link.call("reset")
        self.assertEqual(e.exception.err, "estop")
        self.link.send_line("#estop 0")
        self.link.read_msg(0.2)
        self.assertEqual(self.link.call("reset")["state"], "unhomed")

    def test_set_get(self):
        self.assertEqual(self.link.call("set", key="jet_ms", value=150)["value"], 150)
        self.assertEqual(self.link.call("get", key="jet_ms"), {"id": 2, "ok": True, "key": "jet_ms", "value": 150})


class TestDoubleFeed(unittest.TestCase):
    def test_double_then_reject(self):
        sim = SimRun("--double", "1")
        try:
            sim.link.call("home")
            with self.assertRaises(cs_host.CsError) as e:
                sim.link.call("feed")
            self.assertEqual(e.exception.err, "double_feed")
            self.assertEqual(sim.link.call("eject_reject"), {"id": 3, "ok": True, "bin": 2})
        finally:
            sim.close()


class TestPty(unittest.TestCase):
    def test_over_pty(self):
        master, slave = pty.openpty()
        tty.setraw(slave)
        proc = subprocess.Popen([mcu_sim.find_binary(), "--speed", "50"], stdin=master, stdout=master,
                                stderr=subprocess.DEVNULL)
        try:
            link = cs_host.Link(os.ttyname(slave))
            self.assertTrue(link.call("ping")["ok"])
            os.close(link.rfd)
        finally:
            proc.terminate()
            proc.wait(5)
            os.close(master)
            os.close(slave)


if __name__ == "__main__":
    unittest.main()
