"""Pure-Python reader <-> controller link protocol (see ../PROTOCOL.md).

Mirrors lib/mb_protocol: framing, HMAC-SHA256/128 tag, payload packing,
streaming decoder and replay guard.  Standard library only.
"""

import hashlib
import hmac
import struct

SOF = 0xA5
PROTO_VERSION = 2
KEY_LEN = 32
HEADER_LEN = 8
TAG_LEN = 16
MAX_PAYLOAD = 32

SRC_READER = ord("R")
SRC_CONTROLLER = ord("C")

MSG = {
    "HELLO": 0x01,
    "BAND_SCAN": 0x10,
    "FINGER_MATCH": 0x11,
    "FINGER_NOMATCH": 0x12,
    "TAMPER": 0x13,
    "ENROLL_RESULT": 0x14,
    "FEEDBACK": 0x20,
    "ENROLL_FINGER": 0x21,
    "SET_CONFIG": 0x22,
    "DELETE_FINGER": 0x23,
}
MSG_NAME = {v: k for k, v in MSG.items()}

FEEDBACK = ["IDLE", "READING", "NEED_FINGER", "GRANTED", "DENIED", "ERROR", "OFFLINE",
            "ENROLL_BAND", "ENROLL_FINGER", "ENROLL_OK", "ENROLL_FAIL", "LOCKOUT"]
# HELLO.caps bits (build-time capabilities of the sender)
CAP_FINGERPRINT = 0x01
CAP_NFC = 0x02
CAPS_V1 = CAP_FINGERPRINT | CAP_NFC  # a 12-byte v1 HELLO implies these



def tag(key, data):
    return hmac.new(key, data, hashlib.sha256).digest()[:TAG_LEN]


def encode(key, src, mtype, ctr, payload=b""):
    if len(payload) > MAX_PAYLOAD:
        raise ValueError("payload too long")
    head = struct.pack("<BBBBI", SOF, len(payload), src, mtype, ctr) + payload
    return head + tag(key, head)


class Frame:
    def __init__(self, src, mtype, ctr, payload):
        self.src, self.type, self.ctr, self.payload = src, mtype, ctr, payload

    def __repr__(self):
        return "Frame(%s ctr=%d src=%s %s)" % (MSG_NAME.get(self.type, hex(self.type)), self.ctr,
                                               chr(self.src), describe(self.type, self.payload))


def parse(key, buf):
    """Returns (status, frame, consumed); status is ok/need_more/bad_sof/bad_len/bad_tag."""
    if len(buf) < 1:
        return "need_more", None, 0
    if buf[0] != SOF:
        return "bad_sof", None, 0
    if len(buf) < 2:
        return "need_more", None, 0
    n = buf[1]
    if n > MAX_PAYLOAD:
        return "bad_len", None, 0
    total = HEADER_LEN + n + TAG_LEN
    if len(buf) < total:
        return "need_more", None, 0
    if not hmac.compare_digest(tag(key, bytes(buf[:HEADER_LEN + n])), bytes(buf[HEADER_LEN + n:total])):
        return "bad_tag", None, 0
    _, _, src, mtype, ctr = struct.unpack("<BBBBI", bytes(buf[:HEADER_LEN]))
    return "ok", Frame(src, mtype, ctr, bytes(buf[HEADER_LEN:HEADER_LEN + n])), total


class Decoder:
    """Streaming decoder with the same resync rules as FrameDecoder."""

    def __init__(self, key):
        self.key = key
        self.buf = bytearray()
        self.bad_tag = self.bad_len = 0

    def feed(self, data):
        out = []
        for b in data:
            self.buf.append(b)
            while self.buf:
                st, fr, used = parse(self.key, self.buf)
                if st == "ok":
                    del self.buf[:used]
                    out.append(fr)
                    break
                if st == "need_more":
                    break
                if st == "bad_sof":
                    k = 1
                    while k < len(self.buf) and self.buf[k] != SOF:
                        k += 1
                    del self.buf[:k]
                else:
                    if st == "bad_tag":
                        self.bad_tag += 1
                    else:
                        self.bad_len += 1
                    del self.buf[:1]
        return out


class ReplayGuard:
    def __init__(self, last=0, window=1 << 20):
        self.last, self.window = last, window

    def check(self, ctr):
        if ctr <= self.last:
            return "replay"
        if ctr - self.last > self.window:
            return "out_of_window"
        return "fresh"

    def accept(self, ctr):
        self.last = max(self.last, ctr)


# ---- payloads ----------------------------------------------------------------------
def hello(flags=0, uptime=0, last_seen=0, fw=(0, 1), caps=0, v1=False):
    """v1=True builds the old 12-byte HELLO (proto 1, no caps byte)."""
    if v1:
        return struct.pack("<BBBBII", 1, fw[0], fw[1], flags, uptime, last_seen)
    return struct.pack("<BBBBIIB", PROTO_VERSION, fw[0], fw[1], flags, uptime, last_seen, caps)


def hello_caps(p):
    """Capability bits of a HELLO payload (CAPS_V1 for a v1 HELLO)."""
    return p[12] if len(p) >= 13 else CAPS_V1


def band_scan(uid):
    return bytes([len(uid)]) + bytes(uid)


def finger_match(page, score):
    return struct.pack("<HH", page, score)


def u8(v):
    return bytes([v])


def u16(v):
    return struct.pack("<H", v)


def feedback(state, hold_ms=0):
    if isinstance(state, str):
        state = FEEDBACK.index(state)
    return struct.pack("<BH", state, hold_ms)


def enroll_result(page, status):
    return struct.pack("<HB", page, status)


def set_config(brightness, volume):
    return bytes([brightness, volume])


def describe(mtype, p):
    name = MSG_NAME.get(mtype)
    try:
        if name == "HELLO":
            v, ma, mi, fl, up, ls = struct.unpack("<BBBBII", p[:12])
            return "proto=%d fw=%d.%d flags=0x%02x caps=0x%02x up=%ds last_seen=%d" % (
                v, ma, mi, fl, hello_caps(p), up, ls)
        if name == "BAND_SCAN":
            return "uid=" + p[1:1 + p[0]].hex().upper()
        if name == "FINGER_MATCH":
            return "page=%d score=%d" % struct.unpack("<HH", p[:4])
        if name in ("FINGER_NOMATCH", "TAMPER"):
            return "value=%d" % p[0]
        if name == "ENROLL_RESULT":
            return "page=%d status=%d" % struct.unpack("<HB", p[:3])
        if name == "FEEDBACK":
            s, hold = struct.unpack("<BH", p[:3])
            return "%s hold=%dms" % (FEEDBACK[s] if s < len(FEEDBACK) else s, hold)
        if name in ("ENROLL_FINGER", "DELETE_FINGER"):
            return "page=%d" % struct.unpack("<H", p[:2])
        if name == "SET_CONFIG":
            return "brightness=%d volume=%d" % (p[0], p[1])
    except (struct.error, IndexError):
        return "malformed " + p.hex()
    return p.hex()


def load_key(hex_or_path):
    """Key from a 64-char hex string or from include/secrets.h."""
    s = hex_or_path.strip()
    if len(s) == 64 and all(c in "0123456789abcdefABCDEF" for c in s):
        return bytes.fromhex(s)
    with open(s) as f:
        text = f.read()
    import re
    m = re.search(r"LINK_KEY_HEX\s+\"([0-9a-fA-F]{64})\"", text)
    if not m:
        raise ValueError("no LINK_KEY_HEX in " + s)
    return bytes.fromhex(m.group(1))
