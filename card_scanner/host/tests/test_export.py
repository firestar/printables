import csv
import io

from cardscanner.index import CardRecord
from cardscanner.inventory import MOXFIELD_HEADER, TCGPLAYER_HEADER, Inventory


def fill(inv):
    sid = inv.start_session(notes="box 1", foil=False, condition="LP")
    inv.add_card(session_id=sid, seq=1, game="mtg", card_id="mtg:1", name="Ember Drake", set_code="syn",
                 set_name="Synthetic Set", collector_number="1", rarity="rare", foil=0, price_usd=4.25,
                 confidence=0.93, method="hash", bin=0, rule="Valuable", status="ok", front_path="a.jpg")
    inv.add_card(session_id=sid, seq=2, game="pokemon", card_id="pokemon:2", name="Pyrokit", set_code="syn",
                 set_name="Synthetic Set", collector_number="12", rarity="rare", foil=1, price_usd=7.75,
                 confidence=0.88, method="hash", bin=0, rule="Valuable", status="ok")
    inv.add_card(session_id=sid, seq=3, status="rejected", error="double_feed", bin=2, rule="reject")
    inv.add_card(session_id=sid, seq=4, game=None, card_id=None, name=None, confidence=0.1, bin=2, rule="default",
                 status="review", candidates=[{"id": "mtg:1", "label": "Ember Drake", "distance": 20}])
    return sid


def test_moxfield_export(tmp_path):
    inv = Inventory(tmp_path / "inv.sqlite")
    sid = fill(inv)
    rows = list(csv.reader(io.StringIO(inv.export_csv("moxfield", sid))))
    assert rows[0] == MOXFIELD_HEADER
    assert len(rows) == 3  # header + 2 identified cards (reject + unresolved review excluded)
    r = dict(zip(rows[0], rows[1]))
    assert r["Name"] == "Ember Drake" and r["Edition"] == "syn" and r["Collector Number"] == "1"
    assert r["Condition"] == "Lightly Played" and r["Foil"] == "" and r["Purchase Price"] == "4.25"
    r2 = dict(zip(rows[0], rows[2]))
    assert r2["Foil"] == "foil" and r2["Count"] == "1"


def test_tcgplayer_export_and_resolve(tmp_path):
    inv = Inventory(tmp_path / "inv.sqlite")
    sid = fill(inv)
    queue = inv.review_queue(sid)
    assert len(queue) == 1 and queue[0]["candidates"][0]["id"] == "mtg:1"
    rec = CardRecord("ygo:9", "ygo", "Chrono Wyrm", "syn", "Synthetic Set", "9", "rare", usd=2.4)
    inv.resolve(queue[0]["id"], rec, price_usd=2.4)
    assert inv.review_queue(sid) == []
    rows = list(csv.reader(io.StringIO(inv.export_csv("tcgplayer", sid))))
    assert rows[0] == TCGPLAYER_HEADER
    assert len(rows) == 4
    r = dict(zip(rows[0], rows[3]))
    assert r["Name"] == "Chrono Wyrm" and r["Set Code"] == "SYN" and r["Printing"] == "Normal"
    assert r["Condition"] == "Lightly Played" and r["Rarity"] == "Rare"
    st = inv.stats(sid)
    assert st["total"] == 4 and st["rejected"] == 1 and st["resolved"] == 1 and st["bins"] == [2, 0, 1]


def test_full_export_has_all_rows(tmp_path):
    inv = Inventory(tmp_path / "inv.sqlite")
    sid = fill(inv)
    rows = list(csv.reader(io.StringIO(inv.export_csv("full", sid))))
    assert rows[0][0] == "session_id"
    assert len(rows) == 3  # identified cards only
    assert inv.sessions()[0]["n"] == 4
