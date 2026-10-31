"""In-process stand-in for the ESP32-S3 motion controller.

Implements the JSON protocol as a Transport so McuClient can talk to it
without a serial port.  Simulates hopper/magazine counts, homing, lights,
tunables, e-stop and scripted/random faults.

faults = {
    "feed":   {3: "double_feed", 9: "pick_fail"},        # feed number -> err code
    "sleeve": {5: ["sleeve_open_fail"],                   # card number -> err per attempt
               7: ["sleeve_open_fail", "sleeve_open_fail"]},
    "sort":   {},
    "rate":   0.0,                                        # random fault probability per op
}
"""

import json
import queue
import random
import threading
import time

DELAYS = {"home": 1.2, "feed": 0.45, "sleeve": 0.7, "sort": 0.35, "eject_reject": 0.3, "lights": 0.02}
RANDOM_FAULTS = {"feed": ["double_feed", "pick_fail"], "sleeve": ["sleeve_open_fail", "sleeve_insert_fail"],
                 "sort": ["exit_timeout", "jam"]}
MSGS = {
    "hopper_empty": "input hopper is empty", "magazine_empty": "sleeve magazine is empty",
    "double_feed": "thickness sensor saw two cards", "pick_fail": "no card reached the station",
    "jam": "card did not clear the path", "sleeve_open_fail": "could not open sleeve mouth",
    "sleeve_insert_fail": "card did not enter sleeve", "exit_timeout": "card never reached the bin sensor",
    "estop": "e-stop is active", "not_homed": "axes not homed", "busy": "a motion is in progress",
    "bad_cmd": "unknown command or bad args",
}
DEFAULT_PARAMS = {"feed_speed": 60, "feed_retries": 2, "sleeve_open_ms": 350, "sleeve_push_mm": 92,
                  "sort_dwell_ms": 150, "light_warmup_ms": 80}


