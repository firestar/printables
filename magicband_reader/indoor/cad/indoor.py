"""Indoor variants of the MagicBand reader (PETG / PLA, no gaskets).

Reuses the outdoor design in ../../cad/magicband.py: the parts whose geometry
does not depend on the gasket gaps are built with the outdoor parameters (their
STLs are identical to ../../cad/stl/), then the module parameters are switched
to the indoor set (GASKET_GAP = 0, halo shoulder up to the collar seat, pod cap
1 mm taller) and the changed parts are rebuilt.

    head  : ball + face stack + neck (same as outdoors, gaps closed)
    arm   : fp    = arm_base + pod_cap_in (R503)
            blank = arm_base + pod_cap_blank (oval recess, no sensor)
            ball  = no arm: ball_riser (the arm's neck boss on its own)
    mount : wall  = wall_bracket_in (outdoor bracket, no gasket gap)
            table = table_base (hollow, ballast pockets) + table_floor
            post  = post_base + post_floor + 3 post_collar + 4 post_sleeve
                    + post_saddle on a 1" EMT pipe core
    tray  : split = electronics_tray (outdoor), aio = electronics_tray_aio
            (side fins) + aio_deck carrying a 1-ch relay + 6-way 5.08 terminal

Every mount carries the same ARM SEAT: 4 x M3 from below at (XB +-19, YC +-12)
into the inserts under arm_base / ball_riser, cable hole at (XB, YC).  So arm
and ball-only fit every mount; ball-only puts the ball centre over the seat.

Frames: the head frame (H) is the outdoor world frame (arm underside z = 0,
neck axis x = 0, y = YC).  Mount worlds: wall = H (wall plane y = 0); table =
table top z = 0, head at z = TB_H; post = floor z = 0, pipe axis (XB, YC),
head at z = ZS.  Ball-only shifts the ball parts by +XB in x.

Run: PYTHONPATH=../../../.pydeps python3 indoor.py
"""
import json
import math
import os
import sys

import numpy as np
import manifold3d as m3d

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..", "..", "cad")))
import magicband as mb  # noqa: E402
from magicband import (box, union, clean, zcyl, zcone, ycyl, xform, poly, to_trimesh,  # noqa: E402
                       bed_fit, overhang_area, ok, bbox, bbox_hit, orient)

OUT = HERE
G_OUT = mb.GASKET_GAP
YC_OUT = mb.YC

# ---- indoor parameters (mm, g/cm3) -------------------------------------------
PIPE = "emt"                       # "emt" (1" EMT steel) or "pvc" (32 mm PVC)
PIPES = {"emt": (29.5, 1.45, 7.85), "pvc": (32.0, 2.4, 1.40)}   # OD, wall, density
PIPE_OD, PIPE_WALL, PIPE_RHO = PIPES[PIPE]
PIPE_CLR = 0.3                     # radial clearance pipe -> printed bores
FACE_H = 1050.0                    # post: face (ball) centre above the floor
SLEEVE_MAX = 245.0                 # max printed sleeve segment height

RHO = 1.25                         # PETG / PLA
T_SKIN = 1.2                       # walls / top / bottom skin per side (3 x 0.4)
INFILL = 0.15
BALLAST = {"sand": 1.6, "steel": 4.5}   # bulk densities (dry sand, stacked washers / shot)
BALLAST_USE = {"table": "sand", "post": "sand"}
MIN_TIP = 10.0

# table base (centred under the arm seat)
TB_HX, TB_HY, TB_R, TB_H = 120.0, 72.0, 30.0, 26.0
TB_TOP, TB_RIM, TB_FLOOR = 5.0, 3.0, 3.0
TB_BEV = 6.0                       # top edge bevel, 40 deg from vertical
TB_PADS = [(-100.0, -50.0), (100.0, -50.0), (100.0, 50.0), (-100.0, 50.0)]
TB_BAY = (30.0, 22.0)              # service bay half sizes (seat screws, cable)
DUCT_HW = 6.5                      # cable duct half width (inside)

# post
PB_R, PB_H, PB_TOP, PB_RIM, PB_FLOOR = 124.0, 50.0, 5.0, 3.0, 3.0
PB_BEV = 12.0
PB_TUBE = 22.0
PB_STOP = 24.0                     # top of the 35 deg pipe-stop cone
PB_RIBS = (0.0, 45.0, 90.0, 135.0, 180.0, 225.0, 315.0)   # 270 = cable duct (back)
PB_PADS = [(106.0, a) for a in (0.0, 60.0, 120.0, 180.0, 240.0, 300.0)]
PB_BOSSES = [(60.0, a) for a in (45.0, 135.0, 225.0, 315.0)] + [(106.0, 90.0)]
PB_ANCHORS = [(95.0, a) for a in (22.5, 157.5, 292.5)]
COL_AF, COL_H, COL_BEV = 100.0, 35.0, 5.0
SL_R, SL_T = 38.0, 2.4
SAD_H, SAD_AF0, SAD_AF1, SAD_PLATE = 45.0, 78.0, 62.0, 10.0

# AIO electronics (ball frame)
DECK_Z = -12.0                     # deck underside = fin tops
DECK_T = 3.0
FIN_X = 47.5
FIN_BOSSES = [(sx * FIN_X, y) for sx in (-1, 1) for y in (-14.0, 14.0)]
AIO_BOARDS = {                     # x0, x1, y0, y1, height on the deck
    "relay": (-42.0, 8.0, -28.0, -2.0, 19.0),        # 1-ch 5 V relay module 50 x 26 x 19
    "terminal": (12.0, 44.0, -29.0, -19.0, 13.0),    # 6-way 5.08 mm screw terminal on a strip
}

# electronics masses (g) for the tip-over check
E_MASS = {"pn532": 8, "speaker": 25, "led_strip": 12, "esp32s3": 4, "max98357a": 2, "buck": 5,
          "max3485": 3, "buck3v3": 2, "protect": 6, "tamper_switch": 3, "r503": 12, "relay": 18,
          "terminal": 10}
E_WIRING = 70.0                    # wiring, screws, inserts in the head (at the ball centre)

ARMS = ("fp", "blank", "ball")
MOUNTS = ("wall", "table", "post")
MODES = ("split", "aio")


