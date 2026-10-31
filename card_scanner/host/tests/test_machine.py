"""State machine + retry policy against the mock controller."""

import time

import numpy as np
import pytest

from cardscanner.camera import FakeCameraPair
from cardscanner.index import CardRecord
from cardscanner.inventory import Inventory
from cardscanner.machine import Orchestrator
from cardscanner.mock_mcu import MockMcu
from cardscanner.protocol import McuClient
from cardscanner.recognize import Recognition
from cardscanner.rules import RulesEngine

RULES = [
    {"name": "Valuable", "bin": 0, "when": {"min_price": 2.0, "min_confidence": 0.6}},
    {"name": "Bulk", "bin": 1, "when": {"recognized": True}},
]


class StubRecognizer:
    """Returns a scripted sequence of recognitions."""

    def __init__(self, seq):
        self.seq = list(seq)
        self.calls = 0

    def identify(self, front, back=None, foil=False):
        self.calls += 1
        r = self.seq.pop(0) if self.seq else self.seq_default()
        return r

    @staticmethod
    def seq_default():
        return Recognition(card=CardRecord("mtg:x", "mtg", "Bulk Card", "syn", "Syn", "1", "common", usd=0.1),
                           confidence=0.9, distance=3.0, method="hash")


class StubPrices:
    def get(self, rec, foil=False):
        return (rec.usd_foil if foil else rec.usd), {"source": "stub"}


def good(name="Ember Drake", usd=4.25, conf=0.9):
    return Recognition(card=CardRecord("mtg:" + name, "mtg", name, "syn", "Syn", "1", "rare", usd=usd),
                       confidence=conf, distance=2.0, method="hash")


def unknown():
    return Recognition(card=None, confidence=0.0, error=None)


def make(tmp_path, mock, recog_seq):
    mcu = McuClient(mock, default_timeout=2.0)
    blank = np.full((240, 320, 3), 200, np.uint8)
    cams = FakeCameraPair(pairs=[(blank, blank)])
    inv = Inventory(tmp_path / "inv.sqlite")
    orch = Orchestrator(mcu, cams, StubRecognizer(recog_seq), RulesEngine(RULES, 2), inv, StubPrices(),
                        {"lights": {"top": 100, "bottom": 50}}, tmp_path / "data")
    return orch, mcu, inv


