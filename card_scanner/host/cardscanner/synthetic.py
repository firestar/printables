"""Synthetic cards + camera photos for tests and the no-hardware demo."""

import hashlib
import random

import cv2
import numpy as np

from .vision import CANON_H, CANON_W, ART_REGION

FRAME = {"mtg": (20, 20, 20), "pokemon": (40, 170, 230), "ygo": (70, 90, 140)}
BACK = {"mtg": (40, 70, 110), "pokemon": (170, 90, 30), "ygo": (70, 50, 90)}


def _seed(name):
    return int(hashlib.sha1(name.encode()).hexdigest()[:8], 16)


def render_card(name, game="mtg", collector="001", set_code="SYN", w=CANON_W, h=CANON_H, seed=None):
    """Draw a deterministic fake card: frame, art box with shapes, name + number."""
    rng = random.Random(_seed(name) if seed is None else seed)
    img = np.full((h, w, 3), FRAME.get(game, (30, 30, 30)), np.uint8)
    inner = (rng.randint(150, 240), rng.randint(150, 240), rng.randint(150, 240))
    cv2.rectangle(img, (int(0.04 * w), int(0.03 * h)), (int(0.96 * w), int(0.97 * h)), inner, -1)
    x0, y0, x1, y1 = ART_REGION[game]
    ax0, ay0, ax1, ay1 = int(x0 * w), int(y0 * h), int(x1 * w), int(y1 * h)
    art_bg = (rng.randint(0, 255), rng.randint(0, 255), rng.randint(0, 255))
    cv2.rectangle(img, (ax0, ay0), (ax1, ay1), art_bg, -1)
    for _ in range(rng.randint(6, 14)):
        col = (rng.randint(0, 255), rng.randint(0, 255), rng.randint(0, 255))
        kind = rng.random()
        cx, cy = rng.randint(ax0, ax1), rng.randint(ay0, ay1)
        if kind < 0.4:
            cv2.circle(img, (cx, cy), rng.randint(20, 120), col, -1)
        elif kind < 0.8:
            x2, y2 = rng.randint(ax0, ax1), rng.randint(ay0, ay1)
            cv2.rectangle(img, (cx, cy), (x2, y2), col, -1)
        else:
            pts = np.array([[rng.randint(ax0, ax1), rng.randint(ay0, ay1)] for _ in range(3)])
            cv2.fillPoly(img, [pts], col)
    img[ay0:ay1, ax0:ax1] = cv2.GaussianBlur(img[ay0:ay1, ax0:ax1], (0, 0), 1.5)
    scale = w / 630.0
    cv2.putText(img, name, (int(0.07 * w), int(0.085 * h)), cv2.FONT_HERSHEY_SIMPLEX, 1.1 * scale, (10, 10, 10), 2)
    body_y = int(0.62 * h)
    for i in range(4):
        cv2.line(img, (int(0.1 * w), body_y + i * int(0.05 * h)), (int(0.9 * w), body_y + i * int(0.05 * h)),
                 (90, 90, 90), 2)
    cv2.putText(img, "%s %s" % (collector, set_code), (int(0.06 * w), int(0.96 * h)), cv2.FONT_HERSHEY_SIMPLEX,
                0.8 * scale, (10, 10, 10), 2)
    return img


def render_back(game="mtg", w=CANON_W, h=CANON_H):
    rng = random.Random(_seed("back-" + game))
    img = np.full((h, w, 3), BACK.get(game, (60, 60, 60)), np.uint8)
    cv2.ellipse(img, (w // 2, h // 2), (int(0.35 * w), int(0.3 * h)), 0, 0, 360, (200, 180, 120), -1)
    for _ in range(12):
        col = (rng.randint(0, 255), rng.randint(0, 255), rng.randint(0, 255))
        cv2.circle(img, (rng.randint(0, w), rng.randint(0, h)), rng.randint(10, 60), col, 3)
    cv2.putText(img, game.upper(), (int(0.25 * w), int(0.53 * h)), cv2.FONT_HERSHEY_DUPLEX, 2.2, (30, 30, 30), 4)
    return img


def photograph(card, bg_size=(1280, 960), angle_deg=0.0, scale=0.8, bg_color=(235, 235, 235), noise=4,
               offset=(0, 0), blur=0.6):
    """Place a canonical card onto a background as a camera would see it
    (rotated, scaled, slightly blurred).  Returns BGR image."""
    bw, bh = bg_size
    out = np.full((bh, bw, 3), bg_color, np.uint8)
    ch, cw = card.shape[:2]
    target_h = bh * scale
    s = target_h / ch
    src = np.array([[0, 0], [cw, 0], [cw, ch], [0, ch]], dtype=np.float32)
    a = np.deg2rad(angle_deg)
    rot = np.array([[np.cos(a), -np.sin(a)], [np.sin(a), np.cos(a)]], dtype=np.float32)
    centred = (src - [cw / 2, ch / 2]) * s
    dst = centred @ rot.T + [bw / 2 + offset[0], bh / 2 + offset[1]]
    m = cv2.getPerspectiveTransform(src, dst.astype(np.float32))
    warped = cv2.warpPerspective(card, m, (bw, bh), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_TRANSPARENT,
                                 dst=out.copy())
    out = warped
    if blur:
        out = cv2.GaussianBlur(out, (0, 0), blur)
    if noise:
        n = np.random.default_rng(_seed("noise") % 1000).normal(0, noise, out.shape)
        out = np.clip(out.astype(np.int16) + n.astype(np.int16), 0, 255).astype(np.uint8)
    return out


def demo_catalog():
    """A small fixed set of fake cards for tests and the demo index."""
    cards = []
    names = {
        "mtg": [("Ember Drake", "rare", 4.25), ("Mossback Turtle", "common", 0.12), ("Starfall Oracle", "mythic", 18.0),
                ("Tidal Sprite", "common", 0.08), ("Iron Golem", "uncommon", 0.5)],
        "pokemon": [("Pyrokit", "rare", 3.1), ("Leafling", "common", 0.1), ("Voltmouse", "uncommon", 0.35),
                    ("Aquafin", "common", 0.15)],
        "ygo": [("Chrono Wyrm", "rare", 2.4), ("Pebble Knight", "common", 0.05), ("Mirror Mage", "uncommon", 0.4)],
    }
    for game, lst in names.items():
        for i, (name, rarity, usd) in enumerate(lst, 1):
            cards.append({"id": "%s-%03d" % (game, i), "game": game, "name": name, "set_code": "SYN",
                          "set_name": "Synthetic Set", "collector_number": "%03d" % i, "rarity": rarity,
                          "usd": usd, "usd_foil": round(usd * 2.5, 2), "finishes": ["nonfoil", "foil"]})
    return cards
