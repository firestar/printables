"""One 120 mm fan -> ONE Tesla V100 PCIe tail, press-fit sleeve (no foam tape).

Reuses gpu_duct.py with N_CARDS = 1 (no splitter) and a tight sleeve, plus a
fit-test plate: three 12 mm sleeve rings at CLR_TEST clearances, marked with
1 / 2 / 3 notches on the top edge (tightest = 1 notch). Push each over the card
tail, pick the one that grips without forcing, set CLR to it and re-run.

Run: PYTHONPATH=../../.pydeps python3 v100_single.py
"""
import os

import manifold3d as m3d
import numpy as np

import gpu_duct as gd

TAIL_H = 99.0               # measured: cooler height at the card's tail (spec 111.2 is the full card)
TAIL_T = 35.0               # cooler thickness at the tail (estimate, not published)
CLR = 0.3                   # per side, press fit on the tail (set from the fit test)
SLV = 25.0                  # sleeve overlap onto the card (longer = more grip)
CLR_TEST = (0.2, 0.3, 0.4)
RING_H = 12.0


def configure(clr):
    gd.N_CARDS = 1
    gd.CARD_H, gd.CARD_T = TAIL_H, TAIL_T
    gd.CLR = clr
    gd.SLV = SLV
    gd.ENV_X = gd.CARD_T
    gd.ENV_Y = gd.CARD_H
    gd.Z_SLV = gd.Z_SEAT + gd.LIP + gd.CLR
    gd.Z_TOP = gd.Z_SLV + gd.SLV
    gd.CORNER = 0.5         # near-square sleeve corners: card tail corners must not jam


def ring(clr, notches):
    w, h = gd.ENV_X + 2 * clr, gd.ENV_Y + 2 * clr
    inner = gd.rrect(w, h)
    outer = gd.rrect(w + 2 * gd.WALL, h + 2 * gd.WALL, gd.CORNER + gd.WALL)
    r = m3d.Manifold.extrude(outer - inner, RING_H)
    for k in range(notches):
        y = h / 2 - 8 - 5 * k
        r = r - gd.box(w / 2 - 1, w / 2 + gd.WALL + 1, y - 1, y + 1, RING_H - 2, RING_H + 1)
    return r


def fit_plate():
    pitch = gd.ENV_X + 2 * max(CLR_TEST) + 2 * gd.WALL + 8
    rings = [ring(c, k + 1).translate(((k - 1) * pitch, 0, 0)) for k, c in enumerate(CLR_TEST)]
    return gd.union(rings)


def export(name, m):
    tm = gd.to_trimesh(m)
    tm.export(os.path.join(gd.OUT, "stl", f"{name}.stl"))
    fits = max(tm.extents[:2]) <= gd.BED - 2 * gd.BED_MARGIN and tm.extents[2] <= gd.BED - gd.BED_MARGIN
    print(f"  {name:16s} size {np.round(tm.extents, 1)}  {tm.volume / 1000:.0f} cm3  "
          f"watertight={tm.is_watertight} bed {gd.ok(fits)}")


def main():
    configure(CLR)
    duct = gd.make_duct()
    card = gd.make_card(0)
    ov = (duct ^ card).volume()
    print(f"-- V100 single: sleeve {gd.ENV_X + 2 * CLR:.1f} x {gd.ENV_Y + 2 * CLR:.1f} mm "
          f"({CLR} mm/side), {SLV:.0f} mm deep")
    print(f"  card overlap {ov:.3f} mm3, min gap {duct.min_gap(card, 5.0):.2f} -> {gd.ok(ov < 1e-2)}")
    tm = gd.to_trimesh(duct)
    down = (tm.face_normals[:, 2] < -np.cos(np.radians(45)) - 1e-3) & (tm.triangles_center[:, 2] > 0.2)
    print(f"  overhang > 45 deg (excluding bed): {tm.area_faces[down].sum():.1f} mm2")
    os.makedirs(os.path.join(gd.OUT, "stl"), exist_ok=True)
    export("v100_single_duct", duct)
    export("v100_fit_test", fit_plate())


if __name__ == "__main__":
    main()
