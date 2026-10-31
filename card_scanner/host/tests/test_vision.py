import numpy as np
import pytest

from cardscanner import hashing, vision
from cardscanner.synthetic import photograph, render_card


@pytest.mark.parametrize("angle", [0.0, 4.0, -9.0, 15.0])
def test_crop_deskew_recovers_card(angle):
    card = render_card("Ember Drake", "mtg", "001")
    photo = photograph(card, bg_size=(1280, 960), angle_deg=angle, scale=0.78)
    canon, quad = vision.extract_card(photo)
    assert canon.shape == (vision.CANON_H, vision.CANON_W, 3)
    # the deskewed result should hash very close to the original render
    d = hashing.hamming(hashing.phash(canon), hashing.phash(card))
    assert d <= 8, "phash distance %d too large at %.0f deg" % (d, angle)
    d_art = hashing.hamming(hashing.phash(vision.art_region(canon, "mtg")), hashing.phash(vision.art_region(card, "mtg")))
    assert d_art <= 10


def test_landscape_photo_is_rotated_to_portrait():
    card = render_card("Tidal Sprite", "mtg", "004")
    photo = photograph(card, bg_size=(1280, 960), angle_deg=90.0, scale=0.6)
    canon, _ = vision.extract_card(photo)
    assert canon.shape[0] > canon.shape[1]
    d = min(hashing.hamming(hashing.phash(canon), hashing.phash(card)),
            hashing.hamming(hashing.phash(vision.rotate180(canon)), hashing.phash(card)))
    assert d <= 8


def test_ygo_size_card_is_found():
    # 59x86 -> slightly different aspect, still inside the accepted ratio band
    card = render_card("Chrono Wyrm", "ygo", "001", w=590, h=860)
    photo = photograph(card, angle_deg=-3.0, scale=0.7)
    canon, quad = vision.extract_card(photo)
    assert canon.shape[:2] == (vision.CANON_H, vision.CANON_W)
    assert quad.shape == (4, 2)


def test_blank_image_raises():
    blank = np.full((480, 640, 3), 230, np.uint8)
    with pytest.raises(vision.CardNotFound):
        vision.extract_card(blank)


def test_hash_helpers():
    a = 0b1011
    arr = np.array([a, a ^ 0b1, 0], dtype=np.uint64)
    assert hashing.hamming_many(a, arr).tolist() == [0, 1, 3]
    big = (1 << 63) | 5
    assert hashing.from_signed(hashing.to_signed(big)) == big
