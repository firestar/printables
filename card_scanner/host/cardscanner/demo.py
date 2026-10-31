"""Build the no-hardware demo: a synthetic index, reference backs, a cached
image per card (for ORB re-rank) and a folder of fake camera photos."""

import random
from pathlib import Path

import cv2

from .index import CardIndex, CardRecord
from .sources import ImageCache
from .synthetic import demo_catalog, photograph, render_back, render_card


def setup_demo(index_db, cache_dir, photos_dir, n_unknown=3, seed=7):
    rng = random.Random(seed)
    index = CardIndex(index_db)
    cache = ImageCache(cache_dir)
    photos = Path(photos_dir)
    photos.mkdir(parents=True, exist_ok=True)
    for f in photos.glob("*.jpg"):
        f.unlink()
    cards = demo_catalog()
    shots = []
    for c in cards:
        rec = CardRecord(**c)
        img = render_card(rec.name, rec.game, rec.collector_number, rec.set_code)
        index.add(rec, img, commit=False)
        p = cache.path_for(rec.id)
        p.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(p), cv2.resize(img, (146, 204), interpolation=cv2.INTER_AREA))
        shots.append((img, rec.game))
    for game in ("mtg", "pokemon", "ygo"):
        index.set_back(game, render_back(game))
    index.commit()
    index.set_meta("demo", "1")
    index.load()
    for i in range(n_unknown):
        game = rng.choice(["mtg", "pokemon", "ygo"])
        shots.append((render_card("Mystery Card %d" % (i + 1), game, "999", "UNK"), game))
    rng.shuffle(shots)
    for i, (img, game) in enumerate(shots, 1):
        angle = rng.uniform(-7, 7)
        front = photograph(img, angle_deg=angle, scale=rng.uniform(0.72, 0.85),
                           offset=(rng.randint(-40, 40), rng.randint(-20, 20)))
        back = photograph(render_back(game), angle_deg=-angle, scale=0.8)
        cv2.imwrite(str(photos / ("%02d_front.jpg" % i)), front)
        cv2.imwrite(str(photos / ("%02d_back.jpg" % i)), back)
    index.close()
    return len(cards), len(shots)