class MockMcu:
    def __init__(self, hopper=30, magazine=100, delays=False, faults=None, seed=1, magazine_low_at=5):
        self.hopper = hopper
        self.magazine = magazine
        self.delays = delays
        self.faults = {"feed": {}, "sleeve": {}, "sort": {}, "rate": 0.0}
        self.faults.update(faults or {})
        self.rng = random.Random(seed)
        self.magazine_low_at = magazine_low_at
        self.homed = False
        self.estopped = False
        self.lid_open = False
        self.busy = False
        self.lights = {"top": 0, "bottom": 0}
        self.params = dict(DEFAULT_PARAMS)
        self.card_at_station = False
        self.card_sleeved = False
        self.feeds = 0
        self.cards = 0           # cards successfully fed (sleeve/sort fault index)
        self.sleeve_attempts = 0
        self.log = []            # (cmd, args) history for tests
        self.bins = [0, 0, 0]
        self.t0 = time.time()
        self._out = queue.Queue()
        self._lock = threading.Lock()
        self.closed = False

    # --- Transport interface -------------------------------------------------
    def write_line(self, line):
        try:
            msg = json.loads(line)
        except ValueError:
            return
        if self.delays:
            threading.Thread(target=self._handle, args=(msg,), daemon=True).start()
        else:
            self._handle(msg)

    def read_line(self, timeout):
        try:
            return self._out.get(timeout=timeout)
        except queue.Empty:
            return None

    def close(self):
        self.closed = True

    # --- helpers --------------------------------------------------------------
    def _send(self, obj):
        self._out.put(json.dumps(obj))

    def emit(self, evt, **kw):
        """Push an async event (also used by tests / web demo)."""
        self._send({"evt": evt, **kw})

    def trip_estop(self):
        self.estopped = True
        self.emit("estop")

    def open_lid(self, open=True):
        self.lid_open = open
        if open:
            self.emit("lid_open")

    def refill(self, hopper=None, magazine=None):
        if hopper is not None:
            self.hopper = hopper
        if magazine is not None:
            self.magazine = magazine

    def _err(self, cid, code, msg=None):
        self._send({"id": cid, "ok": False, "err": code, "msg": msg or MSGS.get(code, code)})

    def _ok(self, cid, **kw):
        self._send({"id": cid, "ok": True, **kw})

    def _sleep(self, cmd):
        if self.delays:
            time.sleep(DELAYS.get(cmd, 0.05))

    def _scripted(self, kind, n):
        f = self.faults.get(kind, {})
        v = f.get(n)
        if v is None:
            v = f.get(str(n))
        return v

    def _random_fault(self, kind):
        if self.faults.get("rate", 0) and self.rng.random() < self.faults["rate"]:
            return self.rng.choice(RANDOM_FAULTS[kind])
        return None

    # --- command handling ------------------------------------------------------
    def _handle(self, msg):
        cid = msg.get("id")
        cmd = msg.get("cmd")
        if cid is None or not isinstance(cmd, str):
            return
        self.log.append((cmd, {k: v for k, v in msg.items() if k not in ("id", "cmd")}))
        fn = getattr(self, "cmd_" + cmd, None)
        if fn is None:
            return self._err(cid, "bad_cmd")
        if self.estopped and cmd not in ("ping", "status", "reset", "get", "estop"):
            return self._err(cid, "estop")
        motion = cmd in ("home", "feed", "sleeve", "sort", "eject_reject")
        if motion:
            with self._lock:
                if self.busy:
                    return self._err(cid, "busy")
                self.busy = True
            try:
                if cmd != "home" and not self.homed:
                    return self._err(cid, "not_homed")
                return fn(cid, msg)
            finally:
                self.busy = False
        return fn(cid, msg)

    def cmd_ping(self, cid, m):
        self._ok(cid, fw="mock-0.1", uptime_ms=int((time.time() - self.t0) * 1000))

    def cmd_home(self, cid, m):
        self._sleep("home")
        self.homed = True
        self.card_at_station = False
        self._ok(cid)

    def cmd_status(self, cid, m):
        sensors = {"stack_top": self.hopper > 0, "double_feed": False, "scan_stop": self.card_at_station,
                   "sleeve_mouth": False, "sleeve_present": False, "exit": False, "elev_home": False,
                   "elev_limit": self.hopper <= 0, "pick_home": True, "tongue_home": True,
                   "mag_low": self.magazine <= self.magazine_low_at, "mag_empty": self.magazine <= 0,
                   "estop": self.estopped,
                   "lid_open": self.lid_open}
        self._ok(cid, homed=self.homed, estop=self.estopped, lid_open=self.lid_open, hopper=self.hopper,
                 magazine=self.magazine, lights=dict(self.lights), card_at_station=self.card_at_station,
                 busy=self.busy, bins=list(self.bins), sensors=sensors)

    def cmd_feed(self, cid, m):
        self._sleep("feed")
        if self.hopper <= 0:
            self.emit("hopper_empty")
            return self._err(cid, "hopper_empty")
        if self.card_at_station:
            return self._err(cid, "jam", "station already occupied")
        self.feeds += 1
        fault = self._scripted("feed", self.feeds) or self._random_fault("feed")
        if fault == "double_feed":
            self.hopper = max(0, self.hopper - 2)
            self.card_at_station = True   # two cards sit at the station until eject_reject
            self.card_sleeved = False
            return self._err(cid, "double_feed")
        if fault:
            return self._err(cid, fault)
        self.hopper -= 1
        self.cards += 1
        self.sleeve_attempts = 0
        self.card_at_station = True
        self.card_sleeved = False
        self._ok(cid, hopper=self.hopper, card=self.cards)
        if self.hopper == 0:
            self.emit("hopper_empty")

    def cmd_lights(self, cid, m):
        try:
            top = int(m.get("top", self.lights["top"]))
            bottom = int(m.get("bottom", self.lights["bottom"]))
        except (TypeError, ValueError):
            return self._err(cid, "bad_cmd")
        if not (0 <= top <= 255 and 0 <= bottom <= 255):
            return self._err(cid, "bad_cmd", "0-255")
        self._sleep("lights")
        self.lights = {"top": top, "bottom": bottom}
        self._ok(cid, **self.lights)

    def cmd_sleeve(self, cid, m):
        self._sleep("sleeve")
        if not self.card_at_station:
            return self._err(cid, "pick_fail", "no card at station")
        if self.magazine <= 0:
            return self._err(cid, "magazine_empty")
        scripted = self._scripted("sleeve", self.cards)
        fault = None
        if scripted and self.sleeve_attempts < len(scripted):
            fault = scripted[self.sleeve_attempts]
        self.sleeve_attempts += 1
        fault = fault or self._random_fault("sleeve")
        if fault:
            return self._err(cid, fault)
        self.magazine -= 1
        self.card_sleeved = True
        self._ok(cid, magazine=self.magazine)
        if self.magazine == self.magazine_low_at:
            self.emit("magazine_low", magazine=self.magazine)

    def cmd_sort(self, cid, m):
        b = m.get("bin")
        if b not in (0, 1, 2):
            return self._err(cid, "bad_cmd", "bin must be 0|1|2")
        if not self.card_at_station:
            return self._err(cid, "exit_timeout", "no card at station")
        self._sleep("sort")
        fault = self._scripted("sort", self.cards) or self._random_fault("sort")
        if fault:
            return self._err(cid, fault)
        self.card_at_station = False
        self.bins[b] += 1
        self._ok(cid, bin=b)

    def cmd_eject_reject(self, cid, m):
        self._sleep("eject_reject")
        self.card_at_station = False
        self.bins[2] += 1
        self._ok(cid, bin=2)

    def cmd_set(self, cid, m):
        key, val = m.get("key"), m.get("value")
        if not isinstance(key, str) or key not in self.params and not key.isidentifier():
            return self._err(cid, "bad_cmd", "unknown key")
        self.params[key] = val
        self._ok(cid, key=key, value=val)

    def cmd_get(self, cid, m):
        key = m.get("key")
        if key not in self.params:
            return self._err(cid, "bad_cmd", "unknown key")
        self._ok(cid, key=key, value=self.params[key])

    def cmd_estop(self, cid, m):
        self.estopped = True
        self._ok(cid)
        self.emit("estop")

    def cmd_reset(self, cid, m):
        self.estopped = False
        self.lid_open = False
        self.homed = False
        self.busy = False
        self.card_at_station = False
        self._ok(cid)