# ---- indoor parameter switch --------------------------------------------------
def set_indoor():
    """Gaskets gone: every gasket gap closes, the halo shoulder seats on the
    collar, the pod cap grows by the old gap.  WALL_GAP +1 keeps YC (so the
    arm, bracket screws and pod stay where they were)."""
    mb.GASKET_GAP = mb.G = 0.0
    mb.WALL_GAP = mb.WALL_GAP + G_OUT
    mb.YC = mb.WALL_GAP + mb.HATCH_T + mb.GASKET_GAP - mb.REAR_Y
    assert abs(mb.YC - YC_OUT) < 1e-9
    mb.ZN0 = mb.Z_BOSS
    mb.ZF = mb.ZN0 + mb.NECK_H
    mb.ZC = mb.ZF + mb.FLAT_D
    mb.HALO_SH = mb.SEAT_Y
    mb.CAP_H = -mb.POD_RIM            # rim stays at -15 -> cap 15 thick


# ---- helpers -------------------------------------------------------------------
def zrot(m, deg, cx=0.0, cy=0.0):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return xform(m, [[c, -s, 0, cx], [s, c, 0, cy], [0, 0, 1, 0]])


def polar_at(r, deg, cx, cy):
    return cx + r * math.cos(math.radians(deg)), cy + r * math.sin(math.radians(deg))


def rr_cs(hx, hy, r, cx, cy):
    return m3d.CrossSection.square((2 * (hx - r), 2 * (hy - r))).translate(
        (cx - (hx - r), cy - (hy - r))).offset(r, m3d.JoinType.Round, circular_segments=96)


def oct_cs(af):
    rc = af / 2 / math.cos(math.radians(22.5))
    return poly([(rc * math.cos(math.radians(22.5 + 45 * k)), rc * math.sin(math.radians(22.5 + 45 * k)))
                 for k in range(8)])


def bevel_body(cs_fn, h, bev, inset=0.0, z0=0.0):
    """Footprint cs_fn(inset) from z0 to h, top edge bevelled inward by bev at
    40 deg from vertical (prints top-down without support)."""
    bh = bev / math.tan(math.radians(40.0))
    t = 0.01
    lower = m3d.Manifold.extrude(cs_fn(inset), h - bh - z0).translate((0, 0, z0))
    a = m3d.Manifold.extrude(cs_fn(inset), t).translate((0, 0, h - bh - t))
    b = m3d.Manifold.extrude(cs_fn(inset + bev), t).translate((0, 0, h - t))
    return lower + m3d.Manifold.batch_hull([a, b])


def keep_below(m, z):
    return m.trim_by_plane((0, 0, -1), -z)


def tear_x_down(r, y, z, x0, x1):
    """Hole along x, roof toward -z (for parts printed top-down)."""
    m = m3d.Manifold.extrude(mb.teardrop_cs(r), x1 - x0)
    return xform(m, [[0, 0, 1, x0], [-1, 0, 0, y], [0, -1, 0, z]])


def pockets(x0, x1, y0, y1, z):
    return box(x0 - 1.6, x1 + 1.6, y0 - 1.6, y1 + 1.6, z, z + 2.5) - box(x0 - 0.3, x1 + 0.3, y0 - 0.3, y1 + 0.3,
                                                                          z - 1, z + 3)


# ---- head (indoor changes) ------------------------------------------------------
def make_rear_hatch_in():
    """Hatch seats directly on the ball_rear lugs; its face closes the tamper switch."""
    y1 = mb.REAR_Y
    m = ycyl(67.0, y1 - mb.HATCH_T, y1)
    return m - union(mb.at_ang(ycyl(1.7, y1 - mb.HATCH_T - 1, y1 + 1, x=mb.R_SCREW), a) for a in mb.HATCH_ANG)


def make_pod_cap_blank():
    """Solid sloped cap, same oval finger recess (flat floor), no sensor.
    Prints TOP UP (rim plane on the bed), located by the 3 cap screws."""
    P = (mb.POD_X, mb.YC)
    m = mb.pod_slab(zcyl(mb.R_POD, 0, 200, *P), -mb.CAP_H, 0.0)
    fa, fb, fd = mb.FUNNEL
    top = fd + 0.5
    sa = (14.2 + (fa - 14.2) * top / fd) / 14.2
    sb = (14.2 + (fb - 14.2) * top / fd) / 14.2
    funnel = m3d.Manifold.extrude(m3d.CrossSection.circle(14.2, mb.SEG), top, 0, 0.0, (sa, sb)).translate((0, 0, -fd))
    cuts = [mb.to_pod(funnel)]
    for d in mb.POD_SCREW_ANG:
        cuts.append(mb.to_pod(zcyl(1.7, -mb.CAP_H - 1, 1.0, *mb.pod_screw_ab(d), seg=32)))
    return m - union(cuts)


def make_riser():
    """Ball-only adapter: the arm's neck boss on its own, seat inserts underneath."""
    x, y = mb.XB, mb.YC
    zb = mb.Z_BOSS
    m = union([zcyl(31.0, 0, 6, x, y), zcone(31.0, mb.R_BOSS, 6, 11, x, y), zcyl(mb.R_BOSS, 11, zb - 3, x, y),
               zcone(mb.R_BOSS, mb.R_BOSS - 3, zb - 3, zb, x, y)])
    cuts = [zcyl(11.0, -1, zb + 1, x, y)]
    for sx, sy in mb.NECK_BOT_SCREWS:
        cuts += [zcyl(3.0, -1, zb - 8, x + sx, y + sy),
                 zcone(3.0, 1.7, zb - 8, zb - 8 + 1.3 * 1.2, x + sx, y + sy),
                 zcyl(1.7, zb - 8, zb + 1, x + sx, y + sy)]
    for bx, by in mb.BRACKET_SCREWS:
        cuts += [zcyl(mb.INSERT_R, -1, 6, bx, by), zcone(mb.INSERT_R, 0.05, 6, 6 + 2.4, bx, by)]
    return m - union(cuts)


