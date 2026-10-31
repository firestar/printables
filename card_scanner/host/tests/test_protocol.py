import json
import queue
import threading
import time

import pytest

from cardscanner.mock_mcu import MockMcu
from cardscanner.protocol import McuClient, McuError, McuTimeout, Transport


class ScriptedTransport(Transport):
    """Records writes; replies come from a script keyed by command name."""

    def __init__(self):
        self.sent = []
        self.out = queue.Queue()
        self.script = {}

    def write_line(self, line):
        msg = json.loads(line)
        self.sent.append(msg)
        fn = self.script.get(msg["cmd"])
        if fn:
            reply = fn(msg)
            if reply is not None:
                reply = dict(reply, id=msg["id"])
                self.out.put(json.dumps(reply))

    def read_line(self, timeout):
        try:
            return self.out.get(timeout=timeout)
        except queue.Empty:
            return None


def test_request_reply_ok():
    t = ScriptedTransport()
    t.script["ping"] = lambda m: {"ok": True, "fw": "1.0"}
    c = McuClient(t)
    r = c.ping()
    assert r["fw"] == "1.0" and r["ok"] is True
    assert t.sent[0] == {"id": 1, "cmd": "ping"}
    c.close()


def test_args_are_serialised_flat():
    t = ScriptedTransport()
    t.script["lights"] = lambda m: {"ok": True}
    t.script["sort"] = lambda m: {"ok": True}
    t.script["set"] = lambda m: {"ok": True}
    c = McuClient(t)
    c.lights(top=200, bottom=10)
    c.sort(2)
    c.set("feed_speed", 55)
    assert t.sent[0] == {"id": 1, "cmd": "lights", "top": 200, "bottom": 10}
    assert t.sent[1] == {"id": 2, "cmd": "sort", "bin": 2}
    assert t.sent[2] == {"id": 3, "cmd": "set", "key": "feed_speed", "value": 55}
    with pytest.raises(ValueError):
        c.sort(3)
    c.close()


def test_error_reply_raises_with_code():
    t = ScriptedTransport()
    t.script["feed"] = lambda m: {"ok": False, "err": "hopper_empty", "msg": "empty"}
    c = McuClient(t)
    with pytest.raises(McuError) as ei:
        c.feed()
    assert ei.value.code == "hopper_empty"
    assert ei.value.msg == "empty"
    c.close()


def test_timeout():
    t = ScriptedTransport()  # never replies
    c = McuClient(t)
    t0 = time.monotonic()
    with pytest.raises(McuTimeout):
        c.send("home", timeout=0.3)
    assert time.monotonic() - t0 < 2
    c.close()


def test_events_and_garbage_lines_are_demuxed():
    t = ScriptedTransport()
    seen = []

    def status(m):
        t.out.put("boot garbage not json")
        t.out.put(json.dumps({"evt": "magazine_low", "magazine": 4}))
        t.out.put(json.dumps({"id": 999, "ok": True}))  # unsolicited id, ignored
        return {"ok": True, "homed": False}

    t.script["status"] = status
    c = McuClient(t)
    c.on_event(seen.append)
    r = c.status()
    assert r["homed"] is False
    time.sleep(0.05)
    assert seen == [{"evt": "magazine_low", "magazine": 4}]
    c.close()


def test_out_of_order_replies_match_ids():
    t = ScriptedTransport()
    held = {}

    def slow(m):
        held[m["id"]] = m
        return None

    t.script["get"] = slow
    c = McuClient(t)
    results = {}

    def worker(key):
        results[key] = c.get(key)["value"]

    th = [threading.Thread(target=worker, args=(k,)) for k in ("a", "b")]
    for x in th:
        x.start()
    time.sleep(0.1)
    # answer in reverse order
    for cid in sorted(held, reverse=True):
        t.out.put(json.dumps({"id": cid, "ok": True, "key": held[cid]["key"], "value": held[cid]["key"] * 2}))
    for x in th:
        x.join(2)
    assert results == {"a": "aa", "b": "bb"}
    c.close()


def test_mock_mcu_contract():
    m = MockMcu(hopper=2, magazine=1)
    c = McuClient(m)
    with pytest.raises(McuError) as ei:
        c.feed()
    assert ei.value.code == "not_homed"
    c.home()
    assert c.status()["homed"] is True
    c.feed()
    c.sleeve()
    c.sort(1)
    assert m.bins == [0, 1, 0]
    c.feed()
    with pytest.raises(McuError) as ei:
        c.sleeve()
    assert ei.value.code == "magazine_empty"
    c.sort(2)
    with pytest.raises(McuError) as ei:
        c.feed()
    assert ei.value.code == "hopper_empty"
    with pytest.raises(McuError) as ei:
        c.send("fly")
    assert ei.value.code == "bad_cmd"
    assert c.get("feed_speed")["value"] == 60
    c.set("feed_speed", 70)
    assert c.get("feed_speed")["value"] == 70
    c.estop()
    with pytest.raises(McuError) as ei:
        c.home()
    assert ei.value.code == "estop"
    c.reset()
    c.home()
    c.close()
