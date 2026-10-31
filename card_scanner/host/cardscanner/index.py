"""Perceptual-hash card index (SQLite + in-memory numpy arrays).

Per card: art-region pHash + dHash and a full-card pHash, keyed by a source
id (Scryfall id / Pokémon TCG id / YGOPRODeck image id).  Also stores one
reference back hash per game and a snapshot of prices taken at build time.
"""

import difflib
import sqlite3
import threading
import time
from pathlib import Path
from dataclasses import asdict, dataclass, field
from typing import Optional

import numpy as np

from . import hashing
from .vision import ART_REGION, art_region, CANON_W, CANON_H
import cv2

SCHEMA = """
CREATE TABLE IF NOT EXISTS cards (
  id TEXT PRIMARY KEY, game TEXT NOT NULL, name TEXT NOT NULL, set_code TEXT, set_name TEXT,
  collector_number TEXT, rarity TEXT, image_uri TEXT, api_id TEXT,
  usd REAL, usd_foil REAL, finishes TEXT, prices_at REAL,
  art_phash INTEGER, art_dhash INTEGER, full_phash INTEGER
);
CREATE INDEX IF NOT EXISTS cards_name ON cards(name COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS cards_game ON cards(game);
CREATE TABLE IF NOT EXISTS backs (game TEXT PRIMARY KEY, phash INTEGER, dhash INTEGER);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
"""

COLS = ["id", "game", "name", "set_code", "set_name", "collector_number", "rarity", "image_uri", "api_id",
        "usd", "usd_foil", "finishes", "prices_at"]


@dataclass
class CardRecord:
    id: str
    game: str
    name: str
    set_code: str = ""
    set_name: str = ""
    collector_number: str = ""
    rarity: str = "unknown"
    image_uri: str = ""
    api_id: str = ""
    usd: Optional[float] = None
    usd_foil: Optional[float] = None
    finishes: list = field(default_factory=lambda: ["nonfoil"])
    prices_at: Optional[float] = None

    @classmethod
    def from_row(cls, row):
        d = dict(zip(COLS, row))
        d["finishes"] = [f for f in (d.get("finishes") or "").split(",") if f]
        return cls(**d)

    def to_dict(self):
        return asdict(self)

    @property
    def label(self):
        return "%s (%s %s)" % (self.name, (self.set_code or "").upper(), self.collector_number or "?")

    @property
    def foil_only(self):
        return bool(self.finishes) and all(f in ("foil", "etched", "glossy") for f in self.finishes)


def compute_hashes(canon, game):
    art = art_region(canon, game if game in ART_REGION else "any")
    return hashing.phash(art), hashing.dhash(art), hashing.phash(canon)


def to_canon(img):
    if img.shape[1] != CANON_W or img.shape[0] != CANON_H:
        img = cv2.resize(img, (CANON_W, CANON_H), interpolation=cv2.INTER_AREA)
    return img