def make_tray_aio():
    """Outdoor tray + plate wings + two fins with insert bosses carrying the deck."""
    t = mb.make_tray()
    z0, z1 = mb.TRAY_Z - 3, DECK_Z
    parts = [t]
    for sx in (-1, 1):
        parts.append(box(*sorted((sx * 42.0, sx * 51.5)), -24.0, 18.0, z0, mb.TRAY_Z))
        parts.append(box(*sorted((sx * (FIN_X - 1.5), sx * (FIN_X + 1.5))), -24.0, 18.0, z0, z1))
    for x, y in FIN_BOSSES:
        parts.append(zcyl(4.0, z0, z1, x, y, seg=48))
    m = union(parts)
    return m - union(zcyl(mb.INSERT_R, z1 - 6, z1 + 1, x, y, seg=32) for x, y in FIN_BOSSES)


def make_deck():
    z = DECK_Z + DECK_T
    m = box(-51.5, 51.5, -31.5, 18.0, DECK_Z, z)
    m = m + union(pockets(x0, x1, y0, y1, z) for x0, x1, y0, y1, _ in AIO_BOARDS.values())
    cuts = [zcyl(1.7, DECK_Z - 1, z + 1, x, y, seg=32) for x, y in FIN_BOSSES]
    cuts += [box(-20.0, 20.0, 4.0, 14.0, DECK_Z - 1, z + 1), box(18.0, 40.0, -14.0, -2.0, DECK_Z - 1, z + 1)]
    return m - union(cuts)


# ---- table base (table world: table top z = 0, centred on the arm seat) ---------
def tb_cs(i):
    return rr_cs(TB_HX - i, TB_HY - i, TB_R - i, mb.XB, mb.YC)


def tb_features():
    """Solid internal features (ribs, bay walls + bay, duct walls + duct, bosses)."""
    cx, cy = mb.XB, mb.YC
    zt = TB_H - TB_TOP + 0.01
    bx, by = TB_BAY
    t = 2.4
    walls = [box(cx - bx, cx + bx, cy - by, cy + by, TB_FLOOR, zt)]                 # bay (filled)
    walls.append(box(cx - DUCT_HW - t, cx + DUCT_HW + t, cy - TB_HY + 1, cy - by + 1, TB_FLOOR, zt))
    for x in (-90.0, -55.0, 55.0, 90.0):
        walls.append(box(cx + x - t / 2, cx + x + t / 2, cy - TB_HY + 1, cy + TB_HY - 1, TB_FLOOR, zt))
    for sx in (-1, 1):
        walls.append(box(*sorted((cx + sx * (TB_HX - 1), cx + sx * bx)), cy - t / 2, cy + t / 2, TB_FLOOR, zt))
    walls.append(box(cx - t / 2, cx + t / 2, cy + by, cy + TB_HY - 1, TB_FLOOR, zt))
    for x, y in tb_boss_xy():
        walls.append(zcyl(4.5, TB_FLOOR, zt, x, y, seg=48))
    return union(walls)


def tb_boss_xy():
    cx, cy = mb.XB, mb.YC
    bx, by = TB_BAY
    return [(cx + x, cy) for x in (-90.0, -55.0, 55.0, 90.0)] + [(cx - bx, cy + by), (cx + bx, cy + by)]


def make_table_base():
    cx, cy = mb.XB, mb.YC
    bx, by = TB_BAY
    t = 2.4
    outer = bevel_body(tb_cs, TB_H, TB_BEV)
    cav = keep_below(bevel_body(tb_cs, TB_H, TB_BEV, inset=TB_RIM, z0=-1.0), TB_H - TB_TOP)
    body = (outer - cav) ^ outer
    feats = tb_features()
    hollow = [box(cx - bx + t, cx + bx - t, cy - by + t, cy + by - t, TB_FLOOR - 1, TB_H - TB_TOP),
              box(cx - DUCT_HW, cx + DUCT_HW, cy - TB_HY - 1, cy - by + t + 0.5, TB_FLOOR - 1, TB_H - TB_TOP)]
    m = body + (feats - union(hollow))
    m = m ^ outer
    cuts = [zcyl(mb.BORE_R, TB_H - TB_TOP - 1, TB_H + 1, cx, cy),
            box(cx - DUCT_HW, cx + DUCT_HW, cy - TB_HY - 1, cy - TB_HY + TB_RIM + 1, -1, 15.0)]
    cuts += [zcyl(1.7, TB_H - TB_TOP - 1, TB_H + 1, x, y, seg=32) for x, y in mb.BRACKET_SCREWS]
    cuts += [zcyl(mb.INSERT_R, TB_FLOOR - 1, TB_FLOOR + 6, x, y, seg=32) for x, y in tb_boss_xy()]
    return m - union(cuts)


def make_table_floor():
    cx, cy = mb.XB, mb.YC
    m = m3d.Manifold.extrude(tb_cs(TB_RIM + 0.3), TB_FLOOR)
    cuts = []
    for x, y in tb_boss_xy():
        cuts += [zcyl(1.7, -1, TB_FLOOR + 1, x, y, seg=32), zcone(3.6, 1.7, -0.01, 1.9, x, y, seg=32)]
    for px, py in TB_PADS:
        cuts.append(zcyl(12.5, -1, 1.2, cx + px, cy + py, seg=64))
    return m - union(cuts)


def table_ballast(base):
    cx, cy = mb.XB, mb.YC
    inner = keep_below(bevel_body(tb_cs, TB_H, TB_BEV, inset=TB_RIM, z0=TB_FLOOR), TB_H - TB_TOP)
    return clean(inner - tb_features() - base)


# ---- post (post world: floor z = 0, pipe axis (XB, YC)) -------------------------
def pb_cs(i):
    return m3d.CrossSection.circle(PB_R - i, 192).translate((mb.XB, mb.YC))


R_SOCK = PIPE_OD / 2 + PIPE_CLR
CONE_A = math.tan(math.radians(35.0))
R_BELOW = 12.0
Z_PIPE0 = PB_STOP - PIPE_CLR / CONE_A          # pipe end bears on the stop cone


def pb_features():
    cx, cy = mb.XB, mb.YC
    zt = PB_H - PB_TOP + 0.01
    t = 2.4
    f = [zcyl(PB_TUBE, PB_FLOOR, PB_H, cx, cy)]
    for a in PB_RIBS:
        f.append(zrot(box(PB_TUBE - 1, PB_R - PB_RIM + 1, -t / 2, t / 2, PB_FLOOR, zt), a, cx, cy))
    f.append(box(cx - DUCT_HW - t, cx + DUCT_HW + t, cy - PB_R + 1, cy - PB_TUBE + 1, PB_FLOOR, zt))
    for r, a in PB_BOSSES:
        f.append(zcyl(4.5, PB_FLOOR, zt, *polar_at(r, a, cx, cy), seg=48))
    for r, a in PB_ANCHORS:
        f.append(zcyl(5.5, PB_FLOOR, zt, *polar_at(r, a, cx, cy), seg=48))
    return union(f)


