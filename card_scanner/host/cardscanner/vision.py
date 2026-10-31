"""Card detection, crop and deskew: contour -> 4-point perspective warp to a
canonical portrait 630x880 image (~10 px/mm for a 63x88 card)."""

import cv2
import numpy as np

CANON_W, CANON_H = 630, 880

# Art-box fractions (x0, y0, x1, y1) of the canonical card, per game.
ART_REGION = {
    "mtg": (0.07, 0.11, 0.93, 0.56),
    "pokemon": (0.08, 0.10, 0.92, 0.48),
    "ygo": (0.12, 0.18, 0.88, 0.63),
    "any": (0.08, 0.10, 0.92, 0.56),
}
# Text line regions for OCR.
NAME_REGION = {
    "mtg": (0.05, 0.04, 0.80, 0.11),
    "pokemon": (0.12, 0.03, 0.75, 0.10),
    "ygo": (0.06, 0.04, 0.80, 0.12),
    "any": (0.05, 0.03, 0.85, 0.12),
}
COLLECTOR_REGION = {
    "mtg": (0.03, 0.91, 0.45, 0.98),
    "pokemon": (0.55, 0.92, 0.98, 0.98),
    "ygo": (0.55, 0.88, 0.98, 0.93),
    "any": (0.03, 0.90, 0.98, 0.98),
}


class CardNotFound(Exception):
    pass


def crop_region(canon, region):
    x0, y0, x1, y1 = region
    h, w = canon.shape[:2]
    return canon[int(y0 * h):int(y1 * h), int(x0 * w):int(x1 * w)]


def art_region(canon, game="any"):
    return crop_region(canon, ART_REGION.get(game, ART_REGION["any"]))


def order_points(pts):
    pts = np.asarray(pts, dtype=np.float32).reshape(4, 2)
    s = pts.sum(axis=1)
    d = np.diff(pts, axis=1).ravel()
    tl = pts[np.argmin(s)]
    br = pts[np.argmax(s)]
    tr = pts[np.argmin(d)]
    bl = pts[np.argmax(d)]
    return np.array([tl, tr, br, bl], dtype=np.float32)


def find_card_quad(img, min_area_frac=0.04):
    """Return the 4 corners (tl, tr, br, bl) of the largest card-like quad."""
    gray = img if img.ndim == 2 else cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blur, 40, 120)
    edges = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=2)
    edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        if blur.std() < 3.0:
            raise CardNotFound("uniform image")
        # fall back to an Otsu threshold (either polarity)
        _, th = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        contours, _ = cv2.findContours(th, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    min_area = min_area_frac * h * w
    max_area = 0.97 * h * w  # the whole frame is not a card
    best = None
    for c in sorted(contours, key=cv2.contourArea, reverse=True):
        area = cv2.contourArea(c)
        if area < min_area:
            break
        if area > max_area:
            continue
        peri = cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, 0.02 * peri, True)
        if len(approx) == 4 and cv2.isContourConvex(approx):
            quad = order_points(approx)
        else:
            rect = cv2.minAreaRect(c)
            quad = order_points(cv2.boxPoints(rect))
        wq = max(np.linalg.norm(quad[1] - quad[0]), np.linalg.norm(quad[2] - quad[3]))
        hq = max(np.linalg.norm(quad[3] - quad[0]), np.linalg.norm(quad[2] - quad[1]))
        if wq < 10 or hq < 10:
            continue
        ratio = min(wq, hq) / max(wq, hq)
        if 0.55 <= ratio <= 0.85:  # 63/88 = 0.716, 59/86 = 0.686
            best = quad
            break
        if best is None:
            best = quad
    if best is None:
        raise CardNotFound("no card-sized contour")
    return best


def warp_card(img, quad, size=(CANON_W, CANON_H)):
    """Perspective-warp the quad to a portrait canonical image."""
    quad = order_points(quad)
    wq = max(np.linalg.norm(quad[1] - quad[0]), np.linalg.norm(quad[2] - quad[3]))
    hq = max(np.linalg.norm(quad[3] - quad[0]), np.linalg.norm(quad[2] - quad[1]))
    if wq > hq:  # landscape in the photo -> rotate 90 deg so it is portrait
        quad = np.array([quad[3], quad[0], quad[1], quad[2]], dtype=np.float32)
    w, h = size
    dst = np.array([[0, 0], [w - 1, 0], [w - 1, h - 1], [0, h - 1]], dtype=np.float32)
    m = cv2.getPerspectiveTransform(quad.astype(np.float32), dst)
    return cv2.warpPerspective(img, m, (w, h), flags=cv2.INTER_AREA)


def extract_card(img):
    """Detect + deskew; returns (canonical BGR image, quad)."""
    quad = find_card_quad(img)
    return warp_card(img, quad), quad


def rotate180(img):
    return cv2.rotate(img, cv2.ROTATE_180)


def to_jpeg(img, quality=88):
    ok, buf = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    if not ok:
        raise RuntimeError("jpeg encode failed")
    return buf.tobytes()
