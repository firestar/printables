"""Ordered bin rules.  First matching rule wins; otherwise `default_bin`.

rule = {"name": str, "bin": 0|1|2, "when": {
    "game": "mtg" | ["mtg", "pokemon"],
    "rarity": "rare" | ["rare", "mythic"],
    "foil": true | false,
    "min_price": 2.0, "max_price": 50.0,
    "recognized": true | false,
    "min_confidence": 0.6, "max_confidence": 0.9,
}}
An empty `when` matches everything.
"""

from .config import GAMES, RARITIES

CONDITION_KEYS = ["game", "rarity", "foil", "min_price", "max_price", "recognized", "min_confidence",
                  "max_confidence"]


def _as_list(v):
    if v is None:
        return None
    return [v] if isinstance(v, str) else list(v)


def matches(when, facts):
    """facts: game, rarity, foil, price, recognized, confidence."""
    when = when or {}
    games = _as_list(when.get("game"))
    if games and facts.get("game") not in games:
        return False
    rarities = _as_list(when.get("rarity"))
    if rarities and (facts.get("rarity") or "unknown") not in rarities:
        return False
    if "foil" in when and when["foil"] is not None and bool(facts.get("foil")) != bool(when["foil"]):
        return False
    if "recognized" in when and when["recognized"] is not None and bool(facts.get("recognized")) != bool(when["recognized"]):
        return False
    price = facts.get("price")
    if when.get("min_price") is not None and (price is None or price < float(when["min_price"])):
        return False
    if when.get("max_price") is not None and (price is None or price > float(when["max_price"])):
        return False
    conf = facts.get("confidence")
    if when.get("min_confidence") is not None and (conf is None or conf < float(when["min_confidence"])):
        return False
    if when.get("max_confidence") is not None and (conf is None or conf > float(when["max_confidence"])):
        return False
    return True


def validate(rules, n_bins=3):
    errors = []
    if not isinstance(rules, list):
        return ["rules must be a list"]
    for i, r in enumerate(rules):
        if not isinstance(r, dict):
            errors.append("rule %d: not a mapping" % i)
            continue
        b = r.get("bin")
        if not isinstance(b, int) or isinstance(b, bool) or not (0 <= b < n_bins):
            errors.append("rule %d: bin must be 0..%d" % (i, n_bins - 1))
        when = r.get("when") or {}
        if not isinstance(when, dict):
            errors.append("rule %d: when must be a mapping" % i)
            continue
        for k in when:
            if k not in CONDITION_KEYS:
                errors.append("rule %d: unknown condition %r" % (i, k))
        for g in _as_list(when.get("game")) or []:
            if g not in GAMES:
                errors.append("rule %d: unknown game %r" % (i, g))
        for rr in _as_list(when.get("rarity")) or []:
            if rr not in RARITIES:
                errors.append("rule %d: unknown rarity %r" % (i, rr))
        for k in ("min_price", "max_price", "min_confidence", "max_confidence"):
            v = when.get(k)
            if v is not None:
                try:
                    float(v)
                except (TypeError, ValueError):
                    errors.append("rule %d: %s must be a number" % (i, k))
    return errors


class RulesEngine:
    def __init__(self, rules, default_bin=2, n_bins=3):
        errs = validate(rules, n_bins)
        if errs:
            raise ValueError("; ".join(errs))
        self.rules = rules
        self.default_bin = default_bin

    def choose(self, facts):
        """Return (bin, rule_name)."""
        for r in self.rules:
            if matches(r.get("when"), facts):
                return int(r["bin"]), r.get("name", "rule")
        return int(self.default_bin), "default"

    @staticmethod
    def facts_from(recognition, price, foil=False):
        rec = recognition.card if recognition else None
        return {
            "game": rec.game if rec else (recognition.game_from_back if recognition else None),
            "rarity": rec.rarity if rec else "unknown",
            "foil": bool(foil or (rec and rec.foil_only)),
            "price": price,
            "recognized": bool(rec) and recognition.confidence >= recognition.review_below,
            "confidence": recognition.confidence if recognition else 0.0,
        }