def make_post_base():
    cx, cy = mb.XB, mb.YC
    outer = bevel_body(pb_cs, PB_H, PB_BEV)
    cav = keep_below(bevel_body(pb_cs, PB_H, PB_BEV, inset=PB_RIM, z0=-1.0), PB_H - PB_TOP)
    m = (outer - cav) + (pb_features() - box(cx - DUCT_HW, cx + DUCT_HW, cy - PB_R - 1, cy - PB_TUBE + 1,
                                              PB_FLOOR - 1, PB_H - PB_TOP))
    m = m ^ outer
    zc0 = PB_STOP - (R_SOCK - R_BELOW) / CONE_A
    cuts = [zcyl(R_SOCK, PB_STOP, PB_H + 1, cx, cy), zcone(R_BELOW, R_SOCK, zc0, PB_STOP, cx, cy),
            zcyl(R_BELOW, -1, zc0 + 0.01, cx, cy),
            box(cx - DUCT_HW, cx + DUCT_HW, cy - PB_TUBE - 1, cy, -1, 18.0),          # tube window
            box(cx - DUCT_HW, cx + DUCT_HW, cy - PB_R - 1, cy - PB_R + PB_RIM + 1, -1, 18.0)]  # rim exit
    for r, a in PB_BOSSES:
        cuts.append(zcyl(mb.INSERT_R, PB_FLOOR - 1, PB_FLOOR + 6, *polar_at(r, a, cx, cy), seg=32))
    for r, a in PB_ANCHORS:
        cuts.append(zcyl(2.6, -1, PB_H + 1, *polar_at(r, a, cx, cy), seg=32))
    return m - union(cuts)


def make_post_floor():
    cx, cy = mb.XB, mb.YC
    m = m3d.Manifold.extrude(pb_cs(PB_RIM + 0.3), PB_FLOOR)
    cuts = []
    for r, a in PB_BOSSES:
        x, y = polar_at(r, a, cx, cy)
        cuts += [zcyl(1.7, -1, PB_FLOOR + 1, x, y, seg=32), zcone(3.6, 1.7, -0.01, 1.9, x, y, seg=32)]
    for r, a in PB_ANCHORS:
        cuts.append(zcyl(2.6, -1, PB_FLOOR + 1, *polar_at(r, a, cx, cy), seg=32))
    for r, a in PB_PADS:
        cuts.append(zcyl(12.5, -1, 1.2, *polar_at(r, a, cx, cy), seg=64))
    return m - union(cuts)


def post_ballast(base):
    inner = keep_below(bevel_body(pb_cs, PB_H, PB_BEV, inset=PB_RIM, z0=PB_FLOOR), PB_H - PB_TOP)
    return clean(inner - pb_features() - base)


def make_collar():
    """Octagon collar (z 0..COL_H on the axis), 40 deg bevels top and bottom."""
    bh = COL_BEV / math.tan(math.radians(40.0))
    t = 0.01
    sl = [m3d.Manifold.extrude(oct_cs(COL_AF - 2 * COL_BEV), t),
          m3d.Manifold.extrude(oct_cs(COL_AF), t).translate((0, 0, bh)),
          m3d.Manifold.extrude(oct_cs(COL_AF), t).translate((0, 0, COL_H - bh - t)),
          m3d.Manifold.extrude(oct_cs(COL_AF - 2 * COL_BEV), t).translate((0, 0, COL_H - t))]
    m = m3d.Manifold.batch_hull(sl) - zcyl(R_SOCK, -1, COL_H + 1)
    return m.translate((mb.XB, mb.YC, 0))


def make_sleeve(h):
    rin = R_SOCK
    m = zcyl(SL_R, 0, h) - zcyl(SL_R - SL_T, -1, h + 1)
    m = m + (zcyl(rin + SL_T, 0, h) - zcyl(rin, -1, h + 1))
    for a in range(0, 360, 60):
        m = m + zrot(box(rin + SL_T - 0.5, SL_R - SL_T + 0.5, -1.0, 1.0, 0, h), a)
    return m.translate((mb.XB, mb.YC, 0))


def make_saddle(zs):
    """Octagonal saddle on the pipe top: arm seat on top, M3 counterbores from
    below, M4 cross bolt through the pipe.  Prints top-down."""
    cx, cy = mb.XB, mb.YC
    z0 = zs - SAD_H
    t = 0.01
    m = m3d.Manifold.batch_hull([m3d.Manifold.extrude(oct_cs(SAD_AF0), t).translate((0, 0, z0)),
                                 m3d.Manifold.extrude(oct_cs(SAD_AF1), t).translate((0, 0, zs - t))])
    m = m.translate((cx, cy, 0))
    zp = zs - SAD_PLATE
    cuts = [zcyl(R_SOCK, z0 - 1, zp, cx, cy), zcyl(8.0, zp - 1, zs + 1, cx, cy),
            tear_x_down(2.2, cy, z0 + 17.0, cx - 50, cx + 50)]
    for x, y in mb.BRACKET_SCREWS:
        cuts += [zcyl(3.5, z0 - 1, zp, x, y, seg=48), zcyl(1.7, zp - 1, zs + 1, x, y, seg=32)]
    return m - union(cuts)


def post_layout():
    zs = FACE_H - mb.ZC
    total = zs - SAD_H - PB_H - 3 * COL_H
    half = total / 2
    n = math.ceil(half / SLEEVE_MAX)
    h = half / n
    z = PB_H
    collars, sleeves = [], []
    for k in range(3):
        collars.append(z)
        z += COL_H
        if k < 2:
            for _ in range(n):
                sleeves.append(z)
                z += h
    assert abs(z - (zs - SAD_H)) < 1e-6
    return zs, h, collars, sleeves


def make_pipe(zs):
    ro, ri = PIPE_OD / 2, PIPE_OD / 2 - PIPE_WALL
    z1 = zs - SAD_PLATE
    return zcyl(ro, Z_PIPE0, z1, mb.XB, mb.YC) - zcyl(ri, Z_PIPE0 - 1, z1 + 1, mb.XB, mb.YC), z1 - Z_PIPE0