class CardIndex:
    def __init__(self, db_path):
        self.db_path = str(db_path)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.executescript(SCHEMA)
        self.lock = threading.RLock()
        self._ids = np.zeros(0, dtype=object)
        self._games = np.zeros(0, dtype=object)
        self._art_p = np.zeros(0, dtype=np.uint64)
        self._art_d = np.zeros(0, dtype=np.uint64)
        self._full_p = np.zeros(0, dtype=np.uint64)
        self._backs = {}
        self._names = {}
        self._dirty = True
        self.load()

    # --- build ------------------------------------------------------------------
    def add(self, rec: CardRecord, img, commit=True):
        """Hash a card image (any size, will be resized to canonical) and store it."""
        art_p, art_d, full_p = compute_hashes(to_canon(img), rec.game)
        self.add_hashes(rec, art_p, art_d, full_p, commit)

    def add_hashes(self, rec: CardRecord, art_p, art_d, full_p, commit=True):
        with self.lock:
            self.conn.execute(
                "INSERT OR REPLACE INTO cards VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (rec.id, rec.game, rec.name, rec.set_code, rec.set_name, rec.collector_number, rec.rarity,
                 rec.image_uri, rec.api_id, rec.usd, rec.usd_foil, ",".join(rec.finishes or []),
                 rec.prices_at or time.time(), hashing.to_signed(art_p), hashing.to_signed(art_d),
                 hashing.to_signed(full_p)))
            if commit:
                self.conn.commit()
            self._dirty = True

    def set_back(self, game, img):
        img = to_canon(img)
        with self.lock:
            self.conn.execute("INSERT OR REPLACE INTO backs VALUES (?,?,?)",
                              (game, hashing.to_signed(hashing.phash(img)), hashing.to_signed(hashing.dhash(img))))
            self.conn.commit()
            self._dirty = True

    def set_meta(self, key, value):
        with self.lock:
            self.conn.execute("INSERT OR REPLACE INTO meta VALUES (?,?)", (key, str(value)))
            self.conn.commit()

    def get_meta(self, key, default=None):
        row = self.conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return row[0] if row else default

    def commit(self):
        with self.lock:
            self.conn.commit()

    def load(self):
        with self.lock:
            rows = self.conn.execute("SELECT id, game, art_phash, art_dhash, full_phash FROM cards").fetchall()
            self._ids = np.array([r[0] for r in rows], dtype=object)
            self._games = np.array([r[1] for r in rows], dtype=object)
            self._art_p = np.array([hashing.from_signed(r[2]) for r in rows], dtype=np.uint64)
            self._art_d = np.array([hashing.from_signed(r[3]) for r in rows], dtype=np.uint64)
            self._full_p = np.array([hashing.from_signed(r[4]) for r in rows], dtype=np.uint64)
            self._backs = {g: (hashing.from_signed(p), hashing.from_signed(d))
                           for g, p, d in self.conn.execute("SELECT game, phash, dhash FROM backs")}
            self._names = {}
            self._dirty = False

    def _ensure(self):
        if self._dirty:
            self.load()

    # --- query --------------------------------------------------------------------
    def count(self, game=None):
        q = "SELECT COUNT(*) FROM cards" + (" WHERE game=?" if game else "")
        return self.conn.execute(q, (game,) if game else ()).fetchone()[0]

    def games(self):
        return [r[0] for r in self.conn.execute("SELECT DISTINCT game FROM cards ORDER BY game")]

    def get(self, card_id):
        row = self.conn.execute("SELECT %s FROM cards WHERE id=?" % ",".join(COLS), (card_id,)).fetchone()
        return CardRecord.from_row(row) if row else None

    def search(self, q, game=None, limit=20):
        """Name/number substring search for the review combobox."""
        q = (q or "").strip()
        sql = "SELECT %s FROM cards WHERE (name LIKE ? COLLATE NOCASE OR collector_number = ?)" % ",".join(COLS)
        params = ["%" + q + "%", q]
        if game:
            sql += " AND game=?"
            params.append(game)
        # prefix matches first, then alphabetical
        sql += " ORDER BY (name LIKE ? COLLATE NOCASE) DESC, name, set_code, collector_number LIMIT ?"
        params += [q + "%", int(limit)]
        return [CardRecord.from_row(r) for r in self.conn.execute(sql, params)]

    def lookup(self, canon, game=None, top_k=5):
        """Hash-match a canonical card image.  Returns [(CardRecord, distance)] sorted ascending.
        distance is a weighted Hamming distance in [0, 64]."""
        self._ensure()
        if len(self._ids) == 0:
            return []
        full_p = hashing.phash(canon)
        d_full = hashing.hamming_many(full_p, self._full_p).astype(np.float32)
        total = np.full(len(self._ids), 999.0, dtype=np.float32)
        games = [game] if game else list(dict.fromkeys(self._games.tolist()))
        for g in games:
            mask = self._games == g
            if not mask.any():
                continue
            art = art_region(canon, g if g in ART_REGION else "any")
            ap, ad = hashing.phash(art), hashing.dhash(art)
            d_ap = hashing.hamming_many(ap, self._art_p[mask]).astype(np.float32)
            d_ad = hashing.hamming_many(ad, self._art_d[mask]).astype(np.float32)
            total[mask] = 0.5 * d_ap + 0.25 * d_ad + 0.25 * d_full[mask]
        k = min(top_k, len(total))
        order = np.argpartition(total, k - 1)[:k]
        order = order[np.argsort(total[order])]
        out = []
        for i in order:
            if total[i] >= 999.0:  # not in the requested game
                continue
            rec = self.get(self._ids[i])
            if rec is not None:
                out.append((rec, float(total[i])))
        return out

    def back_game(self, back_canon, max_distance=18):
        """Identify the game from the card back.  Returns (game|None, distance)."""
        self._ensure()
        if not self._backs:
            return None, None
        p, d = hashing.phash(back_canon), hashing.dhash(back_canon)
        best, best_d = None, 999
        for g, (bp, bd) in self._backs.items():
            dist = 0.6 * hashing.hamming(p, bp) + 0.4 * hashing.hamming(d, bd)
            if dist < best_d:
                best, best_d = g, dist
        return (best if best_d <= max_distance else None), best_d

    def fuzzy_name(self, text, game=None, limit=5, cutoff=0.6):
        """OCR fallback helper: closest card names by sequence ratio."""
        if not text:
            return []
        key = game or "*"
        if key not in self._names:
            sql = "SELECT DISTINCT name FROM cards" + (" WHERE game=?" if game else "")
            self._names[key] = [r[0] for r in self.conn.execute(sql, (game,) if game else ())]
        matches = difflib.get_close_matches(text.strip(), self._names[key], n=limit, cutoff=cutoff)
        out = []
        for m in matches:
            ratio = difflib.SequenceMatcher(None, text.strip().lower(), m.lower()).ratio()
            sql = "SELECT %s FROM cards WHERE name=?" % ",".join(COLS) + (" AND game=?" if game else "")
            for r in self.conn.execute(sql, (m, game) if game else (m,)):
                out.append((CardRecord.from_row(r), ratio))
        return out

    def update_prices(self, card_id, usd, usd_foil, ts=None):
        with self.lock:
            self.conn.execute("UPDATE cards SET usd=?, usd_foil=?, prices_at=? WHERE id=?",
                              (usd, usd_foil, ts or time.time(), card_id))
            self.conn.commit()

    def close(self):
        self.conn.close()
