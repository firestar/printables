#!/usr/bin/env python3
"""Self-test for mbproto.py: python3 -m unittest test_mbproto (from tools/)."""

import os
import subprocess
import sys
import unittest

import mbproto as p

KEY = bytes(range(32))
HERE = os.path.dirname(os.path.abspath(__file__))


class MbprotoTest(unittest.TestCase):
    def test_round_trip(self):
        fr = p.encode(KEY, p.SRC_READER, p.MSG["BAND_SCAN"], 5, p.band_scan(b"\x04\x01\x02\x03\x04\x05\x06"))
        st, f, used = p.parse(KEY, fr)
        self.assertEqual(st, "ok")
        self.assertEqual(used, len(fr))
        self.assertEqual(f.ctr, 5)
        self.assertEqual(p.describe(f.type, f.payload), "uid=04010203040506")

    def test_bad_tag_and_len(self):
        fr = bytearray(p.encode(KEY, p.SRC_READER, p.MSG["HELLO"], 1, p.hello()))
        fr[-1] ^= 1
        self.assertEqual(p.parse(KEY, fr)[0], "bad_tag")
        fr[1] = 99
        self.assertEqual(p.parse(KEY, fr)[0], "bad_len")

    def test_decoder_resync(self):
        good = p.encode(KEY, p.SRC_CONTROLLER, p.MSG["FEEDBACK"], 9, p.feedback("GRANTED", 1500))
        d = p.Decoder(KEY)
        out = d.feed(b"\x00\xa5\x05\x43" + good + b"\x00" * 40)
        self.assertEqual([f.ctr for f in out], [9])

    def test_replay_guard(self):
        g = p.ReplayGuard(10, window=100)
        self.assertEqual(g.check(10), "replay")
        self.assertEqual(g.check(11), "fresh")
        self.assertEqual(g.check(111), "out_of_window")
    def test_hello_caps(self):
        h = p.hello(flags=0x02, caps=p.CAP_NFC)
        self.assertEqual(len(h), 13)
        self.assertEqual(h[0], p.PROTO_VERSION)
        self.assertEqual(p.hello_caps(h), p.CAP_NFC)
        self.assertIn("caps=0x02", p.describe(p.MSG["HELLO"], h))
        v1 = p.hello(flags=0x06, v1=True)
        self.assertEqual(len(v1), 12)
        self.assertEqual(v1[0], 1)
        self.assertEqual(p.hello_caps(v1), p.CAP_FINGERPRINT | p.CAP_NFC)  # v1 readers always had both


    def test_vectors_header_up_to_date(self):
        r = subprocess.run([sys.executable, os.path.join(HERE, "gen_vectors.py"), "--check"], capture_output=True)
        self.assertEqual(r.returncode, 0, r.stdout)


if __name__ == "__main__":
    unittest.main()
