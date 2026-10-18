"""120 mm fan -> 2 x NVIDIA Tesla V100 PCIe (passive) duct, one piece, PETG.

  120 x 25 fan (screwed to the FLANGE)
  -> loft: round fan mouth -> rectangle over both card tails
  -> 45 deg seat the card tails butt against
  -> SLEEVE slides SLV mm over both tails (line it with foam tape)
  A SPLITTER on the centre plane halves the air between the two cards and ends
  in the gap between them.

Frame: x across the cards (thickness / slot direction), y card height,
z airflow (fan at z=0, cards above).  Print orientation = model orientation
(flange down, no supports: every wall leans <= 45 deg).
Run: PYTHONPATH=../../.pydeps python3 gpu_duct.py
"""
import json
import math
import os

import numpy as np
import manifold3d as m3d

OUT = os.path.dirname(os.path.abspath(__file__))

# ---- parameters (mm) -------------------------------------------------------
BED = 256.0
BED_MARGIN = 3.0

# cards: Tesla V100 PCIe, full height, dual slot, adjacent slots
CARD_H = 111.2          # tail end height (spec 4.376")
CARD_T = 35.0           # cooler thickness at the tail
PITCH = 40.64           # 2 PCIe slots
N_CARDS = 2
ENV_X = PITCH * (N_CARDS - 1) + CARD_T     # envelope over both tails
ENV_Y = CARD_H

# fan: 120 mm, 105 mm hole square, works for 25 and 38 mm thick fans
FAN = 120.0
FAN_HOLE = 105.0
FAN_R = 57.5            # duct mouth (blade sweep); + WALL stays inside the frame
HUB_R = 20.0
FAN_T = 25.0            # preview only
HOLE_D = 4.5            # clearance for M4 / fan screws
FLANGE_T = 5.0
FLANGE_R = 6.0          # corner radius

WALL = 2.4
LOFT = 100.0            # round -> rectangle transition length
CLR = 1.0               # per side around the tails (fill with ~1.5 mm foam tape)
LIP = 2.0               # seat the tails butt against
SLV = 20.0              # sleeve overlap onto the cards
CORNER = 3.0            # rectangle corner radius
SPLIT_T = 2.0           # splitter thickness (gap between cards is PITCH - CARD_T)
SPLIT_Z0 = FLANGE_T + 8.0   # splitter starts this far above the fan face
GAP_CLR = 0.4           # per side between the gap fin and the card faces
FIN_T = PITCH - CARD_T - 2 * GAP_CLR   # fin that blocks the gap between the cards

Z_SEAT = FLANGE_T + LOFT                    # seat bottom
Z_SLV = Z_SEAT + LIP + CLR                  # sleeve starts (45 deg seat)
Z_TOP = Z_SLV + SLV


# ---- helpers ---------------------------------------------------------------
def box(x0, x1, y0, y1, z0, z1):
    return m3d.Manifold.cube((x1 - x0, y1 - y0, z1 - z0)).translate((x0, y0, z0))


def union(parts):
    return m3d.Manifold.batch_boolean(list(parts), m3d.OpType.Add)


def rrect(w, h, r=CORNER):
    r = max(min(r, w / 2 - 0.01, h / 2 - 0.01), 0.01)
    sq = m3d.CrossSection.square((w - 2 * r, h - 2 * r), center=True)
    return sq.offset(r, m3d.JoinType.Round, circular_segments=48)


def circle(r):
    return m3d.CrossSection.circle(r, 192)


def slab(cs, z):
    return m3d.Manifold.extrude(cs, 1e-3).translate((0, 0, z))


def loft(stations):
    """Ruled loft through convex sections [(cs, z), ...] by pairwise hulls."""
    out = []
    for (a, za), (b, zb) in zip(stations, stations[1:]):
        if zb > za:
            out.append(m3d.Manifold.batch_hull([slab(a, za), slab(b, zb - 1e-3)]))
    return union(out)


def clean(m):
    return m3d.Manifold.compose([c for c in m.decompose() if c.volume() > 1.0])


def card_x(k):
    return (k - (N_CARDS - 1) / 2) * PITCH


# ---- duct ------------------------------------------------------------------
def make_duct():
    seat_in = rrect(ENV_X - 2 * LIP, ENV_Y - 2 * LIP)
    slv_in = rrect(ENV_X + 2 * CLR, ENV_Y + 2 * CLR)
    slv_out = rrect(ENV_X + 2 * (CLR + WALL), ENV_Y + 2 * (CLR + WALL), CORNER + WALL)
    outer = loft([(circle(FAN_R + WALL), FLANGE_T - 0.5), (slv_out, Z_SEAT),
                  (slv_out, Z_TOP)])
    inner = loft([(circle(FAN_R), -1), (circle(FAN_R), FLANGE_T), (seat_in, Z_SEAT),
                  (slv_in, Z_SLV), (slv_in, Z_TOP + 1)])
    fl = m3d.Manifold.extrude(rrect(FAN, FAN, FLANGE_R), FLANGE_T)
    d = (outer + fl) - inner
    h = FAN_HOLE / 2
    for sx in (-1, 1):
        for sy in (-1, 1):
            d = d - m3d.Manifold.cylinder(FLANGE_T + 2, HOLE_D / 2, HOLE_D / 2, 32) \
                .translate((sx * h, sy * h, -1))
    # splitter between the cards: knife edge down (45 deg, no bridge), widens
    # at 45 deg into a fin that fills the gap between the two cards for the
    # whole sleeve depth, so air can't bypass the heatsinks through the gap
    t, tf = SPLIT_T / 2, FIN_T / 2
    zw = Z_SLV - (tf - t)
    cs = m3d.CrossSection([[(0, SPLIT_Z0), (t, SPLIT_Z0 + t), (t, zw), (tf, Z_SLV),
                            (tf, Z_TOP), (-tf, Z_TOP), (-tf, Z_SLV), (-t, zw),
                            (-t, SPLIT_Z0 + t)]])
    sp = m3d.Manifold.extrude(cs, 2 * FAN).translate((0, 0, -FAN)).rotate((90, 0, 0))
    sp = sp ^ outer
    return clean(d + sp)


