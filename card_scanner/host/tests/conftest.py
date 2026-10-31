import pytest

from cardscanner.index import CardIndex, CardRecord
from cardscanner.synthetic import demo_catalog, render_back, render_card


@pytest.fixture
def synthetic_index(tmp_path):
    """Index of the demo catalog built from rendered synthetic cards."""
    idx = CardIndex(tmp_path / "index.sqlite")
    cards = []
    for c in demo_catalog():
        rec = CardRecord(**c)
        img = render_card(rec.name, rec.game, rec.collector_number, rec.set_code)
        idx.add(rec, img, commit=False)
        cards.append((rec, img))
    for g in ("mtg", "pokemon", "ygo"):
        idx.set_back(g, render_back(g))
    idx.commit()
    idx.load()
    return idx, cards
