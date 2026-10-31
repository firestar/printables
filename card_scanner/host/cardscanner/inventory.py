"""Inventory SQLite DB (sessions + scanned cards) and CSV export in
Moxfield and TCGplayer collection formats."""

import csv
import io
import json
import sqlite3
import threading
import time
import uuid
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
  id TEXT PRIMARY KEY, started_at REAL, ended_at REAL, notes TEXT, foil INTEGER DEFAULT 0, condition TEXT
);
CREATE TABLE IF NOT EXISTS cards (
  id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT, seq INTEGER, ts REAL,
  game TEXT, card_id TEXT, name TEXT, set_code TEXT, set_name TEXT, collector_number TEXT, rarity TEXT,
  foil INTEGER DEFAULT 0, price_usd REAL, confidence REAL, method TEXT,
  bin INTEGER, rule TEXT, status TEXT, error TEXT,
  front_path TEXT, back_path TEXT, candidates TEXT, resolved_by TEXT
);
CREATE INDEX IF NOT EXISTS cards_session ON cards(session_id);
CREATE INDEX IF NOT EXISTS cards_status ON cards(status);
"""
CARD_COLS = ["id", "session_id", "seq", "ts", "game", "card_id", "name", "set_code", "set_name", "collector_number",
             "rarity", "foil", "price_usd", "confidence", "method", "bin", "rule", "status", "error", "front_path",
             "back_path", "candidates", "resolved_by"]
STATUSES = ["ok", "review", "rejected", "error", "resolved", "skipped"]
MOXFIELD_HEADER = ["Count", "Tradelist Count", "Name", "Edition", "Condition", "Language", "Foil", "Tags",
                   "Last Modified", "Collector Number", "Alter", "Proxy", "Purchase Price"]
TCGPLAYER_HEADER = ["Quantity", "Name", "Simple Name", "Set", "Card Number", "Set Code", "Printing", "Condition",
                    "Language", "Rarity", "Product ID", "SKU", "Price"]
FULL_HEADER = ["session_id", "seq", "timestamp", "game", "card_id", "name", "set_code", "set_name",
               "collector_number", "rarity", "foil", "price_usd", "confidence", "method", "bin", "rule", "status",
               "front_path", "back_path"]


class Inventory:
    def __init__(self, db_path):
        Path(str(db_path)).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.lock = threading.RLock()

    # --- sessions -------------------------------------------------------------
    def start_session(self, notes="", foil=False, condition="NM"):
        sid = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:4]
        with self.lock:
            self.conn.execute("INSERT INTO sessions (id, started_at, notes, foil, condition) VALUES (?,?,?,?,?)",
                              (sid, time.time(), notes, int(bool(foil)), condition))
            self.conn.commit()
        return sid

    def end_session(self, sid):
        with self.lock:
            self.conn.execute("UPDATE sessions SET ended_at=? WHERE id=?", (time.time(), sid))
            self.conn.commit()

    def sessions(self, limit=50):
        rows = self.conn.execute(
            "SELECT s.*, (SELECT COUNT(*) FROM cards c WHERE c.session_id=s.id) AS n FROM sessions s "
            "ORDER BY started_at DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]

    def session(self, sid):
        r = self.conn.execute("SELECT * FROM sessions WHERE id=?", (sid,)).fetchone()
        return dict(r) if r else None

    # --- cards ------------------------------------------------------------------
    def add_card(self, **fields):
        fields.setdefault("ts", time.time())
        if isinstance(fields.get("candidates"), (list, dict)):
            fields["candidates"] = json.dumps(fields["candidates"])
        cols = [c for c in CARD_COLS if c != "id" and c in fields]
        with self.lock:
            cur = self.conn.execute("INSERT INTO cards (%s) VALUES (%s)" % (",".join(cols), ",".join("?" * len(cols))),
                                    [fields[c] for c in cols])
            self.conn.commit()
            return cur.lastrowid

    def next_seq(self, sid):
        r = self.conn.execute("SELECT COALESCE(MAX(seq),0)+1 FROM cards WHERE session_id=?", (sid,)).fetchone()
        return r[0]

    def get_card(self, row_id):
        r = self.conn.execute("SELECT * FROM cards WHERE id=?", (row_id,)).fetchone()
        return self._row(r) if r else None

    def _row(self, r):
        d = dict(r)
        try:
            d["candidates"] = json.loads(d["candidates"]) if d.get("candidates") else []
        except ValueError:
            d["candidates"] = []
        return d

    def list_cards(self, session_id=None, status=None, limit=200, offset=0):
        sql, params = "SELECT * FROM cards WHERE 1=1", []
        if session_id:
            sql += " AND session_id=?"
            params.append(session_id)
        if status:
            sts = status if isinstance(status, list) else [status]
            sql += " AND status IN (%s)" % ",".join("?" * len(sts))
            params += sts
        sql += " ORDER BY id DESC LIMIT ? OFFSET ?"
        params += [limit, offset]
        return [self._row(r) for r in self.conn.execute(sql, params)]

    def review_queue(self, session_id=None, limit=200):
        return self.list_cards(session_id, "review", limit)

    def resolve(self, row_id, rec, price_usd=None, resolved_by="operator"):
        """Operator picked the right card for a review-queue entry."""
        with self.lock:
            self.conn.execute(
                "UPDATE cards SET game=?, card_id=?, name=?, set_code=?, set_name=?, collector_number=?, rarity=?, "
                "price_usd=?, confidence=1.0, status='resolved', method='operator', resolved_by=? WHERE id=?",
                (rec.game, rec.id, rec.name, rec.set_code, rec.set_name, rec.collector_number, rec.rarity,
                 price_usd, resolved_by, row_id))
            self.conn.commit()

    def skip(self, row_id):
        with self.lock:
            self.conn.execute("UPDATE cards SET status='skipped' WHERE id=?", (row_id,))
            self.conn.commit()

    def stats(self, session_id):
        rows = self.conn.execute("SELECT status, bin, COUNT(*) n FROM cards WHERE session_id=? GROUP BY status, bin",
                                 (session_id,)).fetchall()
        out = {"total": 0, "ok": 0, "review": 0, "rejected": 0, "error": 0, "resolved": 0, "skipped": 0,
               "bins": [0, 0, 0]}
        for r in rows:
            out["total"] += r["n"]
            out[r["status"]] = out.get(r["status"], 0) + r["n"]
            if r["bin"] is not None and 0 <= r["bin"] < 3 and r["status"] != "rejected":
                out["bins"][r["bin"]] += r["n"]
        return out

    # --- export ------------------------------------------------------------------
    def export_csv(self, fmt="moxfield", session_id=None):
        rows = self.list_cards(session_id, ["ok", "resolved", "review"], limit=1_000_000)
        rows = [r for r in rows if r.get("card_id")]
        rows.reverse()
        buf = io.StringIO()
        w = csv.writer(buf, lineterminator="\n")
        if fmt == "moxfield":
            w.writerow(MOXFIELD_HEADER)
            for r in rows:
                cond = (self.session(r["session_id"]) or {}).get("condition") or "NM"
                w.writerow([1, 0, r["name"], (r["set_code"] or "").lower(), _mox_cond(cond), "English",
                            "foil" if r["foil"] else "", "", time.strftime("%Y-%m-%d", time.localtime(r["ts"])),
                            r["collector_number"] or "", "", "", r["price_usd"] if r["price_usd"] is not None else ""])
        elif fmt == "tcgplayer":
            w.writerow(TCGPLAYER_HEADER)
            for r in rows:
                cond = (self.session(r["session_id"]) or {}).get("condition") or "NM"
                w.writerow([1, r["name"], r["name"], r["set_name"] or "", r["collector_number"] or "",
                            (r["set_code"] or "").upper(), "Foil" if r["foil"] else "Normal", _tcg_cond(cond),
                            "English", (r["rarity"] or "").title(), "", "",
                            r["price_usd"] if r["price_usd"] is not None else ""])
        else:
            w.writerow(FULL_HEADER)
            for r in rows:
                w.writerow([r["session_id"], r["seq"], time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(r["ts"])),
                            r["game"], r["card_id"], r["name"], r["set_code"], r["set_name"], r["collector_number"],
                            r["rarity"], int(bool(r["foil"])), r["price_usd"], r["confidence"], r["method"],
                            r["bin"], r["rule"], r["status"], r["front_path"], r["back_path"]])
        return buf.getvalue()

    def close(self):
        self.conn.close()


_COND = {"NM": ("Near Mint", "Near Mint"), "LP": ("Lightly Played", "Lightly Played"),
         "MP": ("Moderately Played", "Moderately Played"), "HP": ("Heavily Played", "Heavily Played"),
         "DMG": ("Damaged", "Damaged")}


def _mox_cond(c):
    return _COND.get(c, (c, c))[0]


def _tcg_cond(c):
    return _COND.get(c, (c, c))[1]