# ---- context (preview only) -------------------------------------------------
def make_card(k, length=180.0):
    z0 = Z_SEAT + LIP + 1.0                # tail corners land on the rounded seat
    x = card_x(k)
    shell = box(x - CARD_T / 2, x + CARD_T / 2, -CARD_H / 2, CARD_H / 2, z0, z0 + length)
    z0 = Z_SEAT + LIP + 1.0                # tail corners land on the rounded seat
    hole = box(x - CARD_T / 2 + 1.5, x + CARD_T / 2 - 1.5, -CARD_H / 2 + 1.5,
               CARD_H / 2 - 1.5, z0 - 1, z0 + length - 1.5)
    fins = union(box(x - CARD_T / 2 + 1.5, x + CARD_T / 2 - 1.5, y - 0.2, y + 0.2,
                     z0 + 15, z0 + length - 1.5)
                 for y in np.arange(-CARD_H / 2 + 5, CARD_H / 2 - 4, 3.0))
    return shell - hole + fins


def make_fan():
    frame = m3d.Manifold.extrude(rrect(FAN, FAN, 4.0), FAN_T) - \
        m3d.Manifold.cylinder(FAN_T + 2, FAN_R, FAN_R, 128).translate((0, 0, -1))
    hub = m3d.Manifold.cylinder(FAN_T, HUB_R, HUB_R, 64)
    blades = union(box(HUB_R - 1, FAN_R - 1, -1, 1, 3, FAN_T - 3).rotate((0, 0, a))
                   for a in range(0, 360, 40))
    h = FAN_HOLE / 2
    f = frame + hub + blades
    for sx in (-1, 1):
        for sy in (-1, 1):
            f = f - m3d.Manifold.cylinder(FAN_T + 2, 2.2, 2.2, 24).translate((sx * h, sy * h, -1))
    return f.translate((0, 0, -FAN_T))


# ---- checks / export ---------------------------------------------------------
def to_trimesh(m):
    import trimesh
    mesh = m.to_mesh()
    return trimesh.Trimesh(np.asarray(mesh.vert_properties)[:, :3],
                           np.asarray(mesh.tri_verts), process=False)


def ok(flag):
    return "OK" if flag else "FAIL"


def report(duct, cards):
    fan_a = math.pi * (FAN_R ** 2 - HUB_R ** 2)
    seat_a = rrect(ENV_X - 2 * LIP, ENV_Y - 2 * LIP).area() - SPLIT_T * (ENV_Y - 2 * LIP)
    print("-- geometry")
    print(f"  card envelope {ENV_X:.1f} x {ENV_Y:.1f} mm ({N_CARDS} x {CARD_T} mm @ {PITCH} pitch)")
    print(f"  flow area: fan annulus {fan_a / 100:.0f} cm2, seat {seat_a / 100:.0f} cm2 "
          f"({100 * seat_a / fan_a:.0f} %), split {N_CARDS} ways")
    print("-- fit")
    for k, c in enumerate(cards):
        ov = (duct ^ c).volume()
        g = duct.min_gap(c, 5.0)
        print(f"  card {k + 1}: overlap {ov:.3f} mm3, min gap {g:.2f} -> {ok(ov < 1e-2)}")
    print(f"  gap fin {FIN_T:.2f} mm in the {PITCH - CARD_T:.2f} mm card gap, "
          f"{SLV + LIP + CLR:.0f} mm deep -> {ok(FIN_T > 1.6)}")
    tm = to_trimesh(duct)
    n = tm.face_normals
    down = (n[:, 2] < -math.cos(math.radians(45)) - 1e-3) & (tm.triangles_center[:, 2] > 0.2)
    print(f"  overhang > 45 deg (excluding bed): {tm.area_faces[down].sum():.1f} mm2")


def export(duct, preview):
    print("-- STL export")
    os.makedirs(os.path.join(OUT, "stl"), exist_ok=True)
    os.makedirs(os.path.join(OUT, "preview"), exist_ok=True)
    tm = to_trimesh(duct)
    tm.export(os.path.join(OUT, "stl", "duct.stl"))
    fits = max(tm.extents[:2]) <= BED - 2 * BED_MARGIN and tm.extents[2] <= BED - BED_MARGIN
    print(f"  duct  flange down  size {np.round(tm.extents, 1)}  {tm.volume / 1000:.0f} cm3  "
          f"watertight={tm.is_watertight} bed {ok(fits)}")
    entries = []
    for name, (m, color, lvl, ctx) in preview.items():
        to_trimesh(m).export(os.path.join(OUT, "preview", f"{name}.stl"))
        entries.append({"name": name, "file": f"preview/{name}.stl", "color": color,
                        "lvl": lvl, "ctx": ctx})
    with open(os.path.join(OUT, "preview", "manifest.json"), "w") as fh:
        json.dump({"title": f"120 mm fan -> {N_CARDS} x Tesla V100 PCIe duct", "parts": entries},
                  fh, indent=1)


def main():
    duct = make_duct()
    cards = [make_card(k) for k in range(N_CARDS)]
    report(duct, cards)
    preview = {"duct": (duct, "#4a7fb5", 0, False), "fan": (make_fan(), "#333333", -1, True)}
    for k, c in enumerate(cards):
        preview[f"v100_{k + 1}"] = (c, "#b9a66b", 1, True)
    export(duct, preview)


if __name__ == "__main__":
    main()
