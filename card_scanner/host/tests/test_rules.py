import pytest

from cardscanner.rules import RulesEngine, matches, validate

RULES = [
    {"name": "Valuable", "bin": 0, "when": {"min_price": 2.0, "min_confidence": 0.6}},
    {"name": "Foil rares", "bin": 0, "when": {"foil": True, "rarity": ["rare", "mythic"]}},
    {"name": "Pokémon commons", "bin": 2, "when": {"game": "pokemon", "rarity": "common"}},
    {"name": "Recognized", "bin": 1, "when": {"recognized": True}},
]


def facts(**kw):
    base = {"game": "mtg", "rarity": "common", "foil": False, "price": 0.1, "recognized": True, "confidence": 0.9}
    base.update(kw)
    return base


def test_first_match_wins_and_default():
    e = RulesEngine(RULES, default_bin=2)
    assert e.choose(facts(price=5.0)) == (0, "Valuable")
    assert e.choose(facts(price=5.0, confidence=0.3)) == (1, "Recognized")   # too unsure for "Valuable"
    assert e.choose(facts(foil=True, rarity="mythic", price=0.5)) == (0, "Foil rares")
    assert e.choose(facts(foil=False, rarity="mythic", price=0.5)) == (1, "Recognized")
    assert e.choose(facts(game="pokemon", rarity="common")) == (2, "Pokémon commons")
    assert e.choose(facts(recognized=False, price=None, confidence=0.0)) == (2, "default")


def test_price_conditions_require_a_price():
    assert not matches({"min_price": 1.0}, facts(price=None))
    assert not matches({"max_price": 1.0}, facts(price=None))
    assert matches({"max_price": 1.0}, facts(price=0.5))
    assert matches({}, facts())
    assert matches(None, facts())


def test_game_and_rarity_lists():
    assert matches({"game": ["mtg", "ygo"]}, facts(game="ygo"))
    assert not matches({"game": ["mtg", "ygo"]}, facts(game="pokemon"))
    assert matches({"rarity": "unknown"}, facts(rarity=None))


def test_validation():
    assert validate(RULES) == []
    errs = validate([{"name": "x", "bin": 5, "when": {"gane": "mtg"}},
                     {"name": "y", "bin": 1, "when": {"game": "hearthstone", "rarity": "shiny", "min_price": "abc"}}])
    assert any("bin must be" in e for e in errs)
    assert any("unknown condition" in e for e in errs)
    assert any("unknown game" in e for e in errs)
    assert any("unknown rarity" in e for e in errs)
    assert any("must be a number" in e for e in errs)
    with pytest.raises(ValueError):
        RulesEngine([{"bin": 9}])