# ---- build -------------------------------------------------------------------
BALL_LOCAL = ("ball_front_in", "ball_rear", "rear_hatch_in", "face_carrier", "electronics_tray",
              "electronics_tray_aio", "aio_deck", "halo_ring_in", "face_disc", "mickey_inlay")
REUSED = ("ball_rear", "face_carrier", "electronics_tray", "face_disc", "face_disc_blank", "mickey_inlay",
          "neck", "arm_base")


def build():
    """Returns (singles: name -> manifold to export, objs: name -> (manifold, meta))."""
    reuse = {"ball_rear": mb.make_ball_rear(), "face_carrier": mb.make_face_carrier(),
             "electronics_tray": mb.make_tray(), "face_disc": mb.make_face_disc(),
             "face_disc_blank": mb.make_face_disc(None), "mickey_inlay": mb.make_inlay(),
             "neck": mb.make_neck(), "arm_base": mb.make_arm_base()}
    set_indoor()
    zs, sl_h, col_z, sl_z = post_layout()
    new = {"ball_front_in": mb.make_ball_front(), "halo_ring_in": mb.make_halo(),
           "rear_hatch_in": make_rear_hatch_in(), "pod_cap_in": mb.make_pod_cap(),
           "pod_cap_blank": make_pod_cap_blank(), "ball_riser": make_riser(),
           "electronics_tray_aio": make_tray_aio(), "aio_deck": make_deck(),
           "wall_bracket_in": mb.make_bracket(), "table_base": make_table_base(), "table_floor": make_table_floor(),
           "post_base": make_post_base(), "post_floor": make_post_floor(), "post_collar": make_collar(),
           "post_sleeve": make_sleeve(sl_h), "post_saddle": make_saddle(zs)}
    singles = {k: clean(v) for k, v in {**reuse, **new}.items()}
    pipe, pipe_len = make_pipe(zs)
    L = {"zs": zs, "sl_h": sl_h, "n_sleeves": len(sl_z), "pipe_len": pipe_len, "col_z": col_z, "sl_z": sl_z}

    A, MO, MD = list(ARMS), list(MOUNTS), list(MODES)
    objs = {}

    def add(name, m, frame, group="part", arms=A, mounts=MO, modes=MD):
        objs[name] = (m, {"frame": frame, "group": group, "arms": list(arms), "mounts": list(mounts),
                          "modes": list(modes)})

    for k in BALL_LOCAL:
        modes = ["split"] if k == "electronics_tray" else ["aio"] if k in ("electronics_tray_aio", "aio_deck") else MD
        add(k, mb.to_ball(singles[k]), "ball", modes=modes)
    add("neck", singles["neck"].translate((0, 0, -G_OUT)), "ball")
    add("arm_base", singles["arm_base"], "arm", arms=["fp", "blank"])
    add("pod_cap_in", singles["pod_cap_in"], "arm", arms=["fp"])
    add("pod_cap_blank", singles["pod_cap_blank"], "arm", arms=["blank"])
    add("ball_riser", singles["ball_riser"], "arm", arms=["ball"])
    add("wall_bracket_in", singles["wall_bracket_in"], "mount", mounts=["wall"])
    add("table_base", singles["table_base"], "mount", mounts=["table"])
    add("table_floor", singles["table_floor"], "mount", mounts=["table"])
    add("post_base", singles["post_base"], "mount", mounts=["post"])
    add("post_floor", singles["post_floor"], "mount", mounts=["post"])
    for i, z in enumerate(col_z):
        add(f"post_collar_{i + 1}", singles["post_collar"].translate((0, 0, z)), "mount", mounts=["post"])
    for i, z in enumerate(sl_z):
        add(f"post_sleeve_{i + 1}", singles["post_sleeve"].translate((0, 0, z)), "mount", mounts=["post"])
    add("post_saddle", singles["post_saddle"], "mount", mounts=["post"])
    # electronics dummies
    comps = mb.components()
    for k, v in comps.items():
        if k.startswith("ctl_"):
            continue
        if k == "r503":
            add(k, v, "arm", "component", arms=["fp"])
        else:
            add(k, v, "ball", "component")
    zt = DECK_Z + DECK_T
    for k, (x0, x1, y0, y1, h) in AIO_BOARDS.items():
        add(k, mb.to_ball(box(x0, x1, y0, y1, zt, zt + h)), "ball", "component", modes=["aio"])
    # hardware + context
    add("post_pipe", pipe, "mount", "hardware", mounts=["post"])
    add("table_ballast", table_ballast(singles["table_base"]), "mount", "hardware", mounts=["table"])
    add("post_ballast", post_ballast(singles["post_base"]), "mount", "hardware", mounts=["post"])
    add("wall", box(-160, 340, -40, 0, -270, 330), "mount", "context", mounts=["wall"])
    add("table", box(mb.XB - 330, mb.XB + 330, mb.YC - 230, mb.YC + 230, -25, 0), "mount", "context",
        mounts=["table"])
    add("floor", box(mb.XB - 420, mb.XB + 420, mb.YC - 420, mb.YC + 420, -20, 0), "mount", "context",
        mounts=["post"])
    band = m3d.CrossSection.circle(32.0, 96) - m3d.CrossSection.circle(29.0, 96)
    add("magicband", mb.xprism(band, -9, 9, yoff=mb.YC + mb.FACE_Y + 35, zoff=mb.ZC), "ball", "context")
    return singles, objs, L


def offsets(L):
    return {"wall": (0.0, 0.0, 0.0), "table": (0.0, 0.0, TB_H), "post": (0.0, 0.0, L["zs"])}


def shift(meta, arm, mount, L):
    if meta["frame"] == "mount":
        return (0.0, 0.0, 0.0)
    o = offsets(L)[mount]
    if meta["frame"] == "ball" and arm == "ball":
        o = (o[0] + mb.XB, o[1], o[2])
    return o


def combo(objs, L, arm, mount, mode, cache):
    out = {}
    for k, (m, me) in objs.items():
        if arm in me["arms"] and mount in me["mounts"] and mode in me["modes"]:
            t = shift(me, arm, mount, L)
            key = (k, t)
            if key not in cache:
                cache[key] = m.translate(t) if any(t) else m
            out[k] = (cache[key], me)
    return out


