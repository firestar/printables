"""Card-data sources for the offline index build and price refresh.

  mtg      Scryfall bulk data ("default_cards") + /cards/{id}
  pokemon  Pokémon TCG API v2 (/cards paged, optional X-Api-Key)
  ygo      YGOPRODeck v7 cardinfo.php (one record per artwork)

Each iterator yields (CardRecord, image_url).  Images are fetched at small
size into an on-disk cache.
"""

import json
import logging
import time
from pathlib import Path

import cv2
import numpy as np

from .index import CardRecord

log = logging.getLogger(__name__)
USER_AGENT = "card-scanner-host/0.1 (+https://github.com/; hobby card sorter)"
SCRYFALL = "https://api.scryfall.com"
POKEMON = "https://api.pokemontcg.io/v2"
YGO = "https://db.ygoprodeck.com/api/v7"


def _client(timeout=60.0):
    import httpx
    return httpx.Client(timeout=timeout, headers={"User-Agent": USER_AGENT, "Accept": "*/*"}, follow_redirects=True)


def _get_json(client, url, retries=4, **kw):
    for attempt in range(retries):
        try:
            r = client.get(url, **kw)
            if r.status_code == 429:
                time.sleep(2.0 * (attempt + 1))
                continue
            r.raise_for_status()
            return r.json()
        except Exception as e:  # network hiccup
            if attempt == retries - 1:
                raise
            log.warning("GET %s failed (%s); retrying", url, e)
            time.sleep(1.5 * (attempt + 1))


