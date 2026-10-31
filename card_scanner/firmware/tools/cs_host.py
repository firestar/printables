#!/usr/bin/env python3
"""Minimal host for the card scanner motion controller (protocol in ../PROTOCOL.md).

Reference client + bench tool.  No dependencies (raw termios, no pyserial), so it
works against the board (/dev/ttyACM0) and the simulator pty (tools/mcu_sim.py).

    python3 cs_host.py /dev/ttyACM0 ping
    python3 cs_host.py /dev/ttyACM0 status
    python3 cs_host.py /dev/ttyACM0 home
    python3 cs_host.py /dev/ttyACM0 sort 1
    python3 cs_host.py /dev/ttyACM0 lights 200 80
    python3 cs_host.py /dev/ttyACM0 set feed_speed 180
    python3 cs_host.py /dev/ttyACM0 get feed_speed
    python3 cs_host.py /dev/ttyACM0 raw '{"cmd":"feed"}'
    python3 cs_host.py /dev/ttyACM0 cycle -n 20      # home, then feed/sleeve/sort round-robin
"""
import argparse
import json
import os
import select
import sys
import termios
import time
import tty

# Per-command reply timeouts, seconds.  Motion commands reply when they finish.
TIMEOUTS = {"home": 60, "feed": 60, "sleeve": 30, "sort": 15, "eject_reject": 20}
DEFAULT_TIMEOUT = 2


class CsError(Exception):
    def __init__(self, reply):
        super().__init__(f"{reply.get('err')}: {reply.get('msg')}")
        self.err = reply.get("err")
        self.reply = reply


class Link:
    """One JSON object per line.  call() sends a command and waits for the reply
    with the same id; events and stray replies seen meanwhile go to on_event."""

    def __init__(self, port=None, rfd=None, wfd=None, on_event=None):
        if port is not None:
            fd = os.open(port, os.O_RDWR | os.O_NOCTTY)
            if os.isatty(fd):
                tty.setraw(fd)
                attrs = termios.tcgetattr(fd)
                attrs[4] = attrs[5] = termios.B115200
                termios.tcsetattr(fd, termios.TCSANOW, attrs)
            rfd = wfd = fd
        self.rfd, self.wfd = rfd, wfd
        self.on_event = on_event or (lambda msg: print("event:", json.dumps(msg), file=sys.stderr))
        self.next_id = 1
        self.buf = b""

    def send_line(self, line):
        os.write(self.wfd, line.encode() + b"\n")

    def read_msg(self, timeout):
        """Next JSON object, or None on timeout."""
        end = time.monotonic() + timeout
        while b"\n" not in self.buf:
            left = end - time.monotonic()
            if left <= 0:
                return None
            r, _, _ = select.select([self.rfd], [], [], left)
            if r:
                chunk = os.read(self.rfd, 4096)
                if not chunk:
                    raise EOFError("link closed")
                self.buf += chunk
        line, self.buf = self.buf.split(b"\n", 1)
        line = line.strip()
        if not line:
            return self.read_msg(max(0.0, end - time.monotonic()))
        return json.loads(line)

    def call(self, cmd, timeout=None, check=True, **args):
        cid = self.next_id
        self.next_id += 1
        self.send_line(json.dumps({"id": cid, "cmd": cmd, **args}, separators=(",", ":")))
        timeout = timeout if timeout is not None else TIMEOUTS.get(cmd, DEFAULT_TIMEOUT)
        end = time.monotonic() + timeout
        while True:
            msg = self.read_msg(max(0.0, end - time.monotonic()))
            if msg is None:
                raise TimeoutError(f"no reply to {cmd} (id {cid}) within {timeout} s")
            if msg.get("id") == cid:
                if check and not msg.get("ok"):
                    raise CsError(msg)
                return msg
            self.on_event(msg)


def cycle(link, n, bins):
    link.call("home")
    link.call("lights", top=255, bottom=255)
    for i in range(n):
        try:
            link.call("feed")
        except CsError as e:
            if e.err == "double_feed":
                print(f"card {i}: double feed -> reject bin")
                link.call("eject_reject")
                continue
            raise
        # (the real host captures + recognises the card here)
        link.call("sleeve")
        b = bins[i % len(bins)]
        link.call("sort", bin=b)
        print(f"card {i}: sleeved -> bin {b}")
    link.call("lights", top=0, bottom=0)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("port")
    ap.add_argument("cmd")
    ap.add_argument("args", nargs="*")
    ap.add_argument("-n", type=int, default=10, help="cycle: number of cards")
    ap.add_argument("--bins", default="0,1,2", help="cycle: bins to rotate through")
    a = ap.parse_args()
    link = Link(a.port)
    try:
        if a.cmd == "cycle":
            cycle(link, a.n, [int(b) for b in a.bins.split(",")])
            return 0
        if a.cmd == "raw":
            msg = json.loads(a.args[0])
            cmd = msg.pop("cmd")
            print(json.dumps(link.call(cmd, check=False, **msg)))
            return 0
        kw = {}
        if a.cmd == "sort":
            kw = {"bin": int(a.args[0])}
        elif a.cmd == "lights":
            kw = {"top": int(a.args[0]), "bottom": int(a.args[1])}
        elif a.cmd == "set":
            kw = {"key": a.args[0], "value": float(a.args[1])}
        elif a.cmd == "get":
            kw = {"key": a.args[0]}
        reply = link.call(a.cmd, check=False, **kw)
        print(json.dumps(reply, indent=2 if a.cmd == "status" else None))
        return 0 if reply.get("ok") else 1
    except CsError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