# ---- checks ------------------------------------------------------------------
def printed_mass(m):
    tm = to_trimesh(m)
    v, a = tm.volume, tm.area
    solid = min(v, a * T_SKIN)
    return RHO * (solid + INFILL * (v - solid)) / 1000.0, np.asarray(tm.center_mass)


def cable_path(arm, mount, L):
    off = np.array(offsets(L)[mount])
    XB, YC, ZC = mb.XB, mb.YC, mb.ZC
    paths = []
    if arm == "fp":
        paths.append(("R503 pod->ball", [np.add(p, off) for p in
                                         [(mb.POD_X, YC, 40.0), (mb.POD_X, YC, 8.5), (0.0, YC, 8.5), (0.0, YC, ZC - 50)]]))
    if arm == "ball":
        head = [(XB, YC, ZC - 50), (XB, YC, 4.0)]
    else:
        head = [(0.0, YC, ZC - 50), (0.0, YC, 8.5), (XB, YC, 8.5)]
    head = [tuple(np.add(p, off)) for p in head]
    if mount == "wall":
        a, b = mb.bore_axis()
        d = (b - a) / np.linalg.norm(b - a)
        tail = [tuple(a), tuple(b + 3 * d)]
    elif mount == "table":
        tail = [(XB, YC, 9.0), (XB, YC - TB_HY - 8, 9.0)]
    else:
        tail = [(XB, YC, 10.5), (XB, YC - PB_R - 8, 10.5)]
    paths.append(("main cable -> " + {"wall": "wall", "table": "base back", "post": "pipe -> base back"}[mount],
                  head + tail))
    return paths


def probe(path):
    return union(m3d.Manifold.batch_hull([m3d.Manifold.sphere(2.9, 24).translate(tuple(p)),
                                          m3d.Manifold.sphere(2.9, 24).translate(tuple(q))])
                 for p, q in zip(path, path[1:]))


def contact_hull(mount):
    cx, cy = mb.XB, mb.YC
    if mount == "table":
        return [(cx + x, cy + y) for x, y in TB_PADS]
    return [polar_at(r, a, cx, cy) for r, a in PB_PADS]


def tip_angle(items, hull):
    mass = sum(m for m, _ in items)
    c = sum(m * np.asarray(p) for m, p in items) / mass
    d = min(((q[0] - p[0]) * (c[1] - p[1]) - (q[1] - p[1]) * (c[0] - p[0])) / math.dist(p, q)
            for p, q in zip(hull, hull[1:] + hull[:1]))
    return mass, c, d, math.degrees(math.atan2(d, c[2]))


def report(singles, objs, L):
    allok = True
    cache = {}
    print("-- indoor layout")
    print(f"  head: ball D{2 * mb.R_BALL:.0f} centre z {mb.ZC:.1f} above the arm seat (outdoor "
          f"{mb.ZC + 2 * G_OUT:.1f}), no gaskets: all {G_OUT:.1f} mm gasket gaps closed")
    print(f"  post: face centre {FACE_H:.0f} -> seat z {L['zs']:.1f}, base {2 * PB_R:.0f} x {PB_H:.0f}, "
          f"3 collars AF{COL_AF:.0f} x {COL_H:.0f}, {L['n_sleeves']} sleeves D{2 * SL_R:.0f} x {L['sl_h']:.1f}, "
          f"saddle {SAD_H:.0f}")
    print(f"  pipe: {PIPE.upper()} OD {PIPE_OD} wall {PIPE_WALL} -> cut length {L['pipe_len']:.0f} mm "
          f"(z {Z_PIPE0:.1f} .. {L['zs'] - SAD_PLATE:.1f})")
    print(f"  table base {2 * TB_HX:.0f} x {2 * TB_HY:.0f} x {TB_H:.0f}, seat at z {TB_H:.0f}")
    # overlaps per combo
    print("-- fit: unintended overlaps per combo (mm3, bbox-touching pairs; ballast excluded)")
    pair_cache = {}
    for arm in ARMS:
        for mount in MOUNTS:
            for mode in MODES:
                c = combo(objs, L, arm, mount, mode, cache)
                names = [k for k, (_, me) in c.items() if me["group"] != "hardware" or k == "post_pipe"]
                bb = {k: bbox(c[k][0]) for k in names}
                worst, n = (0.0, "-"), 0
                for i, a in enumerate(names):
                    for b in names[i + 1:]:
                        ga, gb = c[a][1]["group"], c[b][1]["group"]
                        if ga == "component" and gb == "component" or ga == gb == "context":
                            continue
                        if not bbox_hit(bb[a], bb[b]):
                            continue
                        key = (id(c[a][0]), id(c[b][0]))
                        if key not in pair_cache:
                            pair_cache[key] = (c[a][0] ^ c[b][0]).volume()
                        n += 1
                        ov = pair_cache[key]
                        if ov > worst[0]:
                            worst = (ov, f"{a}/{b}")
                good = worst[0] <= 1e-2
                allok &= good
                print(f"  {arm:5s} {mount:5s} {mode:5s} {n:3d} pairs, max overlap {worst[0]:.4f} {worst[1]} -> {ok(good)}")
    # components vs enclosure (head is the same on every mount)
    print("-- components vs enclosure (min gap, mm)")
    cok = True
    for arm, mode in (("fp", "split"), ("fp", "aio"), ("ball", "aio")):
        c = combo(objs, L, arm, "wall", mode, cache)
        encl = {k: m for k, (m, me) in c.items() if me["group"] == "part"}
        for k, (cm, me) in c.items():
            if me["group"] != "component" or (arm == "ball" and k not in AIO_BOARDS):
                continue
            hits = [p for p, pm in encl.items() if bbox_hit(bbox(cm), bbox(pm)) and (cm ^ pm).volume() > 1e-2]
            gap = min((cm.min_gap(pm, 3.0) for pm in encl.values() if bbox_hit(bbox(cm), bbox(pm), 3.0)), default=3.0)
            cok &= not hits
            if k in AIO_BOARDS or mode == "split":
                print(f"  {arm:4s} {mode:5s} {k:14s} min gap {gap:4.2f}" + (f" HITS {hits} -> FAIL" if hits else ""))
    print(f"  components incl. relay + terminal clear of the enclosure -> {ok(cok)}")
    allok &= cok
    # cable paths
    print("-- cable path (6 mm probe vs all printed parts + pipe)")
    pok = True
    for arm in ARMS:
        for mount in MOUNTS:
            c = combo(objs, L, arm, mount, "aio", cache)
            encl = [m for k, (m, me) in c.items() if me["group"] == "part" or k == "post_pipe"]
            for label, path in cable_path(arm, mount, L):
                pr = probe(path)
                pb = bbox(pr)
                hit = sum((pr ^ m).volume() for m in encl if bbox_hit(pb, bbox(m)))
                pok &= hit < 1e-2
                print(f"  {arm:5s} {mount:5s} {label:26s} overlap {hit:.3f} mm3 -> {ok(hit < 1e-2)}")
    print(f"  cable path continuous for every combo -> {ok(pok)}")
    allok &= pok
    # tip-over
    print(f"-- tip-over (printed {RHO} g/cm3, {T_SKIN} mm skins + {INFILL * 100:.0f} % infill; "
          f"{PIPE.upper()} pipe {PIPE_RHO} g/cm3; contact = felt pad centres)")
    masses = {}
    tips = {}
    for mount in ("table", "post"):
        for arm in ARMS:
            c = combo(objs, L, arm, mount, "aio", cache)
            items = []
            for k, (m, me) in c.items():
                if me["group"] == "part":
                    key = (k, bbox(m)[0].tobytes())
                    if key not in masses:
                        masses[key] = printed_mass(m)
                    items.append(masses[key])
                elif me["group"] == "component":
                    lo, hi = bbox(m)
                    items.append((E_MASS.get(k, 5) / 1.0, (lo + hi) / 2))
                elif k == "post_pipe":
                    items.append((m.volume() * PIPE_RHO / 1000, np.mean(bbox(m), axis=0)))
            ball_c = np.add(shift({"frame": "ball"}, arm, mount, L), (0, mb.YC, mb.ZC))
            items.append((E_WIRING, ball_c))
            bal = c[f"{mount}_ballast"][0]
            btm = to_trimesh(bal)
            res = {}
            for kind, dens in BALLAST.items():
                res[kind] = tip_angle(items + [(btm.volume * dens / 1000, btm.center_mass)], contact_hull(mount))
            res["none"] = tip_angle(items, contact_hull(mount))
            tips[(mount, arm)] = res
            use = BALLAST_USE[mount]
            M, com, d, ang = res[use]
            good = ang >= MIN_TIP
            allok &= good
            bm = btm.volume * BALLAST[use] / 1000
            print(f"  {mount:5s} {arm:5s} ballast {use} {bm / 1000:.2f} kg (pockets {btm.volume / 1000:.0f} cm3): "
                  f"total {M / 1000:.2f} kg, CoM ({com[0] - mb.XB:+.0f}, {com[1] - mb.YC:+.0f}, {com[2]:.0f}) "
                  f"edge {d:.0f} -> tip {ang:.1f} deg (steel {res['steel'][3]:.1f}, none {res['none'][3]:.1f}) "
                  f"-> {ok(good)}")
    return allok, tips


