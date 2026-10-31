"""Host side of the Pi <-> ESP32-S3 motion-controller link.

Wire format: 115200 baud, newline-delimited JSON.
  host -> mcu   {"id": <int>, "cmd": "<name>", ...args}
  reply         {"id": <int>, "ok": true, ...} | {"id": <int>, "ok": false, "err": "<code>", "msg": "..."}
  async event   {"evt": "<name>", ...}

Transports are tiny line-oriented objects so the same client drives a real
serial port (SerialTransport) or the in-process MockMcu.
"""

import itertools
import json
import logging
import threading
import time

log = logging.getLogger(__name__)

COMMANDS = ["ping", "home", "status", "feed", "lights", "sleeve", "sort", "eject_reject",
            "set", "get", "estop", "reset"]
ERR_CODES = ["hopper_empty", "magazine_empty", "double_feed", "pick_fail", "jam", "sleeve_open_fail",
             "sleeve_insert_fail", "exit_timeout", "estop", "not_homed", "busy", "bad_cmd"]
EVENTS = ["estop", "lid_open", "hopper_empty", "magazine_low"]


class McuError(Exception):
    """ok:false reply from the controller."""

    def __init__(self, code, msg="", reply=None):
        super().__init__("%s: %s" % (code, msg) if msg else code)
        self.code = code
        self.msg = msg
        self.reply = reply or {}


class McuTimeout(McuError):
    def __init__(self, cmd, timeout):
        super().__init__("timeout", "no reply to %s within %.1fs" % (cmd, timeout))
        self.cmd = cmd


class Transport:
    def write_line(self, line: str):
        raise NotImplementedError

    def read_line(self, timeout: float):
        """Return one line (without newline) or None on timeout."""
        raise NotImplementedError

    def close(self):
        pass


class SerialTransport(Transport):
    def __init__(self, port, baud=115200):
        import serial  # pyserial
        self.ser = serial.Serial(port, baud, timeout=0.1)
        self._wlock = threading.Lock()
        time.sleep(0.3)  # USB-CDC settles / possible reset
        self.ser.reset_input_buffer()

    def write_line(self, line):
        with self._wlock:
            self.ser.write((line + "\n").encode("utf-8"))

    def read_line(self, timeout):
        deadline = time.monotonic() + timeout
        buf = bytearray()
        while time.monotonic() < deadline:
            b = self.ser.read(1)
            if not b:
                continue
            if b == b"\n":
                return buf.decode("utf-8", "replace").rstrip("\r")
            buf += b
        return None

    def close(self):
        self.ser.close()


class McuClient:
    """Thread-safe request/reply client.  A reader thread demultiplexes replies
    (by id) from async events (dispatched to `on_event` callbacks)."""

    def __init__(self, transport: Transport, default_timeout=15.0):
        self.t = transport
        self.default_timeout = default_timeout
        self._ids = itertools.count(1)
        self._pending = {}  # id -> [Event, reply]
        self._plock = threading.Lock()
        self._event_handlers = []
        self._stop = threading.Event()
        self.connected = False
        self.last_event = None
        self._reader = threading.Thread(target=self._read_loop, name="mcu-reader", daemon=True)
        self._reader.start()

    # --- events -------------------------------------------------------------
    def on_event(self, fn):
        self._event_handlers.append(fn)
        return fn

    def _dispatch_event(self, evt):
        self.last_event = evt
        for fn in list(self._event_handlers):
            try:
                fn(evt)
            except Exception:  # pragma: no cover - handler bugs must not kill the reader
                log.exception("event handler failed")

    def _read_loop(self):
        while not self._stop.is_set():
            try:
                line = self.t.read_line(0.25)
            except Exception as e:
                log.warning("transport read failed: %s", e)
                self.connected = False
                time.sleep(0.5)
                continue
            if line is None:
                continue
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except ValueError:
                log.debug("non-JSON line from MCU: %r", line)
                continue
            if not isinstance(msg, dict):
                continue
            if "evt" in msg:
                self._dispatch_event(msg)
            elif "id" in msg:
                with self._plock:
                    slot = self._pending.get(msg["id"])
                if slot is not None:
                    slot[1] = msg
                    slot[0].set()
                else:
                    log.debug("unsolicited reply: %r", msg)

    # --- requests -----------------------------------------------------------
    def send(self, cmd, timeout=None, **args):
        """Send a command; return the reply dict on ok:true, raise McuError otherwise."""
        timeout = self.default_timeout if timeout is None else timeout
        cid = next(self._ids)
        msg = {"id": cid, "cmd": cmd}
        msg.update(args)
        slot = [threading.Event(), None]
        with self._plock:
            self._pending[cid] = slot
        try:
            self.t.write_line(json.dumps(msg, separators=(",", ":")))
            if not slot[0].wait(timeout):
                self.connected = False
                raise McuTimeout(cmd, timeout)
        finally:
            with self._plock:
                self._pending.pop(cid, None)
        reply = slot[1]
        self.connected = True
        if reply.get("ok"):
            return reply
        raise McuError(reply.get("err", "unknown"), reply.get("msg", ""), reply)

    # convenience wrappers (the whole contract) -------------------------------
    def ping(self):
        return self.send("ping", timeout=2.0)

    def home(self):
        return self.send("home", timeout=60.0)

    def status(self):
        return self.send("status", timeout=3.0)

    def feed(self):
        return self.send("feed")

    def lights(self, top=0, bottom=0):
        return self.send("lights", timeout=3.0, top=int(top), bottom=int(bottom))

    def sleeve(self):
        return self.send("sleeve")

    def sort(self, bin):
        if bin not in (0, 1, 2):
            raise ValueError("bin must be 0, 1 or 2")
        return self.send("sort", bin=int(bin))

    def eject_reject(self):
        return self.send("eject_reject")

    def set(self, key, value):
        return self.send("set", timeout=3.0, key=str(key), value=value)

    def get(self, key):
        return self.send("get", timeout=3.0, key=str(key))

    def estop(self):
        return self.send("estop", timeout=2.0)

    def reset(self):
        return self.send("reset", timeout=10.0)

    def close(self):
        self._stop.set()
        self._reader.join(1.0)
        self.t.close()