def wait_for(pred, timeout=5.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if pred():
            return True
        time.sleep(0.01)
    return False


def test_happy_path_sorts_by_rules(tmp_path):
    mock = MockMcu(hopper=3, magazine=10)
    orch, mcu, inv = make(tmp_path, mock, [good(), StubRecognizer.seq_default(), unknown()])
    sid = orch.start(notes="t")
    assert wait_for(lambda: orch.state == "paused" and orch.pause_reason == "hopper_empty")
    assert orch.stats["processed"] == 3
    assert mock.bins == [1, 1, 1]
    assert orch.stats["bins"] == [1, 1, 1]
    cmds = [c for c, _ in mock.log]
    # per card: feed, lights on, lights off, sleeve, sort (sleeve may interleave with lights off);
    # the mock emits a hopper_empty event after the last successful feed, so no 4th feed is attempted
    assert cmds.count("feed") == 3 and cmds.count("sleeve") == 3 and cmds.count("sort") == 3
    assert ("lights", {"top": 100, "bottom": 50}) in mock.log and ("lights", {"top": 0, "bottom": 0}) in mock.log
    rows = inv.list_cards(sid)
    assert len(rows) == 3
    by_seq = {r["seq"]: r for r in rows}
    assert by_seq[1]["name"] == "Ember Drake" and by_seq[1]["bin"] == 0 and by_seq[1]["status"] == "ok"
    assert by_seq[2]["bin"] == 1
    assert by_seq[3]["status"] == "review" and by_seq[3]["bin"] == 2
    assert (tmp_path / "data" / by_seq[1]["front_path"]).exists()
    # refill + resume continues the same session
    mock.refill(hopper=1)
    orch.resume()
    assert wait_for(lambda: orch.stats["processed"] == 4)
    orch.stop()
    assert orch.state == "idle"
    assert inv.session(sid)["ended_at"] is not None


def test_double_feed_is_rejected_unsleeved(tmp_path):
    mock = MockMcu(hopper=4, magazine=10, faults={"feed": {1: "double_feed"}})
    orch, mcu, inv = make(tmp_path, mock, [])
    orch.start()
    assert wait_for(lambda: orch.pause_reason == "hopper_empty")
    cmds = [c for c, _ in mock.log]
    assert "eject_reject" in cmds
    assert cmds.index("eject_reject") < cmds.index("sleeve")
    assert orch.stats["rejected"] == 1
    assert mock.bins[2] == 1
    rows = inv.list_cards(orch.session_id, "rejected")
    assert len(rows) == 1 and rows[0]["error"] == "double_feed"
    orch.stop()


def test_sleeve_open_fail_retries_once_then_pauses(tmp_path):
    mock = MockMcu(hopper=3, magazine=10,
                   faults={"sleeve": {1: ["sleeve_open_fail"], 2: ["sleeve_open_fail", "sleeve_open_fail"]}})
    orch, mcu, inv = make(tmp_path, mock, [])
    orch.start()
    # card 1: one failure then success -> sorted; card 2: two failures -> pause
    assert wait_for(lambda: orch.state == "paused")
    assert orch.pause_reason == "sleeve_open_fail"
    assert orch.stats["processed"] == 2
    assert mock.bins == [0, 1, 0]            # only card 1 sorted so far
    assert orch._pending and orch._pending["stage"] == "sleeve"
    sleeves = [c for c, _ in mock.log].count("sleeve")
    assert sleeves == 4                      # 2 for card 1, 2 for card 2
    # operator clears the sleever and resumes: sleeve retried, then sorted, then next card
    orch.resume()
    assert wait_for(lambda: orch.pause_reason == "hopper_empty")
    assert mock.bins == [0, 3, 0]
    assert orch._pending is None
    orch.stop()


def test_magazine_empty_pauses_and_resumes(tmp_path):
    mock = MockMcu(hopper=2, magazine=0)
    orch, mcu, inv = make(tmp_path, mock, [])
    orch.start()
    assert wait_for(lambda: orch.pause_reason == "magazine_empty")
    assert mock.card_at_station is True
    mock.refill(magazine=10)
    orch.resume()
    assert wait_for(lambda: orch.pause_reason == "hopper_empty")
    assert mock.bins == [0, 2, 0]
    orch.stop()


def test_pick_fail_retries_once(tmp_path):
    mock = MockMcu(hopper=3, magazine=10, faults={"feed": {1: "pick_fail", 3: "pick_fail", 4: "pick_fail"}})
    orch, mcu, inv = make(tmp_path, mock, [])
    orch.start()
    assert wait_for(lambda: orch.state == "paused")
    assert orch.pause_reason == "pick_fail"
    assert mock.bins == [0, 1, 0]
    orch.stop()


def test_estop_event_stops_loop_until_reset(tmp_path):
    mock = MockMcu(hopper=10, magazine=10)
    orch, mcu, inv = make(tmp_path, mock, [])
    orch.start()
    assert wait_for(lambda: orch.stats["processed"] >= 1)
    mock.trip_estop()
    assert wait_for(lambda: orch.state == "estop")
    with pytest.raises(RuntimeError):
        orch.start()
    orch.reset()
    assert orch.state == "idle" and mock.homed
    orch.start()
    assert wait_for(lambda: orch.stats["processed"] >= 1)
    orch.stop()


def test_lid_open_event_pauses(tmp_path):
    mock = MockMcu(hopper=10, magazine=10)
    orch, mcu, inv = make(tmp_path, mock, [])
    orch.start()
    assert wait_for(lambda: orch.stats["processed"] >= 1)
    mock.open_lid()
    assert wait_for(lambda: orch.state == "paused" and orch.pause_reason == "lid_open")
    orch.stop()


def test_foil_batch_uses_foil_price(tmp_path):
    mock = MockMcu(hopper=1, magazine=10)
    r = Recognition(card=CardRecord("mtg:f", "mtg", "Foily", "syn", "Syn", "1", "rare", usd=0.5, usd_foil=9.0),
                    confidence=0.95)
    orch, mcu, inv = make(tmp_path, mock, [r])
    orch.start(foil=True)
    assert wait_for(lambda: orch.pause_reason == "hopper_empty")
    row = inv.list_cards(orch.session_id)[0]
    assert row["price_usd"] == 9.0 and row["foil"] == 1 and row["bin"] == 0
    orch.stop()