# ---- export --------------------------------------------------------------------
UP = {
    "ball_front_in": ((0, -1, 0), "face down"), "halo_ring_in": ((0, 1, 0), "shoulder down"),
    "rear_hatch_in": ((0, 1, 0), "back down"), "pod_cap_in": (tuple(-mb.POD_N), "top face down"),
    "pod_cap_blank": (tuple(mb.POD_N), "rim down (top up)"), "ball_riser": ((0, 0, 1), "base down"),
    "electronics_tray_aio": ((0, 0, 1), "plate down"), "aio_deck": ((0, 0, 1), "plate down"),
    "wall_bracket_in": ((0, 1, 0), "wall side down"), "table_base": ((0, 0, -1), "top down"),
    "table_floor": ((0, 0, -1), "inside down"), "post_base": ((0, 0, -1), "top down"),
    "post_floor": ((0, 0, -1), "inside down"), "post_collar": ((0, 0, 1), "upright"),
    "post_sleeve": ((0, 0, 1), "upright"), "post_saddle": ((0, 0, -1), "top down"),
}
MATERIAL = {
    "ball_front_in": "PETG/PLA silver", "ball_rear": "PETG/PLA silver", "rear_hatch_in": "PETG/PLA",
    "face_carrier": "PETG/PLA white", "electronics_tray": "PETG/PLA", "electronics_tray_aio": "PETG/PLA",
    "aio_deck": "PETG/PLA", "halo_ring_in": "transl. PETG", "face_disc": "PETG/PLA black",
    "face_disc_blank": "PETG/PLA black", "mickey_inlay": "transl. PETG", "neck": "PETG/PLA",
    "arm_base": "PETG/PLA", "pod_cap_in": "PETG/PLA", "pod_cap_blank": "PETG/PLA", "ball_riser": "PETG/PLA",
    "wall_bracket_in": "PETG/PLA", "table_base": "PETG/PLA", "table_floor": "PETG/PLA",
    "post_base": "PETG green", "post_floor": "PETG/PLA", "post_collar": "PETG green",
    "post_sleeve": "PETG green", "post_saddle": "PETG green",
}