def _f(v):
    try:
        return float(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


# --- Scryfall ------------------------------------------------------------------
def scryfall_record(c):
    img = (c.get("image_uris") or {}).get("small")
    if not img and c.get("card_faces"):
        img = (c["card_faces"][0].get("image_uris") or {}).get("small")
    prices = c.get("prices") or {}
    return CardRecord(id="mtg:" + c["id"], game="mtg", name=c.get("name", ""), set_code=c.get("set", ""),
                      set_name=c.get("set_name", ""), collector_number=str(c.get("collector_number", "")),
                      rarity=c.get("rarity", "unknown"), image_uri=img or "", api_id=c["id"],
                      usd=_f(prices.get("usd")), usd_foil=_f(prices.get("usd_foil")),
                      finishes=c.get("finishes") or ["nonfoil"], prices_at=time.time()), img


def iter_scryfall(client, cache_dir, limit=None, skip_digital=True):
    bulk = _get_json(client, SCRYFALL + "/bulk-data")
    entry = next(b for b in bulk["data"] if b["type"] == "default_cards")
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    local = cache_dir / "scryfall_default_cards.json"
    if not local.exists() or time.time() - local.stat().st_mtime > 86400:
        log.info("downloading Scryfall bulk %s (%.0f MB)", entry["updated_at"], entry.get("size", 0) / 1e6)
        with client.stream("GET", entry["download_uri"]) as r, open(local, "wb") as f:
            for chunk in r.iter_bytes(1 << 20):
                f.write(chunk)
    with open(local) as f:
        cards = json.load(f)
    n = 0
    for c in cards:
        if skip_digital and c.get("digital"):
            continue
        if c.get("layout") in ("token", "emblem", "art_series", "double_faced_token"):
            continue
        rec, img = scryfall_record(c)
        if not img:
            continue
        yield rec, img
        n += 1
        if limit and n >= limit:
            break


def scryfall_prices(client, api_id):
    c = _get_json(client, SCRYFALL + "/cards/" + api_id)
    time.sleep(0.1)  # Scryfall asks for <= 10 req/s
    p = c.get("prices") or {}
    return _f(p.get("usd")), _f(p.get("usd_foil"))


# --- Pokémon TCG API -------------------------------------------------------------
def pokemon_price(c):
    prices = ((c.get("tcgplayer") or {}).get("prices") or {})
    normal = None
    foil = None
    for k, v in prices.items():
        m = _f((v or {}).get("market")) or _f((v or {}).get("mid"))
        if m is None:
            continue
        if k in ("normal", "1stEditionNormal", "unlimited"):
            normal = m if normal is None else min(normal, m)
        else:
            foil = m if foil is None else max(foil, m)
    if normal is None and foil is not None and not prices.get("holofoil"):
        normal = foil
    return normal, foil


def pokemon_record(c):
    usd, usd_foil = pokemon_price(c)
    img = (c.get("images") or {}).get("small", "")
    finishes = []
    prices = ((c.get("tcgplayer") or {}).get("prices") or {})
    if any(k in prices for k in ("normal", "1stEditionNormal", "unlimited")):
        finishes.append("nonfoil")
    if any("olo" in k for k in prices):
        finishes.append("foil")
    return CardRecord(id="pokemon:" + c["id"], game="pokemon", name=c.get("name", ""),
                      set_code=(c.get("set") or {}).get("id", ""), set_name=(c.get("set") or {}).get("name", ""),
                      collector_number=str(c.get("number", "")), rarity=(c.get("rarity") or "unknown").lower(),
                      image_uri=img, api_id=c["id"], usd=usd, usd_foil=usd_foil,
                      finishes=finishes or ["nonfoil"], prices_at=time.time()), img


def iter_pokemon(client, api_key="", limit=None):
    headers = {"X-Api-Key": api_key} if api_key else {}
    page, n = 1, 0
    while True:
        data = _get_json(client, POKEMON + "/cards", params={"page": page, "pageSize": 250,
                                                             "select": "id,name,number,rarity,set,images,tcgplayer"},
                         headers=headers)
        for c in data.get("data", []):
            rec, img = pokemon_record(c)
            if img:
                yield rec, img
                n += 1
                if limit and n >= limit:
                    return
        if page * 250 >= data.get("totalCount", 0) or not data.get("data"):
            return
        page += 1


def pokemon_prices(client, api_id, api_key=""):
    headers = {"X-Api-Key": api_key} if api_key else {}
    c = _get_json(client, POKEMON + "/cards/" + api_id, headers=headers, params={"select": "tcgplayer"})
    return pokemon_price(c.get("data") or {})


# --- YGOPRODeck -------------------------------------------------------------------
def ygo_records(c):
    prices = (c.get("card_prices") or [{}])[0]
    usd = _f(prices.get("tcgplayer_price")) or _f(prices.get("cardmarket_price"))
    sets = c.get("card_sets") or []
    rarity = (sets[0].get("set_rarity") if sets else "unknown") or "unknown"
    set_code = sets[0].get("set_code", "").split("-")[0] if sets else ""
    set_name = sets[0].get("set_name", "") if sets else ""
    out = []
    for im in c.get("card_images") or []:
        img = im.get("image_url_small") or im.get("image_url")
        rec = CardRecord(id="ygo:%s" % im["id"], game="ygo", name=c.get("name", ""), set_code=set_code,
                         set_name=set_name, collector_number=str(im["id"]), rarity=rarity.lower(), image_uri=img,
                         api_id=str(c["id"]), usd=usd, usd_foil=None, finishes=["nonfoil"], prices_at=time.time())
        out.append((rec, img))
    return out


def iter_ygo(client, limit=None):
    data = _get_json(client, YGO + "/cardinfo.php")
    n = 0
    for c in data.get("data", []):
        for rec, img in ygo_records(c):
            yield rec, img
            n += 1
            if limit and n >= limit:
                return


def ygo_prices(client, api_id):
    data = _get_json(client, YGO + "/cardinfo.php", params={"id": api_id})
    c = (data.get("data") or [{}])[0]
    prices = (c.get("card_prices") or [{}])[0]
    return _f(prices.get("tcgplayer_price")), None


# --- image cache --------------------------------------------------------------------
class ImageCache:
    def __init__(self, root):
        self.root = Path(root)

    def path_for(self, card_id):
        game, sep, rest = card_id.partition(":")
        if not sep:  # ids without a game prefix (e.g. synthetic demo cards)
            game, rest = "local", card_id
        safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in rest)
        return self.root / game / (safe + ".jpg")

    def fetch(self, client, card_id, url):
        p = self.path_for(card_id)
        if p.exists() and p.stat().st_size > 0:
            return p
        p.parent.mkdir(parents=True, exist_ok=True)
        for attempt in range(3):
            try:
                r = client.get(url)
                if r.status_code == 429:
                    time.sleep(2)
                    continue
                r.raise_for_status()
                p.write_bytes(r.content)
                return p
            except Exception as e:
                if attempt == 2:
                    log.warning("image %s failed: %s", url, e)
                    return None
                time.sleep(1)
        return None

    def load(self, card_id):
        p = self.path_for(card_id)
        if not p.exists():
            return None
        img = cv2.imread(str(p))
        return img


def build_index(index, games, cache_dir, api_key="", limit=None, progress=None):
    """Download metadata + small images and hash them into `index`."""
    cache = ImageCache(cache_dir)
    with _client() as client:
        for game in games:
            if game == "mtg":
                it = iter_scryfall(client, Path(cache_dir) / "bulk", limit)
            elif game == "pokemon":
                it = iter_pokemon(client, api_key, limit)
            elif game == "ygo":
                it = iter_ygo(client, limit)
            else:
                raise ValueError("unknown game %s" % game)
            n = 0
            for rec, url in it:
                p = cache.fetch(client, rec.id, url)
                if p is None:
                    continue
                img = cv2.imread(str(p))
                if img is None:
                    continue
                index.add(rec, img, commit=False)
                n += 1
                if n % 200 == 0:
                    index.commit()
                    if progress:
                        progress(game, n)
                if game == "mtg":
                    time.sleep(0.05)  # Scryfall image CDN: be polite
            index.commit()
            index.set_meta("built_" + game, time.time())
            if progress:
                progress(game, n)
    index.load()
