"""Perceptual hashes (pHash via DCT, dHash via gradients) on numpy/OpenCV, with
vectorised Hamming distance over a uint64 array for index lookups."""

import numpy as np
import cv2

HASH_BITS = 64
_POP = np.array([bin(i).count("1") for i in range(256)], dtype=np.uint8)


def _gray(img):
    if img.ndim == 3:
        return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return img


def bits_to_int(bits):
    v = 0
    for b in np.asarray(bits).ravel():
        v = (v << 1) | int(bool(b))
    return v


def phash(img, hash_size=8, highfreq_factor=4):
    g = _gray(img)
    n = hash_size * highfreq_factor
    g = cv2.resize(g, (n, n), interpolation=cv2.INTER_AREA).astype(np.float32)
    dct = cv2.dct(g)
    low = dct[:hash_size, :hash_size]
    med = np.median(low)
    return bits_to_int(low > med)


def dhash(img, hash_size=8):
    g = _gray(img)
    g = cv2.resize(g, (hash_size + 1, hash_size), interpolation=cv2.INTER_AREA).astype(np.int16)
    return bits_to_int(g[:, 1:] > g[:, :-1])


def hamming(a, b):
    return int(a ^ b).bit_count()


def to_signed(v):
    """uint64 -> int64 for SQLite storage."""
    return v - (1 << 64) if v >= (1 << 63) else v


def from_signed(v):
    return v + (1 << 64) if v < 0 else v


def hamming_many(query, arr):
    """Hamming distance between one hash (int) and a uint64 numpy array."""
    if len(arr) == 0:
        return np.zeros(0, dtype=np.int32)
    x = arr ^ np.uint64(query)
    return _POP[x.view(np.uint8).reshape(-1, 8)].sum(axis=1).astype(np.int32)
