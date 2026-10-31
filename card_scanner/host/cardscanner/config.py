"""YAML config loading + typed access.  Keeps the raw dict so the rules editor
can round-trip it back to disk without losing unknown keys."""

import copy
import os
from pathlib import Path

import yaml

GAMES = ["mtg", "pokemon", "ygo"]
GAME_LABELS = {"mtg": "Magic: The Gathering", "pokemon": "Pokémon", "ygo": "Yu-Gi-Oh!"}
RARITIES = ["common", "uncommon", "rare", "mythic", "special", "bonus", "unknown"]
CARD_SIZES_MM = {"mtg": (63, 88), "pokemon": (63, 88), "ygo": (59, 86)}

DEFAULTS = {
    "serial": {"port": "/dev/ttyACM0", "baud": 115200, "mock": False, "timeout_s": 15.0,
               "mock_options": {"hopper": 30, "magazine": 100, "delays": True, "faults": {}}},
    "cameras": {"backend": "fake", "front_index": 0, "back_index": 1, "size": [2304, 1296],
                "fake_dir": "data/demo/photos", "settle_ms": 120},
    "lights": {"top": 220, "bottom": 180},
    "paths": {"data_dir": "data", "index_db": "data/index.sqlite", "inventory_db": "data/inventory.sqlite",
              "image_cache": "data/cache/images", "backs_dir": "data/backs"},
    "recognition": {"review_below": 0.6, "top_k": 5, "orb_rerank": True, "ocr": True,
                    "ocr_below": 0.75, "max_distance": 24.0, "verify_back": True},
    "prices": {"ttl_hours": 24, "pokemon_api_key": "", "offline": False},
    "rules": [
        {"name": "Valuable", "bin": 0, "when": {"min_price": 2.0, "min_confidence": 0.6}},
        {"name": "Recognized bulk", "bin": 1, "when": {"recognized": True}},
    ],
    "default_bin": 2,
    "bins": [{"id": 0, "name": "Valuable"}, {"id": 1, "name": "Bulk"}, {"id": 2, "name": "Unknown / review"}],
    "tunables": ["feed_speed", "feed_retries", "sleeve_open_ms", "sleeve_push_mm", "sort_dwell_ms", "light_warmup_ms"],
    "web": {"host": "0.0.0.0", "port": 8080},
}


def _merge(base, override):
    out = copy.deepcopy(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


class Config:
    def __init__(self, data=None, path=None):
        self.path = Path(path) if path else None
        self.data = _merge(DEFAULTS, data or {})
        self.root = self.path.parent if self.path else Path(os.getcwd())

    @classmethod
    def load(cls, path):
        path = Path(path)
        with open(path) as f:
            return cls(yaml.safe_load(f) or {}, path)

    def save(self, path=None):
        path = Path(path or self.path)
        with open(path, "w") as f:
            yaml.safe_dump(self.data, f, sort_keys=False, allow_unicode=True)

    def __getitem__(self, key):
        return self.data[key]

    def get(self, key, default=None):
        return self.data.get(key, default)

    def resolve(self, rel):
        """Resolve a path from the config relative to the config file's directory."""
        p = Path(rel)
        return p if p.is_absolute() else (self.root / p)

    @property
    def paths(self):
        return {k: self.resolve(v) for k, v in self.data["paths"].items()}

    @property
    def rules(self):
        return self.data["rules"]

    @rules.setter
    def rules(self, rules):
        self.data["rules"] = rules

    @property
    def default_bin(self):
        return int(self.data.get("default_bin", 2))
