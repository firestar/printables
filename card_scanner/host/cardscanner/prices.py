"""Price lookup with a TTL cache.  The index stores the build-time snapshot;
stale entries are refreshed from the per-card API endpoints when online."""

import logging
import threading
import time

from . import sources

log = logging.getLogger(__name__)


class PriceService:
    def __init__(self, index, ttl_hours=24, pokemon_api_key="", offline=False):
        self.index = index
        self.ttl = ttl_hours * 3600.0
        self.api_key = pokemon_api_key
        self.offline = offline
        self._client = None
        self._lock = threading.Lock()
        self.failures = 0

    def _c(self):
        if self._client is None:
            self._client = sources._client(timeout=10.0)
        return self._client

    def refresh(self, rec):
        if rec.game == "mtg":
            usd, foil = sources.scryfall_prices(self._c(), rec.api_id)
        elif rec.game == "pokemon":
            usd, foil = sources.pokemon_prices(self._c(), rec.api_id, self.api_key)
        elif rec.game == "ygo":
            usd, foil = sources.ygo_prices(self._c(), rec.api_id)
        else:
            return rec
        rec.usd, rec.usd_foil, rec.prices_at = usd, foil, time.time()
        self.index.update_prices(rec.id, usd, foil, rec.prices_at)
        return rec

    def get(self, rec, foil=False):
        """Return (price_usd|None, info dict).  Never raises."""
        if rec is None:
            return None, {"source": "none"}
        age = time.time() - (rec.prices_at or 0)
        source = "cache"
        if age > self.ttl and not self.offline and rec.api_id and self.failures < 5:
            with self._lock:
                try:
                    self.refresh(rec)
                    source = "api"
                    self.failures = 0
                except Exception as e:
                    self.failures += 1
                    log.warning("price refresh failed for %s: %s", rec.id, e)
                    source = "stale"
        price = rec.usd_foil if (foil and rec.usd_foil is not None) else rec.usd
        if price is None and foil is False and rec.usd_foil is not None and rec.foil_only:
            price = rec.usd_foil
        return price, {"source": source, "usd": rec.usd, "usd_foil": rec.usd_foil, "age_h": round(age / 3600, 1)}
