"""Card recognition: crop/deskew -> hash lookup (+ optional ORB re-rank) ->
OCR fallback, with a confidence in [0, 1].  The back image identifies the
game and is only used to gate/boost the match."""

import logging
from dataclasses import dataclass, field
from typing import Optional

import cv2
import numpy as np

from . import vision
from .index import CardRecord, to_canon

log = logging.getLogger(__name__)


@dataclass
class Recognition:
    card: Optional[CardRecord] = None
    confidence: float = 0.0
    distance: Optional[float] = None
    method: str = "none"            # hash | orb | ocr | none
    game_from_back: Optional[str] = None
    candidates: list = field(default_factory=list)  # [(CardRecord, distance)]
    error: Optional[str] = None
    review_below: float = 0.6
    ocr_text: Optional[str] = None
    canon_front: Optional[np.ndarray] = None
    canon_back: Optional[np.ndarray] = None

    @property
    def needs_review(self):
        return self.card is None or self.confidence < self.review_below

    def to_dict(self):
        return {
            "card": self.card.to_dict() if self.card else None,
            "confidence": round(self.confidence, 3), "distance": self.distance, "method": self.method,
            "game_from_back": self.game_from_back, "error": self.error, "ocr_text": self.ocr_text,
            "candidates": [{"card": c.to_dict(), "distance": round(d, 2)} for c, d in self.candidates],
        }


def orb_matches(a, b, n_features=500):
    orb = cv2.ORB_create(n_features)
    ga = cv2.cvtColor(a, cv2.COLOR_BGR2GRAY) if a.ndim == 3 else a
    gb = cv2.cvtColor(b, cv2.COLOR_BGR2GRAY) if b.ndim == 3 else b
    ka, da = orb.detectAndCompute(ga, None)
    kb, db = orb.detectAndCompute(gb, None)
    if da is None or db is None or len(ka) < 8 or len(kb) < 8:
        return 0
    bf = cv2.BFMatcher(cv2.NORM_HAMMING)
    good = 0
    for pair in bf.knnMatch(da, db, k=2):
        if len(pair) == 2 and pair[0].distance < 0.75 * pair[1].distance:
            good += 1
    return good


class Recognizer:
    def __init__(self, index, cfg=None, image_loader=None, ocr=None):
        cfg = cfg or {}
        self.index = index
        self.top_k = int(cfg.get("top_k", 5))
        self.max_distance = float(cfg.get("max_distance", 24.0))
        self.review_below = float(cfg.get("review_below", 0.6))
        self.ocr_below = float(cfg.get("ocr_below", 0.75))
        self.use_orb = bool(cfg.get("orb_rerank", True)) and image_loader is not None
        self.verify_back = bool(cfg.get("verify_back", True))
        self.image_loader = image_loader  # callable(card_id) -> BGR image or None
        self.ocr = ocr

    def _confidence(self, cands):
        if not cands:
            return 0.0
        best = cands[0][1]
        conf = max(0.0, 1.0 - best / self.max_distance)
        if len(cands) > 1:
            margin = cands[1][1] - best
            if margin < 3.0:
                conf *= 0.6 + 0.4 * (margin / 3.0)
        return float(min(1.0, conf))

    def _rerank(self, canon, cands):
        """ORB re-rank of top-k using cached reference images."""
        scored = []
        for rec, dist in cands:
            ref = self.image_loader(rec.id)
            if ref is None:
                scored.append((rec, dist, None))
                continue
            ref = to_canon(ref)
            m = orb_matches(vision.art_region(canon, rec.game), vision.art_region(ref, rec.game))
            scored.append((rec, dist, m))
        with_orb = [s for s in scored if s[2] is not None]
        if len(with_orb) < 2:
            return cands, "hash"
        with_orb.sort(key=lambda s: -s[2])
        top, second = with_orb[0], with_orb[1]
        if top[2] >= 20 and top[2] >= 1.6 * max(second[2], 1) and top[0].id != cands[0][0].id:
            # strong feature evidence overrides the hash order
            new = [(top[0], min(top[1], cands[0][1] - 0.5))] + [(r, d) for r, d in cands if r.id != top[0].id]
            return new, "orb"
        return cands, "hash"

    def identify(self, front_bgr, back_bgr=None, foil=False):
        rec = Recognition(review_below=self.review_below)
        try:
            canon, _ = vision.extract_card(front_bgr)
        except vision.CardNotFound as e:
            rec.error = "no_card: %s" % e
            return rec
        rec.canon_front = canon
        game = None
        if back_bgr is not None and self.verify_back:
            try:
                back_canon, _ = vision.extract_card(back_bgr)
                rec.canon_back = back_canon
                g, _ = self.index.back_game(back_canon)
                if g is None:
                    g, _ = self.index.back_game(vision.rotate180(back_canon))
                game = g
            except vision.CardNotFound:
                pass
        rec.game_from_back = game

        best_cands, best_canon = [], canon
        for cand_img in (canon, vision.rotate180(canon)):
            cands = self.index.lookup(cand_img, game=game, top_k=self.top_k)
            if cands and (not best_cands or cands[0][1] < best_cands[0][1]):
                best_cands, best_canon = cands, cand_img
        rec.canon_front = best_canon
        method = "hash"
        if best_cands and self.use_orb:
            best_cands, method = self._rerank(best_canon, best_cands)
        rec.candidates = best_cands
        conf = self._confidence(best_cands)
        if best_cands:
            rec.card, rec.distance, rec.method = best_cands[0][0], best_cands[0][1], method
        rec.confidence = conf

        if conf < self.ocr_below and self.ocr and self.ocr.enabled:
            text = self.ocr.read_name(best_canon, game or (rec.card.game if rec.card else "any"))
            rec.ocr_text = text
            if text:
                for cand, ratio in self.index.fuzzy_name(text, game=game, limit=3):
                    in_topk = any(c.id == cand.id for c, _ in best_cands)
                    if ratio >= 0.8 and (in_topk or conf < 0.3):
                        new_conf = 0.55 + 0.4 * (ratio - 0.8) / 0.2
                        if in_topk:
                            new_conf = max(new_conf, conf + 0.2)
                        if new_conf > conf:
                            rec.card, rec.confidence, rec.method = cand, min(1.0, new_conf), "ocr"
                            if not in_topk:
                                rec.candidates = [(cand, 999.0)] + best_cands
                        break
        if rec.card and game and rec.card.game != game:
            rec.confidence *= 0.5
        return rec