GREEN, GREEN2 = "#1f4d2b", "#183d22"
COLOR = {
    "ball_front_in": "#c3c8ce", "ball_rear": "#b8bdc3", "rear_hatch_in": "#9fa5ab", "face_carrier": "#f4f4f2",
    "electronics_tray": "#e2e2dc", "electronics_tray_aio": "#e2e2dc", "aio_deck": "#d6d6cf",
    "halo_ring_in": ("#e9f6ff", 0.8), "face_disc": "#18191b", "mickey_inlay": ("#f6f7f2", 0.92),
    "neck": "#4a4f55", "arm_base": "#4a4f55", "pod_cap_in": "#5a6066", "pod_cap_blank": "#5a6066",
    "ball_riser": "#4a4f55", "wall_bracket_in": "#4a4f55", "table_base": "#3b4046", "table_floor": "#2c3035",
    "post_base": GREEN2, "post_floor": "#2c3035", "post_saddle": GREEN2,
    "pn532": "#c0392b", "speaker": "#333333", "led_strip": "#f0f0f0", "tamper_switch": "#222222",
    "r503": "#202020", "relay": "#1f5fbf", "terminal": "#2e9e4f",
    "post_pipe": "#9aa3ab", "table_ballast": ("#b59a6a", 0.9), "post_ballast": ("#b59a6a", 0.9),
    "wall": ("#d9d4c7", 0.55), "table": ("#a0784f", 0.6), "floor": ("#cfcac0", 0.6),
    "magicband": ("#2c7be5", 0.45),
}
EXPLODE = {
    "ball_front_in": (0, 110, 0), "ball_rear": (0, 0, 0), "rear_hatch_in": (0, -110, 0),
    "face_carrier": (0, 150, 0), "electronics_tray": (0, -60, -40), "electronics_tray_aio": (0, -60, -40),
    "aio_deck": (0, -60, 0), "halo_ring_in": (0, 220, 0), "face_disc": (0, 260, 0), "mickey_inlay": (0, 300, 0),
    "neck": (0, 0, -55), "arm_base": (0, 0, -110), "pod_cap_in": (0, 0, -20), "pod_cap_blank": (0, 0, -20),
    "ball_riser": (0, 0, -110), "wall_bracket_in": (0, 0, -200), "table_base": (0, 0, -140),
    "table_floor": (0, 0, -220), "post_base": (0, 0, -120), "post_floor": (0, 0, -200),
    "post_saddle": (0, 0, -40), "pn532": (0, 175, 0), "speaker": (0, 130, 0), "led_strip": (0, 165, 0),
    "tamper_switch": (0, -40, 0), "r503": (0, 0, 40), "relay": (0, -60, 40), "terminal": (0, -60, 40),
    "post_pipe": (0, 0, 0), "table_ballast": (0, 0, -180), "post_ballast": (0, 0, -160),
    "magicband": (0, 120, 0),
}


def meta_view(name, me):
    c = COLOR.get(name, GREEN if name.startswith("post_") else "#1f6f43")
    c, o = c if isinstance(c, tuple) else (c, 1.0)
    e = EXPLODE.get(name, (0, 0, 0))
    if name.startswith("post_collar_") or name.startswith("post_sleeve_"):
        e = (0, 0, -60)
    if me["frame"] == "ball" and name != "neck":
        e = tuple(np.add(e, (0, 0, 110)))
    if me["frame"] == "arm" and name in ("pod_cap_in", "pod_cap_blank", "r503"):
        e = tuple(np.add(e, mb.POD_N * 90 + (0, 0, 0)))
    return c, o, [round(float(v), 1) for v in e]


def check_identical(name, tm):
    import trimesh
    p = os.path.join(mb.OUT, "stl", f"{name}.stl")
    if not os.path.exists(p):
        return "outdoor STL missing"
    ref = trimesh.load(p)
    same = len(ref.faces) == len(tm.faces) and np.allclose(ref.bounds, tm.bounds, atol=1e-3) and \
        abs(ref.volume - tm.volume) < 1e-3 * max(1.0, ref.volume)
    return "identical to ../../cad/stl" if same else "DIFFERS from outdoor STL"


def export(singles, objs, L):
    print("-- STL export (print orientation): indoor-new parts -> stl/, reused parts checked only")
    os.makedirs(os.path.join(OUT, "stl"), exist_ok=True)
    os.makedirs(os.path.join(OUT, "preview"), exist_ok=True)
    allok = True
    rows = []
    for name, m in singles.items():
        up, how = (mb.UP[name] if name in REUSED else UP[name])
        bodies = len(m.decompose())
        tm = to_trimesh(orient(m, up))
        tm.apply_translation(-np.array([tm.bounds[0][0] + tm.extents[0] / 2,
                                        tm.bounds[0][1] + tm.extents[1] / 2, tm.bounds[0][2]]))
        if name in REUSED:
            where = check_identical(name, tm)
            good_id = where.startswith("identical")
        else:
            tm.export(os.path.join(OUT, "stl", f"{name}.stl"))
            where, good_id = "stl/", True
        side, ang = bed_fit(tm)
        fits = side <= mb.BED - 2 * mb.BED_MARGIN and tm.extents[2] <= mb.BED - mb.BED_MARGIN
        oh = overhang_area(tm)
        good = fits and tm.is_watertight and bodies == 1 and oh < 1.0 and good_id
        allok &= good
        rows.append((name, MATERIAL[name], np.round(tm.extents, 1), oh, good))
        print(f"  {name:20s} {MATERIAL[name]:16s} {how:17s} size {np.round(tm.extents, 1)} fp {side:5.1f}@{ang:2d} "
              f"{tm.volume / 1000:6.1f} cm3 bodies {bodies} wt {tm.is_watertight} overhang {oh:4.1f} mm2 "
              f"[{where}] -> {ok(good)}")
    entries = []
    for name, (m, me) in objs.items():
        to_trimesh(m).export(os.path.join(OUT, "preview", f"{name}.stl"))
        c, o, e = meta_view(name, me)
        entries.append({"name": name, "file": f"preview/{name}.stl", "color": c, "opacity": o, "explode": e,
                        "group": me["group"], "frame": me["frame"], "arms": me["arms"], "mounts": me["mounts"],
                        "modes": me["modes"], "glow": name in ("halo_ring_in", "mickey_inlay", "led_strip")})
    with open(os.path.join(OUT, "preview", "manifest.json"), "w") as fh:
        json.dump({"title": "MagicBand reader, indoor: arm x mount x electronics",
                   "offsets": offsets(L), "ball_only_shift": [mb.XB, 0, 0],
                   "ball": [0, mb.YC, mb.ZC], "section_y": mb.YC,
                   "arms": {"fp": "Fingerprint pod", "blank": "Blank pod", "ball": "Ball only"},
                   "mounts": {"wall": "Wall bracket", "table": "Tabletop base", "post": "Freestanding post"},
                   "modes": {"split": "Split (reader + indoor controller)", "aio": "All-in-one (relay in head)"},
                   "parts": entries}, fh, indent=1)
    print(f"  all parts single body + watertight + bed fit + overhang ~0 (+ reused == outdoor) -> {ok(allok)}")
    return allok, rows


def main():
    singles, objs, L = build()
    a, _ = report(singles, objs, L)
    b, _ = export(singles, objs, L)
    print(f"== ALL CHECKS {ok(a and b)}")


if __name__ == "__main__":
    main()
