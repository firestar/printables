#!/usr/bin/env python3
"""Reader simulator: speaks the link protocol to a real controller through a
USB-RS485 adapter, so the controller + Home Assistant side can be built and
tested before the outdoor pod exists.

    pip install pyserial
    python3 reader_sim.py --port /dev/ttyUSB0 --key ../include/secrets.h
    python3 reader_sim.py ... --no-finger   # announce a reader without R503 (reader_nofp)

Then type commands:
    band 04A1B2C3D4E5F6     present a band (4-10 byte UID, hex)
    finger 3 [score]        R503 matched template page 3
    nomatch                 R503 found no match
    tamper 1|0              open / close the rear hatch
    enroll ok|fail          answer to the pending ENROLL_FINGER (default: auto ok after 3 s)
    quiet                   stop heartbeats (controller should flag the reader offline)
    talk                    resume heartbeats
    quit

Counters persist in --state (JSON) so restarting the simulator is not seen
as a replay.  Controller HELLOs also resync the counter (see PROTOCOL.md).
"""

import argparse
import json
import os
import sys
import threading
import time

import mbproto as p

try:
    import serial  # pyserial
except ImportError:
    serial = None


class Sim:
    def __init__(self, port, key, state_path, auto_enroll, finger=True):
        self.port = port
        self.key = key
        self.state_path = state_path
        self.auto_enroll = auto_enroll
        self.finger = finger
        self.dec = p.Decoder(key)
        self.lock = threading.Lock()
        self.tamper = 0
        self.quiet = False
        self.pending_enroll = None  # (page, due time)
        st = {}
        if os.path.exists(state_path):
            with open(state_path) as f:
                st = json.load(f)
        self.tx = st.get("tx", 0)
        self.rx = p.ReplayGuard(st.get("rx", 0))

    def save(self):
        with open(self.state_path, "w") as f:
            json.dump({"tx": self.tx, "rx": self.rx.last}, f)

    def send(self, name, payload=b""):
        with self.lock:
            self.tx += 1
            frame = p.encode(self.key, p.SRC_READER, p.MSG[name], self.tx, payload)
            self.save()
            self.port.write(frame)
            self.port.flush()
        if name != "HELLO":
            print(">> %s %s" % (name, p.describe(p.MSG[name], payload)))

    def hello(self):
        flags = (1 if self.tamper else 0) | 0x02 | (0x04 if self.finger else 0)  # NFC (+ finger) "ok"
        caps = p.CAP_NFC | (p.CAP_FINGERPRINT if self.finger else 0)
        self.send("HELLO", p.hello(flags=flags, uptime=int(time.monotonic()), last_seen=self.rx.last, caps=caps))

    def on_frame(self, f):
        if f.src != p.SRC_CONTROLLER:
            print("!! reflected frame ignored")
            return
        verdict = self.rx.check(f.ctr)
        if verdict != "fresh":
            print("!! %s ctr=%d rejected (%s)" % (p.MSG_NAME.get(f.type, f.type), f.ctr, verdict))
            return
        self.rx.accept(f.ctr)
        self.save()
        name = p.MSG_NAME.get(f.type, hex(f.type))
        if name == "HELLO":
            last_seen = int.from_bytes(f.payload[8:12], "little")
            if last_seen >= self.tx:  # controller saw more than we remember: jump past it
                self.tx = last_seen
                self.save()
            return
        print("<< %s %s" % (name, p.describe(f.type, f.payload)))
        if name == "ENROLL_FINGER":
            page = int.from_bytes(f.payload[:2], "little")
            self.pending_enroll = (page, time.monotonic() + 3)

    def reader_thread(self):
        while True:
            data = self.port.read(64)
            for fr in self.dec.feed(data):
                self.on_frame(fr)

    def tick_thread(self):
        while True:
            time.sleep(1)
            if not self.quiet:
                self.hello()
            pe = self.pending_enroll
            if pe and self.auto_enroll and time.monotonic() >= pe[1]:
                self.pending_enroll = None
                self.send("ENROLL_RESULT", p.enroll_result(pe[0], 0))

    def repl(self):
        for line in sys.stdin:
            a = line.split()
            if not a:
                continue
            cmd = a[0].lower()
            try:
                if cmd == "band":
                    uid = bytes.fromhex(a[1])
                    if not 4 <= len(uid) <= 10:
                        raise ValueError("UID must be 4-10 bytes")
                    self.send("BAND_SCAN", p.band_scan(uid))
                elif cmd == "finger":
                    self.send("FINGER_MATCH", p.finger_match(int(a[1]), int(a[2]) if len(a) > 2 else 120))
                elif cmd == "nomatch":
                    self.send("FINGER_NOMATCH", p.u8(0))
                elif cmd == "tamper":
                    self.tamper = int(a[1])
                    self.send("TAMPER", p.u8(self.tamper))
                elif cmd == "enroll":
                    if not self.pending_enroll:
                        print("no ENROLL_FINGER pending")
                        continue
                    page = self.pending_enroll[0]
                    self.pending_enroll = None
                    self.send("ENROLL_RESULT", p.enroll_result(page, 0 if a[1] == "ok" else 2))
                elif cmd == "quiet":
                    self.quiet = True
                elif cmd == "talk":
                    self.quiet = False
                elif cmd in ("quit", "exit"):
                    return
                else:
                    print(__doc__)
            except (IndexError, ValueError) as e:
                print("error:", e)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", required=True, help="serial port of the USB-RS485 adapter")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--key", default=os.path.join(os.path.dirname(__file__), "..", "include", "secrets.h"),
                    help="64 hex digits or path to secrets.h")
    ap.add_argument("--manual-enroll", action="store_true", help="do not auto-answer ENROLL_FINGER")
    ap.add_argument("--no-finger", action="store_true", help="announce no fingerprint capability")
    ap.add_argument("--manual-enroll", action="store_true", help="do not auto-answer ENROLL_FINGER")
    a = ap.parse_args()
    if serial is None:
        sys.exit("pip install pyserial")
    sim = Sim(port, p.load_key(a.key), a.state, not a.manual_enroll, finger=not a.no_finger)
    sim = Sim(port, p.load_key(a.key), a.state, not a.manual_enroll)
    threading.Thread(target=sim.reader_thread, daemon=True).start()
    threading.Thread(target=sim.tick_thread, daemon=True).start()
    print("reader simulator on %s, tx counter %d -- type 'help'" % (a.port, sim.tx))
    sim.repl()


if __name__ == "__main__":
    main()
