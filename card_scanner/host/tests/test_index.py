import random

from cardscanner.ocr import Ocr
from cardscanner.recognize import Recognizer
from cardscanner.synthetic import photograph, render_back, render_card


def test_lookup_top1_from_photos(synthetic_index):
    idx, cards = synthetic_index
    assert idx.count() == len(cards)
    rng = random.Random(3)
    recog = Recognizer(idx, {"max_distance": 24.0, "review_below": 0.6, "orb_rerank": False})
    for rec, img in cards:
        photo = photograph(img, angle_deg=rng.uniform(-8, 8), scale=rng.uniform(0.7, 0.85))
        back = photograph(render_back(rec.game), angle_deg=rng.uniform(-5, 5))
        r = recog.identify(photo, back)
        assert r.card is not None and r.card.id == rec.id, "%s -> %s (%.2f)" % (rec.name, r.card and r.card.name, r.confidence)
        assert r.confidence >= 0.6
        assert r.game_from_back == rec.game


def test_unknown_card_has_low_confidence(synthetic_index):
    idx, cards = synthetic_index
    recog = Recognizer(idx, {"max_distance": 24.0, "review_below": 0.6, "orb_rerank": False})
    stranger = render_card("Totally Unknown", "mtg", "999", "UNK")
    r = recog.identify(photograph(stranger, angle_deg=2.0))
    assert r.needs_review
    assert r.confidence < 0.6


def test_search_for_combobox(synthetic_index):
    idx, _ = synthetic_index
    res = idx.search("drake")
    assert [r.name for r in res] == ["Ember Drake"]
    res = idx.search("a", game="pokemon")
    assert res and all(r.game == "pokemon" for r in res)
    assert idx.search("001", game="mtg")[0].collector_number == "001"
    assert idx.get("ygo-001").name == "Chrono Wyrm"


def test_back_identifies_game(synthetic_index):
    idx, _ = synthetic_index
    for g in ("mtg", "pokemon", "ygo"):
        game, dist = idx.back_game(render_back(g))
        assert game == g


def test_ocr_fallback_with_injected_engine(synthetic_index):
    idx, cards = synthetic_index
    # Pretend the hash lookup is useless (huge distance) by using a tiny max_distance,
    # and inject a fake OCR engine that reads the name line.
    ocr = Ocr(enabled=True, engine=lambda img, cfg: "Starfall Oracle")
    recog = Recognizer(idx, {"max_distance": 0.5, "review_below": 0.6, "orb_rerank": False, "ocr_below": 0.75}, ocr=ocr)
    rec, img = next((r, i) for r, i in cards if r.name == "Starfall Oracle")
    r = recog.identify(photograph(img, angle_deg=1.0))
    assert r.method == "ocr"
    assert r.card.name == "Starfall Oracle"
    assert r.confidence >= 0.55


def test_rotated_180_photo_still_matches(synthetic_index):
    idx, cards = synthetic_index
    recog = Recognizer(idx, {"orb_rerank": False})
    rec, img = cards[0]
    r = recog.identify(photograph(img, angle_deg=180.0 + 3.0))
    assert r.card.id == rec.id
