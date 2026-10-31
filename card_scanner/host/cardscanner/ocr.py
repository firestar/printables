"""Tesseract OCR fallback for the name line and set/collector number."""

import logging
import re

import cv2

from .vision import COLLECTOR_REGION, NAME_REGION, crop_region

log = logging.getLogger(__name__)

try:  # optional dependency
    import pytesseract
    try:
        pytesseract.get_tesseract_version()
        AVAILABLE = True
    except Exception:
        AVAILABLE = False
except ImportError:  # pragma: no cover
    pytesseract = None
    AVAILABLE = False


def _prep(crop):
    g = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    g = cv2.resize(g, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
    g = cv2.bilateralFilter(g, 7, 40, 40)
    _, th = cv2.threshold(g, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    if th.mean() < 127:  # want dark text on light background
        th = 255 - th
    return cv2.copyMakeBorder(th, 12, 12, 12, 12, cv2.BORDER_CONSTANT, value=255)


class Ocr:
    def __init__(self, enabled=True, engine=None):
        self.engine = engine  # injectable callable(image, config) -> str for tests
        self.enabled = enabled and (engine is not None or AVAILABLE)

    def _run(self, img, config):
        if self.engine:
            return self.engine(img, config)
        return pytesseract.image_to_string(img, config=config)

    def read_name(self, canon, game="any"):
        if not self.enabled:
            return None
        crop = crop_region(canon, NAME_REGION.get(game, NAME_REGION["any"]))
        try:
            txt = self._run(_prep(crop), "--psm 7")
        except Exception as e:  # pragma: no cover
            log.warning("ocr failed: %s", e)
            return None
        txt = re.sub(r"[^A-Za-z0-9' ,\-]", " ", txt)
        txt = re.sub(r"\s+", " ", txt).strip()
        return txt or None

    def read_collector(self, canon, game="any"):
        if not self.enabled:
            return None
        crop = crop_region(canon, COLLECTOR_REGION.get(game, COLLECTOR_REGION["any"]))
        try:
            txt = self._run(_prep(crop), "--psm 7")
        except Exception:  # pragma: no cover
            return None
        m = re.search(r"(\d{1,4})\s*(?:/\s*\d{1,4})?\s*([A-Z0-9]{2,5})?", txt.upper())
        if not m:
            return None
        return {"number": m.group(1).lstrip("0") or "0", "set": m.group(2) or ""}
