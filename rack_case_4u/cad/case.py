"""4U 19" rack case, 3D printed (ASA) on a Bambu P1S (256 bed, parts <= 250).
Structure clips together with printed snap pins; removable modules slide on
printed plastic rails.  No screws, no heat-set inserts, no bearings.

Hardware: ASUS ROG STRIX B660-G GAMING WIFI (mATX 244 x 244) with a tower air
cooler (<= 140 mm), 1600 W ATX PSU (150 x 86 x 200), 4 x NVIDIA Tesla V100
PCIe (passive): A and B in the board's two x16 slots, C and D on OCuLink
slot boards fed from the two M.2 slots (thin round SFF-8611 cables).

Top view (front at the bottom, x to the right):

  REAR   [ D    C  | A    B ][ board I/O ][ 2 x 92 exh (outside) ][ C14 ]
         | GPU D  GPU C | GPU A  GPU B |   CPU + tower cooler      |AC/ |
         | (OCuLink     | (board x4 /  |                           |EPS |
         |  slot boards)|  x16 slots)  |                           |trgh|
         |---- duct sleeve over the 4 card tails ----|  slack + plug zone |
         |  loft     2 x 120x38 push fans (module)   |G| 1600 W PSU sled |
  FRONT  [ GPU fan bay (rail)                         |L|[ PSU bay (rail) ]
          x 5 .. 246                                  ane  x 263 .. 416

Rails (plastic on plastic, all print without supports):
  GPU fan module  dovetail rail on the floor, slides out of the FRONT bay
  PSU sled        dovetail rail on the floor, slides out of the FRONT bay
  lid hatch       45 deg V-tongues in wall V-grooves, slides off the REAR over
                  the lowered rear panel; flexure latches at the rear
GPUs and the board tray lift out with the lid and the fan module off.
Cable management: right trough (AC inlet strain relief -> PSU, EPS 8-pin),
GPU lane between the fan module and the PSU (4 x 8-pin, 24-pin), AC slack
bay behind the PSU, comb clips, zip-tie slots, OCuLink guide on the GPU stand.
Clips (structure): lock pins through rib pairs / flanges + floor, countersunk
lock pins (panels -> wall end ribs, rails -> floor), dovetail puzzle joints
between lid tiles, service pins for removable parts.
Bought: nylon snap-in PCB standoffs, silicone fan rivets, snap-in C14, OCuLink kit.

World frame: x across (0 = left outer face), y front -> rear (0 = front face
of the front panel, ears and handles at y < 0), z up (0 = underside of the
floor ribs).  Shell tiles are built in a local (u, v, w) frame -- w = 0 is the
visible face, ribs grow towards +w, and +w is up when printing -- and mapped
to the world by a proper rotation.

Run: PYTHONPATH=../../.pydeps python3 case.py
Outputs stl/ (print orientation), preview/ (assembled + context + manifest).
"""
import json
import math
import os

import numpy as np
import manifold3d as m3d

OUT = os.path.dirname(os.path.abspath(__file__))

# ---- printer / fits (tune these after printing stl/tolerance_coupon_*) ------
BED = 256.0
BED_MAX = 250.0         # largest part extent we allow on the 256 bed
CLR_SLIDE = 0.4         # per side: rails, grooves, bays, pins
CLR_SEAM = 0.25         # per side: 45 deg scarf seams between shell tiles
CLR_PUZZLE = 0.12       # per side: dovetail puzzle joints between lid tiles
CLR_PRESS = 0.1         # per side: magnet pockets
CLR_PART = 1.0          # per side around bought parts
MAG_D, MAG_T = 6.0, 3.0                 # 6 x 3 mm neodymium disc magnets
FOOT_RELIEF = 0.4       # elephant-foot relief on every bed-contact edge
BRIM_EAR_R, BRIM_EAR_T = 8.0, 0.4       # snap-off mouse ears on large tiles
SHRINK = 1.0            # ASA: export at 1.005 or scale 100.5 % in the slicer
OVERHANG_DEG = 45.0     # report down-facing area steeper than this
CIRC = 48

# ---- snap pins ------------------------------------------------------------------
PIN_D = 5.0             # shank
PIN_HOLE = 5.3          # holes for pins (shank + 2 x 0.15)
PIN_FLAT = 0.6          # flats: thickness = PIN_FLAT * d (prints flat, no support)
PIN_SLOT = 2.0          # split between the two snap arms
PIN_LIP = 0.7           # lock barb (square catch)
SPIN_LIP = 0.5          # service barb (35 deg detent, pulls out by hand)
PIN_BARB = 4.0          # barb length past the grip
PIN_CLR = 0.3           # barb catch sits this far past the far face
PIN_HEAD_D, PIN_HEAD_T = 9.0, 2.0
TAB_PIN_D, TAB_PIN_HOLE = 4.0, 4.2      # V100 bracket-tab pins (blind, detent)
TAB_LIP = 0.3
SNAP_STANDOFF_HOLE = 4.0                # bought nylon snap-in PCB standoffs
SNAP_PANEL_T = 1.6                      # panel thickness those (and the C14) snap into
FAN_RIVET_HOLE = 4.6                    # silicone fan rivets
IEC_SNAP = (19.6, 27.2)                 # snap-in C14 cutout (w, h), mounted vertical

# ---- rails ------------------------------------------------------------------------
RAIL_H = 6.0                            # dovetail rail height
RAIL_W0, RAIL_W1 = 10.0, 22.0           # bottom / top width (45 deg flanks)
SLED_T = 8.0                            # sled / module base plates (rail channel inside)
VGROOVE = 2.0                           # depth of the hatch V-grooves (45 deg)
LATCH_W, LATCH_L, LATCH_DROP = 16.0, 50.0, 6.0  # lid flexure latch

# ---- outer shell -------------------------------------------------------------
W = 430.0               # body width (19" rails leave 450)
H = 176.0               # 4U = 177.8
FLOOR_T, FLOOR_RIB = 4.0, 12.0
Z_FL = FLOOR_RIB + FLOOR_T              # floor top = 16
LID_T = 5.0
Z_WT = H - LID_T                        # underside of the lid = 171
WALL_T, WALL_RIB = 4.0, 10.0
PANEL_T, PANEL_RIB = 5.0, 10.0
SEAM_RIB = 4.5                          # seam rib pairs -> 9.25 mm pin grip (arm strain)
FLANGE_T = 6.0                          # structural flanges lock-pinned to the floor
SVC_T = 4.0                             # base plates of service-pinned trays
XI0, XI1 = WALL_T, W - WALL_T           # inner faces of the side walls
RIB_IN = XI0 + WALL_RIB                 # wall ribs / flanges reach x = 14

# ---- board, cooler, PSU ------------------------------------------------------------
Y_FI = PANEL_T                          # inner face of the front panel = 5
BOARD = 244.0
BX0 = 152.0                             # board slot edge (slots face left)
BX1 = BX0 + BOARD                       # 396, CPU edge
BY0 = 314.0
BY1 = BY0 + BOARD                       # 558, I/O edge
Y_RI = BY1 + 4.0                        # inner face of the rear panel = 562
D = Y_RI + PANEL_T                      # 567
STANDOFF_H = 6.35                       # nylon snap standoffs (board, slot boards)
BZ = Z_FL + SVC_T + STANDOFF_H          # board underside
BZ_TOP = BZ + 1.6
COOLER = (125.0, 80.0, 140.0)           # tower cooler w (x), d (y), h above the board
CPU_FROM_EDGE, CPU_FROM_IO = 70.0, 95.0
PSU_W, PSU_H, PSU_L = 150.0, 86.0, 200.0        # 1600 W ATX (measure!)
PSU_X0 = XI1 - WALL_RIB - 2.0 - PSU_W           # 264
PSU_Y0 = 40.0                           # 35 mm for modular plugs in front
PSU_Y1 = PSU_Y0 + PSU_L                 # 240, AC inlet + exhaust face
PSU_Z0 = Z_FL + SLED_T
PSU_TOP = PSU_Z0 + PSU_H
PSU_RAIL_X = PSU_X0 + PSU_W / 2
SLED_X0, SLED_X1 = PSU_X0 - 1.0, XI1 - WALL_RIB - CLR_SLIDE
SLED_Y1 = PSU_Y1 + 6.0                  # sled + 3 mm face flange stays <= 250 long
PSU_AC = (PSU_X0 + PSU_W - 30.0, PSU_Z0 + 30.0)  # inlet on the rear face (x, z)

# ---- GPUs ----------------------------------------------------------------------------
CARD_L, CARD_H, CARD_T = 267.0, 111.2, 35.0     # Tesla V100 PCIe (measure!)
SLOT_FROM_EDGE = {"A": 14.0, "B": 75.0}  # board slots: x16 (x4) and x16 Gen5 (measure!)
SLOT_X = {"B": BX0 + SLOT_FROM_EDGE["B"], "A": BX0 + SLOT_FROM_EDGE["A"]}
SLOT_X["C"] = SLOT_X["A"] - 61.0         # OCuLink slot boards on the GPU stand
SLOT_X["D"] = SLOT_X["C"] - 56.5
CARDS = ["D", "C", "A", "B"]
Y_BRK = Y_RI - 1.0                      # bracket plane (561), tabs rest on the slot rail
Y_TAIL = Y_BRK - CARD_L                 # 294
SLOT_H = 11.25
Z_CARD0 = BZ_TOP + SLOT_H               # card body bottom (slot top)
GZ = Z_CARD0 + CARD_H / 2               # fan + duct centre height
FINGER_LEN, FINGER_Y_OFF = 89.0, 42.0
FY1 = Y_BRK - FINGER_Y_OFF
FY0 = FY1 - FINGER_LEN
BRK_TOP = Z_CARD0 + CARD_H + 9.0        # bracket tab height = slot rail top (120 mm bracket)
BRK_W = 37.0
ADAPTER = (40.0, 110.0)                 # OCuLink slot board x, y size (measure!)


def card_body_x(k):
    return SLOT_X[k] - CARD_T + 2.0, SLOT_X[k] + 2.0


ENV_X0 = card_body_x("D")[0]
ENV_X1 = card_body_x("B")[1]

# ---- GPU fan module ---------------------------------------------------------------------
GFAN, GFAN_T, GFAN_HOLE = 120.0, 38.0, 105.0    # 2 x high-static 120 x 38
FAN_R, HUB_R = 57.5, 20.0
FAN_XC = [XI0 + 1.0 + GFAN / 2, XI0 + 1.0 + 1.5 * GFAN]   # 65, 185 (fans x 5 .. 245)
DUCT_WALL = 2.4
DFLANGE_T = 5.0
Y_PUSH0 = Y_FI + 11.0                   # 16
Y_PUSH1 = Y_PUSH0 + GFAN_T              # 54: duct flange
LIP, SLV_CLR, SLV = 2.0, 1.0, 20.0
PWR_NOTCH_W = 22.0
MOD_X0, MOD_X1 = RIB_IN + CLR_SLIDE, FAN_XC[1] + GFAN / 2 - 6.0  # module base plate
GPU_RAIL_X = (MOD_X0 + MOD_X1) / 2
Y_SPLIT = 150.0                         # fan_face | fan_duct joint
FAN_BAND = (GZ - GFAN / 2 - 1.0, GZ + GFAN / 2 + 1.0)
MOD_FLANGE = 3.0                        # small flange: total width stays <= 250

# ---- cable management ------------------------------------------------------------------
TROUGH_R = (BX1 + 1.6, XI1 - WALL_RIB - CLR_SLIDE)   # right trough x (397.6 .. 415.6)
TROUGH_R_Y = [PSU_Y1 + 15.0, 403.0, Y_RI - 10.4]
LANE = (MOD_X1 + 7.0, SLED_X0 - CLR_SLIDE)           # GPU lane x between module and sled
LANE_Y = [Y_FI + 10.4, 160.0, Y_TAIL - 4.0]
TROUGH_H = 34.0                         # wall height above the base

# ---- misc -------------------------------------------------------------------------
SKIN = 0.4
EAR_W = 26.3                            # 482.6 overall
EAR_HOLE_X = 232.55                     # 465.1 / 2 from the centre
U = 44.45
RACK_Z0 = -(4 * U - H) / 2
IO_W, IO_H = 158.75, 44.45
IO_X1 = BX1 - 4.9
IO_Z0 = BZ_TOP - 2.24
MATX_HOLES = [(6.35, 10.16), (6.35, 165.10), (163.83, 10.16),
              (163.83, 165.10), (209.55, 10.16), (209.55, 165.10)]
PSU_HOLES = [(6.0, 6.0), (6.0, 80.0), (144.0, 80.0), (144.0, 6.0)]
AC_SLACK = 260.0                        # sled travel the AC lead must follow

TILE_X_FLOOR = [0.0, 215.0, W]
TILE_Y = [0.0, 189.0, 378.0, D]
WALL_Y = [Y_FI, 189.0, 378.0, Y_RI]
FRONT_BODY_X = [0.0, 130.0, 254.0, W]
REAR_X = [0.0, 120.0, 181.0, 398.0, W]   # seams in the gaps between the GPU brackets
HATCH_X = [XI0 + 0.2, 215.0, XI1 - 0.2]
HATCH_Y = [Y_FI + 0.4, 189.0, 378.0, D]

GRIP_FLOOR = FLANGE_T + FLOOR_T
GRIP_SVC = SVC_T + FLOOR_T
GRIP_RAIL = RAIL_H + FLOOR_T
GRIP_SEAM = 2 * SEAM_RIB + CLR_SEAM
DIV_X0, RF_Y1 = 134.0, 240.0            # (unused tile maps kept harmless)


# ---- geometry helpers ----------------------------------------------------------
def box(x0, x1, y0, y1, z0, z1):
    return m3d.Manifold.cube((x1 - x0, y1 - y0, z1 - z0)).translate((x0, y0, z0))


def union(parts):
    parts = [p for p in parts if p is not None and not p.is_empty()]
    if not parts:
        return m3d.Manifold()
    return m3d.Manifold.batch_boolean(parts, m3d.OpType.Add)


def xform(m, R, t=(0, 0, 0)):
    M = np.hstack([np.asarray(R, float), np.asarray(t, float).reshape(3, 1)])
    return m.transform(M)


def frame_for(axis, up):
    """Rotation whose local z is `axis` and local x the component of `up` normal to it."""
    a = np.asarray(axis, float)
    a = a / np.linalg.norm(a)
    u = np.asarray(up, float)
    u = u - a * (u @ a)
    tip = np.linalg.norm(u) > 1e-6
    if not tip:
        u = np.array([1.0, 0, 0]) if abs(a[0]) < 0.9 else np.array([0, 1.0, 0])
        u = u - a * (u @ a)
    u = u / np.linalg.norm(u)
    return np.column_stack([u, np.cross(a, u), a]), tip


def hole(p, axis, length, d, up=(0, 0, 1), n=CIRC):
    """Hole from p along axis.  Teardrop (45 deg roof towards print-up) when the
    axis is not vertical in print, so horizontal holes need no support."""
    R, tip = frame_for(axis, up)
    r = d / 2
    pts = [(r * math.cos(2 * math.pi * i / n), r * math.sin(2 * math.pi * i / n))
           for i in range(n)]
    if tip:
        pts.append((r * math.sqrt(2), 0.0))
    cs = m3d.CrossSection([pts]).hull()
    return xform(m3d.Manifold.extrude(cs, length), R, p)


def thru(p, axis, length, d=PIN_HOLE, up=(0, 0, 1)):
    """Through hole that starts 1 mm before p and runs length + 2 along axis."""
    a = np.asarray(axis, float)
    return hole(np.asarray(p, float) - a, axis, length + 2.0, d, up)


def cyl_z(x, y, z0, z1, r, n=CIRC):
    return m3d.Manifold.cylinder(z1 - z0, r, r, n).translate((x, y, z0))


def rrect(w, h, r):
    r = max(min(r, w / 2 - 0.01, h / 2 - 0.01), 0.01)
    sq = m3d.CrossSection.square((w - 2 * r, h - 2 * r), center=True)
    return sq.offset(r, m3d.JoinType.Round, circular_segments=32)


def rect(x0, x1, y0, y1):
    return m3d.CrossSection.square((x1 - x0, y1 - y0)).translate((x0, y0))


def circle(r, n=128):
    return m3d.CrossSection.circle(r, n)


def poly(pts):
    """Polygon from points in either winding."""
    a = sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1]))
    return m3d.CrossSection([pts if a > 0 else pts[::-1]])


def union_cs(css):
    out = css[0]
    for c in css[1:]:
        out = out + c
    return out


def hex_grid(region, cell=9.0, web=1.8):
    """Hexagonal holes (flat-to-flat `cell`) clipped to the 2D `region`."""
    x0, y0, x1, y1 = region.bounds()
    rc = cell / 2 / math.cos(math.pi / 6)
    dx = cell + web
    dy = dx * math.sin(math.pi / 3)
    polys = []
    j = 0
    y = y0 - dy
    while y < y1 + dy:
        x = x0 - dx + (dx / 2 if j % 2 else 0)
        while x < x1 + dx:
            polys.append([(x + rc * math.cos(math.pi / 6 + k * math.pi / 3),
                           y + rc * math.sin(math.pi / 6 + k * math.pi / 3)) for k in range(6)])
            x += dx
        y += dy
        j += 1
    return m3d.CrossSection(polys) ^ region.offset(-web, m3d.JoinType.Miter)


def plane_cut(cs, axis, c0, c1):
    """Extrude a 2D section along a world axis.  cs coords: axis x -> (y, z),
    axis y -> (x, z), axis z -> (x, y)."""
    m = m3d.Manifold.extrude(cs, c1 - c0)
    if axis == "z":
        return m.translate((0, 0, c0))
    if axis == "y":
        return xform(m, [[1, 0, 0], [0, 0, -1], [0, 1, 0]], (0, c1, 0))
    return xform(m, [[0, 0, 1], [1, 0, 0], [0, 1, 0]], (c0, 0, 0))


def loft(stations):
    """Ruled loft along z through convex sections [(cs, z), ...] (pairwise hulls)."""
    out = []
    for (a, za), (b, zb) in zip(stations, stations[1:]):
        if zb > za:
            sa = m3d.Manifold.extrude(a, 1e-3).translate((0, 0, za))
            sb = m3d.Manifold.extrude(b, 1e-3).translate((0, 0, zb - 1e-3))
            out.append(m3d.Manifold.batch_hull([sa, sb]))
    return union(out)


def clean(m):
    parts = [c for c in m.decompose() if c.volume() > 1.0]
    return m3d.Manifold.compose(parts) if parts else m


# ---- snap pins ---------------------------------------------------------------------
PINS = []               # registered pins: (kind, head, grip, p, axis, d, tab)


def add_pin(kind, p, axis, grip, head="flat", d=PIN_D, tab=(1, 0, 0)):
    """kind lock / service / tab; p = head-side face, axis = insertion direction,
    tab = direction the pull tab of a 'tab' head points (normal to axis)."""
    a = np.asarray(axis, float)
    PINS.append((kind, head, round(grip, 2), np.asarray(p, float), a / np.linalg.norm(a), d,
                 np.asarray(tab, float)))


def make_pin(kind, grip, head="flat", d=PIN_D):
    """Pin along +z from the head seat (z = 0); flats normal to x, split along y."""
    r = d / 2
    lip = (PIN_LIP if kind == "lock" else SPIN_LIP) * d / PIN_D
    if kind == "tab":
        lip = TAB_LIP
    g, c, bl = grip, PIN_CLR, PIN_BARB * d / PIN_D
    prof = []
    if head == "csk":                     # 90 deg countersunk, flush
        prof += [(0.0, 0.0), (4.5, 0.0), (r, 4.5 - r)]
    else:
        ht, hr = PIN_HEAD_T * d / PIN_D, PIN_HEAD_D / 2 * d / PIN_D
        prof += [(0.0, -ht), (hr, -ht), (hr, 0.0), (r, 0.0)]
    if kind == "lock":
        prof += [(r, g + c), (r + lip, g + c), (r - 0.4, g + c + bl), (0.0, g + c + bl)]
    else:                                 # 35 deg detent both ways
        z1 = g + c + lip / math.tan(math.radians(35))
        prof += [(r, g + c), (r + lip, z1), (r - 0.4, z1 + bl), (0.0, z1 + bl)]
    tip = prof[-1][1]
    m = m3d.Manifold.revolve(poly(prof), 64)
    fz = PIN_FLAT * d / 2
    m = m ^ box(-fz, fz, -20, 20, -20, tip + 20)
    s = PIN_SLOT * d / PIN_D
    m = m - box(-fz - 1, fz + 1, -s / 2, s / 2, min(0.8, g * 0.15), tip + 1)
    if head == "tab":                     # flat pull tab in the head plane (+y)
        ht, hr = PIN_HEAD_T * d / PIN_D, PIN_HEAD_D / 2 * d / PIN_D
        t = box(-fz, fz, hr - 1.0, hr + 8.0, -ht, 0.0)
        m = m + (t - box(-fz - 1, fz + 1, hr + 3.0, hr + 5.0, -ht - 1, -ht + 0.8))
    return m


_PIN_CACHE = {}


def pin_body(kind, head, grip, d):
    key = (kind, head, grip, d)
    if key not in _PIN_CACHE:
        _PIN_CACHE[key] = make_pin(kind, grip, head, d)
    return _PIN_CACHE[key]


def placed_pins():
    """kind -> composed world bodies of every registered pin."""
    out = {}
    for (kind, head, grip, p, a, d, tab) in PINS:
        m = pin_body(kind, head, grip, d)
        c = np.cross(tab, a)
        hint = c if np.linalg.norm(c) > 1e-6 else ((1, 0, 0) if abs(a[0]) < 0.9 else (0, 1, 0))
        R, _ = frame_for(a, hint)           # local y = tab direction
        out.setdefault(kind, []).append(xform(m, R, p))
    return {k: m3d.Manifold.compose(v) for k, v in out.items()}


def pin_types():
    cnt = {}
    for (kind, head, grip, p, a, d, tab) in PINS:
        cnt[(kind, head, grip, d)] = cnt.get((kind, head, grip, d), 0) + 1
    return cnt


def csk_pin(p, axis, grip, up=(0, 0, 1)):
    """Countersunk lock pin (flush head) and its hole + countersink, registered."""
    a = np.asarray(axis, float)
    add_pin("lock", p, a, grip, "csk")
    R, _ = frame_for(a, (1, 0, 0) if abs(a[0]) < 0.9 else (0, 1, 0))
    cone = xform(m3d.Manifold.cylinder(2.31, 4.6, 2.29, CIRC), R, np.asarray(p, float) - 0.01 * a)
    return thru(p, a, grip, up=up) + cone


# ---- ribbed shell tile -----------------------------------------------------------
TILE_PINS = []          # local (p, axis, grip) of seam pins from the last tile() call


def _lo(role, s, w):
    return s - w if role == "A" else (s + CLR_SEAM + w if role == "B" else s)


def _hi(role, s, w):
    return s + w if role == "A" else (s - CLR_SEAM - w if role == "B" else s)


def tile(u0, u1, v0, v1, t, rh, edges=None, rt=None, spans=None, holes=None, grid=None):
    """Plate u0..u1 x v0..v1, thickness t (w = 0 visible), ribs to w = t + rh.

    edges[e] for e in u0/u1/v0/v1: 'A' / 'B' = 45 deg scarf seam (the A tile
    leans out over the B tile, both print without support), 'P' = plain edge
    with a rib, None = plain edge.  rt[e] rib thickness, spans[e] = list of
    (a, b) along-edge rib intervals, holes[e] = along-edge positions of pin
    holes through the seam ribs (teardrop, local up = +w).  Seam pins are
    recorded (head on the A rib) in TILE_PINS.
    """
    TILE_PINS.clear()
    edges = edges or {}
    rt = rt or {}
    spans = spans or {}
    holes = holes or {}
    e = {k: edges.get(k) for k in ("u0", "u1", "v0", "v1")}
    big = 50.0
    pu = poly([(_lo(e["u0"], u0, 0), 0), (_hi(e["u1"], u1, 0), 0),
               (_hi(e["u1"], u1, t), t), (_lo(e["u0"], u0, t), t)])
    pv = poly([(_lo(e["v0"], v0, 0), 0), (_hi(e["v1"], v1, 0), 0),
               (_hi(e["v1"], v1, t), t), (_lo(e["v0"], v0, t), t)])
    a = xform(m3d.Manifold.extrude(pu, (v1 - v0) + 2 * big),
              [[1, 0, 0], [0, 0, -1], [0, 1, 0]], (0, v1 + big, 0))
    b = xform(m3d.Manifold.extrude(pv, (u1 - u0) + 2 * big),
              [[0, 0, 1], [1, 0, 0], [0, 1, 0]], (u0 - big, 0, 0))
    plate = a ^ b
    ub0, ub1 = _lo(e["u0"], u0, t), _hi(e["u1"], u1, t)     # back-face extents
    vb0, vb1 = _lo(e["v0"], v0, t), _hi(e["v1"], v1, t)
    parts = [plate]
    cuts = []
    for k, role in e.items():
        if role is None:
            continue
        th = rt.get(k, SEAM_RIB)
        along = (vb0, vb1) if k[0] == "u" else (ub0, ub1)
        for (sa, sb) in spans.get(k, [along]):
            sa, sb = max(sa, along[0]), min(sb, along[1])
            if sb <= sa:
                continue
            if k == "u0":
                parts.append(box(ub0, ub0 + th, sa, sb, t - 0.01, t + rh))
            elif k == "u1":
                parts.append(box(ub1 - th, ub1, sa, sb, t - 0.01, t + rh))
            elif k == "v0":
                parts.append(box(sa, sb, vb0, vb0 + th, t - 0.01, t + rh))
            else:
                parts.append(box(sa, sb, vb1 - th, vb1, t - 0.01, t + rh))
        for pos in holes.get(k, []):
            wz = t + rh / 2
            if k == "u0":
                p, ax = (ub0, pos, wz), (1, 0, 0)
            elif k == "u1":
                p, ax = (ub1 - th, pos, wz), (1, 0, 0)
            elif k == "v0":
                p, ax = (pos, vb0, wz), (0, 1, 0)
            else:
                p, ax = (pos, vb1 - th, wz), (0, 1, 0)
            cuts.append(thru(p, ax, th, up=(0, 0, 1)))
            if role == "A":
                TILE_PINS.append((p, ax, GRIP_SEAM))
    if grid:
        step, th, gh = grid
        for uu in np.arange(ub0 + step, ub1 - step / 2, step):
            parts.append(box(uu - th / 2, uu + th / 2, vb0, vb1, t - 0.01, t + gh))
        for vv in np.arange(vb0 + step, vb1 - step / 2, step):
            parts.append(box(ub0, ub1, vv - th / 2, vv + th / 2, t - 0.01, t + gh))
    m = union(parts)
    if cuts:
        m = m - union(cuts)
    return m


def strip_roles(bounds, k):
    """Scarf roles for tile k of a row of tiles split at `bounds` (ascending u)."""
    n = len(bounds) - 1
    return ("B" if k > 0 else None), ("A" if k < n - 1 else None)


# ---- tile -> world mappings (proper rotations; up = print-up direction) ------------
MAP = {
    "floor": ([[1, 0, 0], [0, -1, 0], [0, 0, -1]], (0, 0, Z_FL), (0, 0, -1)),
    "wall_l": ([[0, 0, 1], [1, 0, 0], [0, 1, 0]], (0, 0, 0), (1, 0, 0)),
    "wall_r": ([[0, 0, -1], [-1, 0, 0], [0, 1, 0]], (W, 0, 0), (-1, 0, 0)),
    "front": ([[-1, 0, 0], [0, 0, 1], [0, 1, 0]], (0, 0, 0), (0, 1, 0)),
    "rear": ([[1, 0, 0], [0, 0, -1], [0, 1, 0]], (0, D, 0), (0, -1, 0)),
    "divider": ([[0, 0, 1], [1, 0, 0], [0, 1, 0]], (DIV_X0, 0, 0), (1, 0, 0)),
    "radframe": ([[1, 0, 0], [0, 0, -1], [0, 1, 0]], (0, RF_Y1, 0), (0, -1, 0)),
}


def place(kind, m):
    """Map a tile to the world and register its seam pins."""
    R, t, _ = MAP[kind]
    R = np.asarray(R, float)
    for (p, ax, grip) in TILE_PINS:
        add_pin("lock", R @ np.asarray(p, float) + np.asarray(t, float), R @ np.asarray(ax, float),
                grip)
    TILE_PINS.clear()
    return xform(m, R, t)


def up_of(kind):
    return MAP[kind][2]


def floor_pin(x, y, kind="lock", grip=None, z_top=None, up=(0, 0, 1), tab=(1, 0, 0)):
    """Pin hole through a flange sitting on the floor, pin registered."""
    zt = Z_FL + (FLANGE_T if kind == "lock" else SVC_T) if z_top is None else z_top
    grip = (GRIP_FLOOR if kind == "lock" else GRIP_SVC) if grip is None else grip
    add_pin(kind, (x, y, zt), (0, 0, -1), grip, "tab" if kind == "service" else "flat", tab=tab)
    return thru((x, y, zt), (0, 0, -1), grip, up=up)



def rail_cs(x, z0):
    w0, w1 = RAIL_W0 / 2, RAIL_W1 / 2
    return poly([(x - w0, z0), (x + w0, z0), (x + w1, z0 + RAIL_H), (x - w1, z0 + RAIL_H)])


def rail_channel(x, y0, y1):
    """Female dovetail cut into a sled base: the rail grown by CLR_SLIDE, open below."""
    cs = rail_cs(x, Z_FL).offset(CLR_SLIDE, m3d.JoinType.Miter) + rect(x - RAIL_W0 / 2 - CLR_SLIDE,
                                                                     x + RAIL_W0 / 2 + CLR_SLIDE,
                                                                     Z_FL - 1.0, Z_FL + 0.5)
    return plane_cut(cs, "y", y0 - 1, y1 + 1)


# ---- fixing points shared by the floor and the parts that pin to it -------------
WALL_PIN_Y = [40.0, 120.0, 250.0, 320.0, 440.0, 520.0]
FRONT_PIN_X = [(FRONT_BODY_X[2] + SLED_X0) / 2]
REAR_PIN_X = [40.0, 100.0, 408.0]
REAR_FLANGE_X = [(RIB_IN + CLR_SLIDE, REAR_X[1]), (BX1 + 6.0, XI1 - WALL_RIB - CLR_SLIDE)]
TRAY = (BX0 - 3.0, BX1 + 1.0, BY0 - 2.0, Y_RI - CLR_SLIDE)
TRAY_PTS = [(BX0 + 3.0, 320.0), (BX1 - 6.0, 320.0), (BX0 + 3.0, 552.0), (BX1 - 6.0, 552.0)]
STAND = (MOD_X0, card_body_x("A")[0] - 3.0, FY0 - 24.0, FY1 + 22.0)    # GPU C/D stand
STAND_PTS = [(STAND[0] + 6, STAND[2] + 6), (STAND[1] - 6, STAND[2] + 6),
             (STAND[0] + 6, STAND[3] - 6), (STAND[1] - 6, STAND[3] - 6)]
LATCH_FAN_X = [40.0, 205.0]             # fan-module flexure latches (nub into the floor)
NUB_Y = (9.0, 12.0)
FEET = [(20.0, 20.0), (W - 20, 20.0), (20.0, D - 20), (W - 20, D - 20)]
GPU_RAIL_Y = [8.0, 156.0, 300.0]
PSU_RAIL_Y = [8.0, SLED_Y1 - 2.0]
RAIL_PIN_STEP = 60.0


def rail_pin_points():
    pts = []
    for (x, ys) in ((GPU_RAIL_X, GPU_RAIL_Y), (PSU_RAIL_X, PSU_RAIL_Y)):
        for a, b in zip(ys, ys[1:]):
            for y in np.arange(a + 20.0, b - 10.0, RAIL_PIN_STEP):
                if not any(abs(y - s) < 9 for s in TILE_Y[1:-1]):
                    pts.append((x, float(y)))
    return pts


def trough_pin_points():
    pts = []
    xr = (TROUGH_R[0] + TROUGH_R[1]) / 2
    for a, b in zip(TROUGH_R_Y, TROUGH_R_Y[1:]):
        pts += [(xr, a + 25.0), (xr, b - 25.0)]
    xl = (LANE[0] + LANE[1]) / 2
    for a, b in zip(LANE_Y, LANE_Y[1:]):
        pts += [(xl, a + 25.0), (xl, b - 25.0)]
    return [p for p in pts if not any(abs(p[1] - s) < 9 for s in TILE_Y[1:-1])]


def floor_points():
    pts = [(XI0 + WALL_RIB / 2, y) for y in WALL_PIN_Y]
    pts += [(XI1 - WALL_RIB / 2, y) for y in WALL_PIN_Y]
    pts += [(x, Y_FI + 5) for x in FRONT_PIN_X]
    pts += [(x, Y_RI - 5) for x in REAR_PIN_X]
    pts += TRAY_PTS + STAND_PTS + rail_pin_points() + trough_pin_points()
    return pts


# ---- floor ------------------------------------------------------------------------
def make_floor():
    tiles = {}
    pts = floor_points()
    for ix in range(2):
        for iy in range(3):
            x0, x1 = TILE_X_FLOOR[ix], TILE_X_FLOOR[ix + 1]
            y0, y1 = TILE_Y[iy], TILE_Y[iy + 1]
            edges = {"u0": "B" if ix else "P", "u1": "A" if ix == 0 else "P",
                     "v0": "B" if iy < 2 else "P", "v1": "A" if iy else "P"}
            seam_y = {0: [60.0, 130.0], 1: [250.0, 330.0], 2: [440.0, 510.0]}[iy]
            seam_x = [30.0, 90.0, 175.0] if ix == 0 else [255.0, 310.0, 380.0]
            holes = {"u1" if ix == 0 else "u0": [-y for y in seam_y],
                     "v0": seam_x if iy < 2 else [], "v1": seam_x if iy else []}
            loc = tile(x0, x1, -y1, -y0, FLOOR_T, FLOOR_RIB, edges, holes=holes,
                       grid=(70.0, 2.0, FLOOR_RIB))
            m = place("floor", loc)
            inside = lambda p, mg=4.0: x0 + mg <= p[0] <= x1 - mg and y0 + 0.5 <= p[1] <= y1 - mg
            add, cut = [], []
            for p in pts:               # pin hole + clear pocket under the plate for the barbs
                if inside(p):
                    cut.append(cyl_z(p[0], p[1], -1.0, Z_FL - FLOOR_T, 6.5))
                    cut.append(thru((p[0], p[1], Z_FL), (0, 0, -1), FLOOR_T))
            for tx in LATCH_FAN_X:  # pockets the fan-module latch nubs drop into
                if x0 < tx < x1 and y0 <= NUB_Y[0] < y1:
                    cut.append(box(tx - 6.5, tx + 6.5, NUB_Y[0] - 0.5, NUB_Y[1] + 5.0,
                                   Z_FL - 3.6, Z_FL + 1))
            for p in FEET:      # 15 mm stick-on rubber feet recess
                if inside(p, 2.0):
                    add.append(cyl_z(p[0], p[1], 0.0, Z_FL, 10.0))
                    cut.append(cyl_z(p[0], p[1], -1.0, 1.5, 7.75))
            if add:
                m = m + union(add)
            if cut:
                m = m - union(cut)
            tiles[f"floor_{'LR'[ix]}{iy + 1}"] = m
    return tiles


# ---- floor rails -------------------------------------------------------------------
def make_rails():
    out = {}
    for name, x, ys in (("rail_gpu", GPU_RAIL_X, GPU_RAIL_Y), ("rail_psu", PSU_RAIL_X, PSU_RAIL_Y)):
        for k, (a, b) in enumerate(zip(ys, ys[1:])):
            m = plane_cut(rail_cs(x, Z_FL), "y", a, b)
            for yy in (a, b):           # lead-in chamfers so the sleds find the rail
                m = m - plane_cut(poly([(x - 20, Z_FL + RAIL_H - 2.0), (x + 20, Z_FL + RAIL_H - 2.0),
                                        (x + 20, Z_FL + RAIL_H + 1), (x - 20, Z_FL + RAIL_H + 1)]),
                                  "y", yy - 4, yy + 4)
            cut = [csk_pin((px, py, Z_FL + RAIL_H), (0, 0, -1), GRIP_RAIL)
                   for (px, py) in rail_pin_points() if abs(px - x) < 1 and a + 6 < py < b - 6]
            if cut:
                m = m - union(cut)
            out[f"{name}_{k + 1}"] = m
    return out


# ---- side walls --------------------------------------------------------------------
WALL_SEAM_Z = [28.0, 163.5]
END_PIN_Z = [Z_FL + 10.0, 160.0]


def _vgroove(x_face, inward, y0, y1, d, zc):
    """45 deg V-groove (depth d) along y in the face x = x_face, cut towards `inward`."""
    h = d + 0.6
    return plane_cut(poly([(x_face - inward * 0.6, zc - h), (x_face + inward * d, zc),
                           (x_face - inward * 0.6, zc + h)]), "y", y0, y1)


def make_wall(side):
    kind = "wall_l" if side == "L" else "wall_r"
    up = up_of(kind)
    parts = {}
    bounds = WALL_Y if side == "L" else [-y for y in reversed(WALL_Y)]
    # left wall: ribs skip the band the GPU fans slide through; right wall: skip the C14
    rib_z = [(Z_FL, FAN_BAND[0]), (FAN_BAND[1], Z_WT)] if side == "L" else \
        [(Z_FL, 30.0), (64.0, Z_WT)]
    for k in range(3):
        u0, u1 = bounds[k], bounds[k + 1]
        r0, r1 = strip_roles(bounds, k)
        edges = {"u0": r0 or "P", "u1": r1 or "P"}
        rt = {"u0": SEAM_RIB if r0 else WALL_RIB, "u1": SEAM_RIB if r1 else WALL_RIB}
        spans = {e: rib_z for e in ("u0", "u1")}
        holes = {e: WALL_SEAM_Z for e in ("u0", "u1") if edges[e] != "P"}
        loc = tile(u0, u1, Z_FL, H, WALL_T, WALL_RIB, edges, rt=rt, spans=spans, holes=holes)
        ub0, ub1 = _lo(edges["u0"], u0, WALL_T), _hi(edges["u1"], u1, WALL_T)
        loc = loc + box(ub0, ub1, Z_FL, Z_FL + FLANGE_T, WALL_T - 0.01, WALL_T + WALL_RIB)
        loc = loc + box(ub0, ub1, Z_WT - 4, Z_WT, WALL_T - 0.01, WALL_T + 4)
        m = place(kind, loc)
        y0, y1 = (u0, u1) if side == "L" else (-u1, -u0)
        xc = XI0 + WALL_RIB / 2 if side == "L" else XI1 - WALL_RIB / 2
        cut = [_vgroove(XI0 if side == "L" else XI1, -1 if side == "L" else 1, y0 - 6, y1 + 6,
                        VGROOVE + CLR_SLIDE, Z_WT + LID_T / 2)]
        for y in WALL_PIN_Y:
            if y0 + 6 < y < y1 - 6:
                cut.append(floor_pin(xc, y, up=up))
        for z in END_PIN_Z:
            if abs(y0 - Y_FI) < 1e-6:
                cut.append(thru((xc, Y_FI, z), (0, 1, 0), WALL_RIB, up=up))
            if abs(y1 - Y_RI) < 1e-6:
                cut.append(thru((xc, Y_RI, z), (0, -1, 0), WALL_RIB, up=up))
        m = m - union(cut)
        parts[f"wall_{side}{k + 1}"] = m
    return parts


# ---- front panel -----------------------------------------------------------------
GRIP_CORNER = PANEL_T + WALL_RIB
FACE_T, FACE_FL, FACE_LIP = PANEL_T, 3.0, 8.0
BEZ_T = 4.0
GBEZ = (232.0, 116.0)                   # GPU fan bezel (on the fan-module faceplate)
GBEZ_MAG = [(sx * 110.0, sz * 52.0) for sx in (-1, 1) for sz in (-1, 1)]
TOP_AP = (PSU_RAIL_X, 136.0, 140.0, 22.0)   # intake above the PSU bay
TBEZ = (150.0, 30.0)
TBEZ_MAG = [(sx * 69.0, 0.0) for sx in (-1, 1)]
BTN_D = 12.2
STATUS_Z = 160.0
BTN_X = [285.0, 305.0]
USB_X = 335.0
LIGHT_X = (352.0, 405.0)
LIGHT_Z = (158.0, 162.0)
RACK_SLOT_Z = [RACK_Z0 + 22.225 + k * U for k in range(4)]
HANDLE_Z = [40.0, 136.0]
GRIP_FACE = FACE_FL + PANEL_T


def gpu_bay():
    """Opening the GPU fan module slides through (x, z), before clearance."""
    return rect(MOD_X0, FAN_XC[1] + GFAN / 2, Z_FL, FAN_BAND[0] + 0.5) + \
        rect(FAN_XC[0] - GFAN / 2, FAN_XC[1] + GFAN / 2, FAN_BAND[0], FAN_BAND[1])


def psu_bay():
    return rect(SLED_X0, SLED_X1, Z_FL, PSU_TOP + 2.0)


PSU_FACE_PINS = [(PSU_X0 + 26.0, PSU_TOP + 2.0 + CLR_SLIDE + 4.0),
                 (PSU_X0 + PSU_W - 26.0, PSU_TOP + 2.0 + CLR_SLIDE + 4.0)]


def cut_y(cs, y0=-1.0, y1=PANEL_T + 1.0):
    return plane_cut(cs, "y", y0, y1)


def magnet_pockets(xc, zc, offs, y_face, inward):
    d, h = MAG_D + 2 * CLR_PRESS, MAG_T + 0.2
    out = []
    for (dx, dz) in offs:
        y0 = y_face - 0.01 if inward > 0 else y_face - h
        out.append(hole((xc + dx, y0, zc + dz), (0, 1, 0), h + 0.01, d))
    return out


def clip_x(xa, xb, ranges):
    out = []
    for (a, b) in ranges:
        a, b = max(a, xa), min(b, xb)
        if b > a:
            out.append((a, b))
    return out


def make_front():
    bounds = [-x for x in reversed(FRONT_BODY_X)]
    top = [(FAN_BAND[1] + 2.0, Z_WT)]
    parts = {}
    for k in range(3):
        u0, u1 = bounds[k], bounds[k + 1]
        r0, r1 = strip_roles(bounds, k)
        edges = {"u0": r0, "u1": r1}
        # k = 0: PSU tile (full rib on its u1 side); k = 1, 2: frame tiles over the GPU bay
        spans = {"u0": top, "u1": top} if k else {"u0": top, "u1": [(Z_FL, Z_WT)]}
        holes = {e: [166.0] for e in ("u0", "u1") if edges[e]}
        loc = tile(u0, u1, Z_FL, H, PANEL_T, PANEL_RIB, edges, holes=holes, spans=spans)
        m = place("front", loc)
        xb0, xb1 = -_hi(edges["u1"], u1, PANEL_T), -_lo(edges["u0"], u0, PANEL_T)
        x0, x1 = -u1, -u0
        add, cut = [], []
        for (a, b) in clip_x(xb0, xb1, [(FAN_XC[1] + GFAN / 2 + 1.0, SLED_X0 - 1.0)]):
            add.append(box(a, b, PANEL_T - 0.01, PANEL_T + 10, Z_FL, Z_FL + FLANGE_T))
        for x in FRONT_PIN_X:
            if x0 + 4 < x < x1 - 4:
                cut.append(floor_pin(x, Y_FI + 5))
        for x in (XI0 + WALL_RIB / 2, XI1 - WALL_RIB / 2):
            if x0 < x < x1:
                for z in END_PIN_Z:
                    cut.append(csk_pin((x, 0.0, z), (0, 1, 0), GRIP_CORNER))
        cut.append(cut_y(gpu_bay().offset(CLR_SLIDE, m3d.JoinType.Miter)))
        if k == 2:
            add += ear(left=True)
            cut += ear_cuts(left=True)
        if k == 0:          # PSU bay, intake above it, status strip at the top
            add += ear(left=False)
            cut += ear_cuts(left=False)
            cut.append(cut_y(psu_bay().offset(CLR_SLIDE, m3d.JoinType.Miter)))
            for (x, z) in PSU_FACE_PINS:
                cut.append(thru((x, -FACE_FL, z), (0, 1, 0), GRIP_FACE))
            xc, zc, w, h = TOP_AP
            cut.append(cut_y(hex_grid(rrect(w, h, 6).translate((xc, zc)))))
            cut += magnet_pockets(xc, zc, TBEZ_MAG, 0.0, +1)
            for x in BTN_X:
                cut.append(cut_y(circle(BTN_D / 2, 64).translate((x, STATUS_Z))))
            cut.append(cut_y(rrect(13.0, 7.0, 2.0).translate((USB_X, STATUS_Z))))
            for x in (USB_X - 12.5, USB_X + 12.5):
                cut.append(cut_y(circle(1.3, 32).translate((x, STATUS_Z))))
            cut.append(cut_y(rrect(LIGHT_X[1] - LIGHT_X[0], LIGHT_Z[1] - LIGHT_Z[0], 1.0)
                             .translate((sum(LIGHT_X) / 2, sum(LIGHT_Z) / 2))))
        if add:
            m = m + union(add)
        m = m - union(cut)
        parts[f"front_{k + 1}"] = clean(m)
    return parts


def ear(left):
    s = -1 if left else 1
    xe = 0.0 if left else W
    xa, xb = sorted((xe, xe + s * EAR_W))
    xs = sorted((xe, xe + s * 8.0))
    return [box(xa, xb, 0.0, PANEL_T, 0.0, H), box(xs[0], xs[1], 0.0, 12.0, 0.0, H)]


def ear_cuts(left):
    xc = W / 2 + (-1 if left else 1) * EAR_HOLE_X
    out = [cut_y(rrect(10.0, 7.0, 3.5).translate((xc, z))) for z in RACK_SLOT_Z]
    xi = -4.0 if left else W + 4.0
    out += [thru((xi, 0.0, z), (0, 1, 0), 12.0) for z in HANDLE_Z]
    return out


# ---- rear panel: GPU bracket windows + slot rail, board I/O, exhaust, C14 --------------
EXH = [(258.0, 118.0), (352.0, 118.0)]   # 92 mm exhaust fans on the OUTSIDE (x, z)
IEC = ((REAR_X[3] + XI1 - WALL_RIB) / 2 + 1.0, 45.0)
RAIL_REAR = (Y_BRK - 1.0 - CLR_SLIDE - 3.0, BRK_TOP - 8.0)   # bracket-tab ledge (y0, z0)
CLAMP_X = (RIB_IN + 0.5, 245.0)         # gpu_clamp bar pressing all 4 bracket tabs
CLAMP_POSTS = [113.1, 238.5]
CLAMP_T = 4.0
CLAMP_Y = Y_RI - 7.0                    # clamp pins: head stays clear of the rear panel


def make_rear():
    parts = {}
    for k in range(len(REAR_X) - 1):
        u0, u1 = REAR_X[k], REAR_X[k + 1]
        r0, r1 = strip_roles(REAR_X, k)
        edges = {"u0": r0, "u1": r1}
        holes = {e: [166.0] for e in ("u0", "u1") if edges[e]}     # above the slot rail
        loc = tile(u0, u1, Z_FL, Z_WT, PANEL_T, PANEL_RIB, edges, holes=holes,
                   spans={e: [(Z_CARD0 + CARD_H + 0.2, Z_WT)] for e in ("u0", "u1")})
        m = place("rear", loc)
        xb0, xb1 = _lo(edges["u0"], u0, PANEL_T), _hi(edges["u1"], u1, PANEL_T)
        add, cut = [], []
        for (a, b) in clip_x(xb0, xb1, REAR_FLANGE_X):
            add.append(box(a, b, Y_RI - 10.0, Y_RI + 0.01, Z_FL, Z_FL + FLANGE_T))
        for (a, b) in clip_x(xb0, xb1, [(RIB_IN + CLR_SLIDE, CLAMP_X[1])]):   # bracket-tab ledge
            add.append(box(a, b, RAIL_REAR[0], Y_RI + 0.01, RAIL_REAR[1], BRK_TOP))
        for px in CLAMP_POSTS:      # posts the clamp bar is service-pinned to
            if xb0 + 6 < px < xb1 - 6:
                add.append(box(px - 5, px + 5, RAIL_REAR[0] - 8.0, Y_RI + 0.01, RAIL_REAR[1],
                               BRK_TOP + 1.0))
                cut.append(thru((px, CLAMP_Y, BRK_TOP + 1.0), (0, 0, -1), BRK_TOP + 1.0 - RAIL_REAR[1]))
        for x in REAR_PIN_X:
            if xb0 + 4 < x < xb1 - 4:
                cut.append(floor_pin(x, Y_RI - 5))
        for x in (XI0 + WALL_RIB / 2, XI1 - WALL_RIB / 2):
            if u0 < x < u1:
                for z in END_PIN_Z:
                    cut.append(csk_pin((x, D, z), (0, -1, 0), GRIP_CORNER))
        ry = (Y_RI - 12, D + 1)
        for c in CARDS:             # bracket windows, bracket slots + tab pins in the slot rail
            bx0, bx1 = card_body_x(c)
            bc = (bx0 + bx1) / 2
            if xb0 < bc < xb1:
                cut.append(plane_cut(rect(bx0, bx1, Z_CARD0 - 4.0, RAIL_REAR[1] - 2.0), "y",
                                     Y_RI - 1, D + 1))
                cut.append(box(bc - BRK_W / 2 - 0.6, bc + BRK_W / 2 + 0.6, Y_BRK - 1.0 - CLR_SLIDE,
                               Y_BRK + CLR_SLIDE, RAIL_REAR[1] - 1, BRK_TOP + 1))
        if xb0 < IO_X1 - 10 and IO_X1 - IO_W + 10 < xb1:
            cut.append(plane_cut(rrect(IO_W + 2, IO_H + 2, 1.0)
                                 .translate((IO_X1 - IO_W / 2, IO_Z0 + IO_H / 2)), "y", *ry))
        for (x, z) in EXH:
            if xb0 + 45 < x < xb1 - 45:
                cut.append(plane_cut(hex_grid(circle(44.0).translate((x, z))), "y", Y_RI - 1, D + 1))
                for sx in (-1, 1):
                    for sz in (-1, 1):
                        cut.append(plane_cut(circle(FAN_RIVET_HOLE / 2, 32)
                                             .translate((x + sx * 41.25, z + sz * 41.25)),
                                             "y", Y_RI - 1, D + 1))
        if xb0 < IEC[0] < xb1:      # snap-in C14, panel thinned to SNAP_PANEL_T round it
            cut.append(plane_cut(rrect(IEC_SNAP[0] + 4, IEC_SNAP[1] + 4, 2).translate(IEC), "y",
                                 Y_RI - 1, D - SNAP_PANEL_T))
            cut.append(plane_cut(rrect(*IEC_SNAP, 1.0).translate(IEC), "y", Y_RI - 1, D + 1))
        if add:
            m = m + union(add)
        m = m - union(cut)
        parts[f"rear_{k + 1}"] = m
    return parts


# ---- lid: one sliding hatch of dovetail-puzzle tiles -------------------------------------
PUZZLE_NECK, PUZZLE_HEAD, PUZZLE_DEPTH = 8.0, 14.0, 8.0
LATCH_X = [80.0, 320.0]
LID_Z0, LID_Z1 = Z_WT, H


def puzzle_tab(along, s, axis, sign):
    n, hd, dp = PUZZLE_NECK / 2, PUZZLE_HEAD / 2, PUZZLE_DEPTH
    pts = [(along - n, 0.0), (along + n, 0.0), (along + hd, dp), (along - hd, dp)]
    if axis == "y":
        return poly([(a, s + sign * b) for a, b in pts])
    return poly([(s + sign * b, a) for a, b in pts])


def chevrons(xc, yc, n=3, step=14.0):
    out = []
    for i in range(n):
        y = yc + (i - (n - 1) / 2) * step
        out.append(poly([(xc - 16, y - 8), (xc, y + 8), (xc + 16, y - 8), (xc + 16, y - 14),
                         (xc, y + 2), (xc - 16, y - 14)]))
    return out


def lid_tile_cs(ix, iy):
    xs = HATCH_X
    x0, x1 = xs[ix], xs[ix + 1]
    y0, y1 = HATCH_Y[iy], HATCH_Y[iy + 1]
    cs = rect(x0, x1, y0, y1)
    xs_tabs = list(np.arange(x0 + 25.0, x1 - 20.0, 55.0))
    ys_tabs = list(np.arange(y0 + 30.0, y1 - 20.0, 60.0))
    if iy < 2:
        for a in xs_tabs:
            cs = cs + puzzle_tab(a, y1, "y", +1)
    if iy > 0:
        for a in xs_tabs:
            cs = cs - puzzle_tab(a, y0, "y", +1).offset(CLR_PUZZLE, m3d.JoinType.Miter)
    if ix == 0:
        for a in ys_tabs:
            cs = cs + puzzle_tab(a, x1, "x", +1)
    else:
        for a in ys_tabs:
            cs = cs - puzzle_tab(a, x0, "x", +1).offset(CLR_PUZZLE, m3d.JoinType.Miter)
    return cs


def vtongue(x_edge, outward, y0, y1):
    zc = (LID_Z0 + LID_Z1) / 2
    return plane_cut(poly([(x_edge - outward * 0.01, LID_Z0 + 0.5), (x_edge + outward * VGROOVE, zc),
                           (x_edge - outward * 0.01, LID_Z1 - 0.5)]), "y", y0, y1)


def make_lids():
    parts = {}
    for ix in range(2):
        for iy in range(3):
            y0, y1 = HATCH_Y[iy], HATCH_Y[iy + 1]
            m = plane_cut(lid_tile_cs(ix, iy), "z", LID_Z0, LID_Z1)
            add, cut = [], []
            ty0 = y0 + (0 if iy == 0 else PUZZLE_DEPTH + 1)
            if ix == 0:
                add.append(vtongue(HATCH_X[0], -1, ty0, y1))
            else:
                add.append(vtongue(HATCH_X[-1], +1, ty0, y1))
            if iy == 2:
                for lx in LATCH_X:
                    if HATCH_X[ix] + 12 < lx < HATCH_X[ix + 1] - 12:
                        hw = LATCH_W / 2
                        ya = D - LATCH_L
                        slot = rect(lx - hw - 2, lx + hw + 2, ya, D + 1) - \
                            rect(lx - hw, lx + hw, ya - 1, D + 1)
                        cut.append(plane_cut(slot, "z", LID_Z0 - 1, LID_Z1 + 1))
                        cut.append(box(lx - hw - 0.01, lx + hw + 0.01, D - 4.0, D + 1,
                                       LID_Z1 - 1.2, LID_Z1 + 1))
                        add.append(box(lx - hw, lx + hw, Y_RI - CLR_SLIDE - 3.0, Y_RI - CLR_SLIDE,
                                       LID_Z0 - LATCH_DROP, LID_Z0 + 0.01))
            if iy == 1:
                xc = (HATCH_X[ix] + HATCH_X[ix + 1]) / 2
                for c in chevrons(xc, (y0 + y1) / 2):
                    cut.append(plane_cut(c, "z", H - 0.6, H + 1))
            if add:
                m = m + union(add)
            if cut:
                m = m - union(cut)
            parts[f"lid_{ix + 1}{iy + 1}"] = m
    return parts


def latch_lips():
    return union([box(lx - LATCH_W / 2 - 1, lx + LATCH_W / 2 + 1, Y_RI - 6, Y_RI + 1,
                      LID_Z0 - LATCH_DROP - 1, LID_Z0 + 0.02) for lx in LATCH_X])



# ---- PSU sled -------------------------------------------------------------------------------
def faceplate(bay, pins, grille, lip=FACE_LIP, mags=None, mag_c=(0.0, 0.0)):
    """Plate filling a front bay (y 0..5) + flange on the panel front (y -3..0)."""
    plate = plane_cut(bay, "y", 0.0, FACE_T)
    fl = bay.offset(CLR_SLIDE + lip, m3d.JoinType.Round, circular_segments=16) ^ \
        rect(0.4, W - 0.4, Z_FL, H)
    m = plate + plane_cut(fl, "y", -FACE_FL, 0.0)
    cut = [plane_cut(grille, "y", -FACE_FL - 1, FACE_T + 1)] if grille is not None else []
    for (x, z) in pins:
        add_pin("service", (x, -FACE_FL, z), (0, 1, 0), GRIP_FACE, "tab", tab=(1, 0, 0))
        cut.append(thru((x, -FACE_FL, z), (0, 1, 0), FACE_FL, up=(0, 1, 0)))
    if mags:
        cut += magnet_pockets(mag_c[0], mag_c[1], mags, -FACE_FL, +1)
    x0, z0, x1, z1 = bay.bounds()
    xc = (x0 + x1) / 2
    cut.append(box(xc - 30, xc + 30, -FACE_FL - 1, 2.0, z0 + 3, z0 + 11))   # finger pull
    return m - union(cut)


def make_psu_sled():
    bay = psu_bay()
    grille = hex_grid(rrect(SLED_X1 - SLED_X0 - 24, PSU_TOP - Z_FL - 34, 6)
                      .translate(((SLED_X0 + SLED_X1) / 2, (PSU_TOP + Z_FL) / 2 + 8)))
    m = faceplate(bay, PSU_FACE_PINS, grille)
    base = box(SLED_X0, SLED_X1, FACE_T - 0.01, SLED_Y1, Z_FL, PSU_Z0)
    base = base - rail_channel(PSU_RAIL_X, FACE_T - 1, SLED_Y1 + 1)
    base = base - plane_cut(rrect(110.0, 120.0, 10).translate((PSU_RAIL_X, 140.0)), "z",
                            PSU_Z0 - 1.6, PSU_Z0 + 1)
    m = m + base
    m = m + box(SLED_X0, PSU_X0 - CLR_SLIDE, FACE_T, PSU_Y1, PSU_Z0 - 0.01, PSU_Z0 + 30)   # side lip
    m = m + box(PSU_X0, PSU_X0 + PSU_W, PSU_Y0 - 4.0 - CLR_SLIDE, PSU_Y0 - CLR_SLIDE,
                PSU_Z0 - 0.01, PSU_Z0 + 8)                                              # front stop
    bp = box(SLED_X0, SLED_X1, PSU_Y1 + CLR_SLIDE, PSU_Y1 + CLR_SLIDE + 5, PSU_Z0 - 0.01,
             PSU_TOP + 3)
    ry = (PSU_Y1 - 1, PSU_Y1 + 7)
    bp = bp - plane_cut(rrect(110.0, 64.0, 4).translate((PSU_X0 + 60.0, PSU_Z0 + 44.0)), "y", *ry)
    bp = bp - plane_cut(rrect(36.0, 30.0, 4).translate(PSU_AC), "y", *ry)      # AC inlet access
    for (px, pz) in PSU_HOLES:      # optional ATX screws (slotted)
        x, z = PSU_X0 + PSU_W - px, PSU_Z0 + pz
        slot = rect(x - 6, x + 6, z - 2, z + 2) + circle(2.0, 32).translate((x - 6, z)) + \
            circle(2.0, 32).translate((x + 6, z))
        bp = bp - plane_cut(slot, "y", *ry)
    return m + bp


# ---- board tray and GPU C/D stand (nylon snap standoffs, service-pinned) -----------------
def board_holes():
    return [(BX1 - v, BY1 - u) for (u, v) in MATX_HOLES]


def snap_seat(x, y, z_top):
    """4 mm hole thinned to SNAP_PANEL_T from below for a nylon snap-in standoff."""
    return cyl_z(x, y, z_top - 9.0, z_top + 1.0, SNAP_STANDOFF_HOLE / 2, 32) + \
        cyl_z(x, y, Z_FL - 1.0, z_top - SNAP_PANEL_T, 5.0, 32)


def make_tray():
    x0, x1, y0, y1 = TRAY
    zt = Z_FL + SVC_T
    m = box(x0, x1, y0, y1, Z_FL, zt)
    m = m - union([plane_cut(rrect(w, h, 8).translate((cx, cy)), "z", Z_FL - 1, zt + 1)
                   for (cx, cy, w, h) in [(210.0, 395.0, 90, 120), (330.0, 395.0, 90, 120),
                                          (210.0, 515.0, 90, 50), (330.0, 515.0, 90, 50)]])
    cut = [snap_seat(x, y, zt) for (x, y) in board_holes()]
    cut += [floor_pin(x, y, "service", tab=(-1, 0, 0) if x > W / 2 else (1, 0, 0))
            for (x, y) in TRAY_PTS]
    return m - union(cut)


def adapter_holes(k):
    xs = SLOT_X[k]
    ax, ay = ADAPTER
    yc = (FY0 + FY1) / 2
    return [(xs + sx * (ax / 2 - 4), yc + sy * (ay / 2 - 4)) for sx in (-1, 1) for sy in (-1, 1)]


def make_gpu_clamp():
    """Bar across all four bracket tabs, service-pinned to the two posts on the rear panel."""
    z0 = BRK_TOP + 1.0
    m = box(CLAMP_X[0], CLAMP_X[1], RAIL_REAR[0] - 8.0 + 0.4, Y_BRK + 0.4, z0, z0 + CLAMP_T)
    m = m - plane_cut(rect(CLAMP_X[0] + 40, CLAMP_X[1] - 40, RAIL_REAR[0] - 7.0, RAIL_REAR[0] - 1.0),
                      "z", z0 - 1, z0 + CLAMP_T + 1)          # save plastic, keep stiff edges
    for s in REAR_X[1:3]:           # notches round the rear seam ribs
        m = m - box(s - 6.0, s + 15.0, Y_RI - 10.5, Y_BRK + 1, z0 - 1, z0 + CLAMP_T + 1)
    for px in CLAMP_POSTS:
        add_pin("service", (px, CLAMP_Y, z0 + CLAMP_T), (0, 0, -1),
                CLAMP_T + BRK_TOP + 1.0 - RAIL_REAR[1], "tab", tab=(0, -1, 0))
        m = m - thru((px, CLAMP_Y, z0 + CLAMP_T), (0, 0, -1), CLAMP_T)
    return m


OCU_GUIDE_X = STAND[1] - 4.0


def make_gpu_stand():
    """Plate under the C/D OCuLink slot boards: same standoffs as the board, so the
    cards sit at slot height; OCuLink cable guide along its right edge."""
    x0, x1, y0, y1 = STAND
    zt = Z_FL + SVC_T
    m = box(x0, x1, y0, y1, Z_FL, zt)
    m = m - plane_cut(rrect(26.0, 80.0, 6).translate((SLOT_X["C"] + 28.0, (y0 + y1) / 2)), "z",
                      Z_FL - 1, zt + 1)
    cut = [snap_seat(x, y, zt) for k in ("C", "D") for (x, y) in adapter_holes(k)]
    cut += [floor_pin(x, y, "service", tab=(0, 1, 0) if y < (y0 + y1) / 2 else (0, -1, 0))
            for (x, y) in STAND_PTS]
    # OCuLink guide: two hooks the cables clip under, along the right edge
    hook = poly([(0, 0), (8, 0), (8, 14), (2, 14), (2, 18), (-3, 18), (-3, 11), (4, 11), (4, 4),
                 (0, 4)])
    for y in (y0 + 30.0, y1 - 30.0):
        m = m + plane_cut(hook.translate((OCU_GUIDE_X - 4, zt - 0.01)), "y", y - 5, y + 5)
    return m - union(cut)


# ---- GPU fan module: fan_face (faceplate + 2 fans + loft start) + fan_duct ---------------------
UPSTAND_T, BLOCK_T = 8.0, 9.6
JOINT_X = [(MOD_X0, MOD_X0 + 10.0), (MOD_X1 - 10.0, MOD_X1)]
ZS = Z_FL + SLED_T
JOINT_Z = ZS + 4.6
JOINT_TOP = FAN_BAND[0] - 0.6           # joint ribs stay under the sliding fans
FACE_FOOT = (12.0, -FACE_FL, 8.0)        # width, y0, y1 of the faceplate pin feet


def duct_sections():
    """(inner, outer) 2D sections at the fan flange and at the card seat / sleeve."""
    fx0, fx1 = FAN_XC[0] - FAN_R, FAN_XC[1] + FAN_R
    inlet = rrect(fx1 - fx0, 2 * FAN_R, 6).translate(((fx0 + fx1) / 2, GZ))
    ex0, ex1 = ENV_X0, ENV_X1
    seat = rrect(ex1 - ex0 - 2 * LIP, CARD_H - 2 * LIP, 3).translate(((ex0 + ex1) / 2, GZ))
    slv = rrect(ex1 - ex0 + 2 * SLV_CLR, CARD_H + 2 * SLV_CLR, 3).translate(((ex0 + ex1) / 2, GZ))
    o = DUCT_WALL
    return inlet, seat, slv, inlet.offset(o, m3d.JoinType.Round), slv.offset(o, m3d.JoinType.Round)


def loft_y(stations):
    """Loft along +y through (x, z) sections [(cs, y), ...]."""
    out = []
    for (a, ya), (b, yb) in zip(stations, stations[1:]):
        if yb > ya:
            out.append(m3d.Manifold.batch_hull([plane_cut(a, "y", ya, ya + 1e-3),
                                                plane_cut(b, "y", yb - 1e-3, yb)]))
    return union(out)


def _mix(a, b, t):
    """Section at fraction t between two rrect-like sections (hull of scaled bounds)."""
    ax0, az0, ax1, az1 = a.bounds()
    bx0, bz0, bx1, bz1 = b.bounds()
    x0, x1 = ax0 + (bx0 - ax0) * t, ax1 + (bx1 - ax1) * t
    z0, z1 = az0 + (bz0 - az0) * t, az1 + (bz1 - az1) * t
    return rrect(x1 - x0, z1 - z0, 4).translate(((x0 + x1) / 2, (z0 + z1) / 2))


Y_FL1 = Y_PUSH1 + DFLANGE_T
Y_SEAT = Y_TAIL - LIP - SLV_CLR
Y_SLV1 = Y_TAIL + SLV
T_SPLIT = (Y_SPLIT - Y_FL1) / (Y_SEAT - Y_FL1)


def fan_flange():
    fr = rect(FAN_XC[0] - GFAN / 2, FAN_XC[1] + GFAN / 2, GZ - GFAN / 2, GZ + GFAN / 2)
    m = plane_cut(fr, "y", Y_PUSH1, Y_FL1)
    h = GFAN_HOLE / 2
    for xc in FAN_XC:
        m = m - plane_cut(circle(FAN_R).translate((xc, GZ)), "y", Y_PUSH1 - 1, Y_FL1 + 1)
        for sx in (-1, 1):
            for sz in (-1, 1):
                m = m - plane_cut(circle(FAN_RIVET_HOLE / 2, 32).translate((xc + sx * h, GZ + sz * h)),
                                  "y", Y_PUSH1 - 1, Y_FL1 + 1)
    return m


def joint_ribs(m, y0, y1, pin_from_y, axis):
    """Upstand ribs along the base sides (y0..y1) with lock-pin holes at the y1 / y0 end
    and barb windows; the pins come from the neighbour's joint blocks."""
    end = y1 if axis[1] < 0 else y0
    for (a, b) in JOINT_X:
        m = m + box(a, b, y0, y1, ZS - 0.01, JOINT_TOP)
        x = (a + b) / 2
        add_pin("lock", (x, pin_from_y, JOINT_Z), axis, BLOCK_T + CLR_SLIDE + UPSTAND_T)
        m = m - thru((x, end, JOINT_Z), axis, UPSTAND_T, up=(0, 1, 0))
        w0 = end + axis[1] * UPSTAND_T
        m = m - box(a - 1, b + 1, min(w0, w0 + axis[1] * 8), max(w0, w0 + axis[1] * 8),
                    JOINT_Z - 5, JOINT_Z + 5)
    return m


def joint_blocks(m, y0, y1):
    for (a, b) in JOINT_X:
        m = m + box(a, b, y0, y1, Z_FL, JOINT_TOP)
        m = m - thru(((a + b) / 2, y0, JOINT_Z), (0, 1, 0), y1 - y0, up=(0, 1, 0))
    return m


def make_fan_plate():
    """Front of the GPU fan module: faceplate, grilles, air collars, pin feet, base arm."""
    bay = gpu_bay()
    m = faceplate(bay, [], None, lip=MOD_FLANGE, mags=GBEZ_MAG, mag_c=(sum(FAN_XC) / 2, GZ))
    for xc in FAN_XC:
        m = m - plane_cut(circle(FAN_R).translate((xc, GZ)), "y", -FACE_FL - 1, FACE_T + 1)
        m = m + plane_cut(circle(FAN_R + 0.5).translate((xc, GZ)) -
                          hex_grid(circle(FAN_R).translate((xc, GZ))), "y", -FACE_FL, FACE_T)
        m = m + plane_cut((circle(FAN_R + 2.0) - circle(FAN_R)).translate((xc, GZ)), "y",
                          FACE_T - 0.01, Y_PUSH0 - 1.0)
    y1 = Y_PUSH1 - CLR_SLIDE
    m = m + (box(MOD_X0, MOD_X1, FACE_T - 0.01, y1, Z_FL, ZS) -
             rail_channel(GPU_RAIL_X, FACE_T - 1, y1 + 1))
    m = joint_ribs(m, FACE_T - 0.01, y1, Y_PUSH1 + BLOCK_T, (0, -1, 0))
    for tx in LATCH_FAN_X:          # flexure latch: tongue in the base, nub drops into the floor
        m = m - box(tx - 7.2, tx + 7.2, -FACE_FL - 1, 45.0, Z_FL - 1, ZS + 1)
        m = m - box(tx - 7.2, tx + 7.2, -FACE_FL - 1, FACE_T + 0.01, Z_FL - 1, ZS + 4)
        m = m + box(tx - 6.0, tx + 6.0, -FACE_FL, 45.01, Z_FL + 2.0, ZS)
        m = m + box(tx - 7.21, tx + 7.21, 44.99, 47.0, Z_FL, ZS)
        nub = poly([(NUB_Y[0], Z_FL - 2.6), (NUB_Y[1], Z_FL - 2.6), (NUB_Y[1] + 4.6, Z_FL + 2.01),
                    (NUB_Y[0], Z_FL + 2.01)])
        m = m + plane_cut(nub, "x", tx - 6.0, tx + 6.0)
        m = m - box(tx - 5.0, tx + 5.0, -FACE_FL - 1, -FACE_FL + 2.0, Z_FL + 1.0, Z_FL + 3.5)
    return clean(m)


def make_fan_face():
    """Fan flange (2 x 120 riveted on) + first half of the loft + base on the rail."""
    inlet, seat, slv, inlet_o, slv_o = duct_sections()
    mid_i, mid_o = _mix(inlet, seat, T_SPLIT), _mix(inlet_o, slv_o, T_SPLIT)
    inner = loft_y([(inlet, Y_FL1 - 1.0), (mid_i, Y_SPLIT + 1.0)])
    m = (loft_y([(inlet_o, Y_FL1 - 0.5), (mid_o, Y_SPLIT)]) - inner) + fan_flange()
    m = m + (box(MOD_X0, MOD_X1, Y_PUSH1, Y_SPLIT, Z_FL, ZS) -
             rail_channel(GPU_RAIL_X, Y_PUSH1 - 1, Y_SPLIT + 1))
    m = joint_blocks(m, Y_PUSH1, Y_PUSH1 + BLOCK_T)
    m = joint_ribs(m, Y_PUSH1 + BLOCK_T + 12.0, Y_SPLIT, Y_SPLIT + CLR_SLIDE + BLOCK_T, (0, -1, 0))
    for x in (MOD_X0 + 30, GPU_RAIL_X - 30, GPU_RAIL_X + 30, MOD_X1 - 30):   # webs base -> duct
        m = m + (box(x - 1.5, x + 1.5, Y_FL1, Y_SPLIT, ZS - 0.1, GZ) - inner)
    return clean(m)


def make_fan_duct():
    inlet, seat, slv, inlet_o, slv_o = duct_sections()
    mid_i, mid_o = _mix(inlet, seat, T_SPLIT), _mix(inlet_o, slv_o, T_SPLIT)
    y0 = Y_SPLIT + CLR_SLIDE
    outer = loft_y([(mid_o, y0), (slv_o, Y_SEAT), (slv_o, Y_SLV1)])
    inner = loft_y([(mid_i, y0 - 1), (seat, Y_SEAT), (slv, Y_TAIL), (slv, Y_SLV1 + 1)])
    m = outer - inner
    zb, zt = Z_CARD0 - SLV_CLR, Z_CARD0 + CARD_H + SLV_CLR
    for a, b in zip(CARDS, CARDS[1:]):      # gap fins between neighbouring card tails
        g0, g1 = card_body_x(a)[1] + 0.4, card_body_x(b)[0] - 0.4
        fin = box(g0, g1, Y_TAIL, Y_SLV1, zb, zt) + \
            m3d.Manifold.batch_hull([box(g0, g1, Y_TAIL - 0.01, Y_TAIL, zb, zt),
                                     box((g0 + g1) / 2 - 1, (g0 + g1) / 2 + 1, Y_TAIL - (g1 - g0),
                                         Y_TAIL - (g1 - g0) + 0.01, zb, zt)])
        m = m + (fin ^ outer)
    for c in CARDS:                 # slots for the 8-pin plugs at the card tails (top)
        bx0, bx1 = card_body_x(c)
        xc = (bx0 + bx1) / 2
        m = m - box(xc - PWR_NOTCH_W / 2, xc + PWR_NOTCH_W / 2, Y_SEAT - 12, Y_SLV1 + 1,
                    zt - LIP - 1, zt + DUCT_WALL + 2)
    base = box(MOD_X0, MOD_X1, y0, Y_TAIL - 4.0, Z_FL, ZS) - \
        rail_channel(GPU_RAIL_X, y0 - 1, Y_TAIL)
    m = m + base
    for (a, b) in JOINT_X:
        m = m + box(a, b, y0, y0 + BLOCK_T, Z_FL, JOINT_TOP)
        m = m - thru(((a + b) / 2, y0, JOINT_Z), (0, 1, 0), BLOCK_T, up=(0, 1, 0))
    for x in (MOD_X0 + 30, GPU_RAIL_X - 30, GPU_RAIL_X + 30, MOD_X1 - 30):
        m = m + (box(x - 1.5, x + 1.5, y0, Y_TAIL - 6.0, ZS - 0.1, GZ) - inner)
    return clean(m)


# ---- cable management: troughs, combs, AC strain relief --------------------------------
def trough(x0, x1, y0, y1, ties=True):
    """U channel: 6 mm base lock-pinned to the floor, 2 mm walls, zip-tie slots, comb notches."""
    zb = Z_FL + FLANGE_T
    m = box(x0, x1, y0, y1, Z_FL, zb) + box(x0, x0 + 2, y0, y1, zb - 0.01, zb + TROUGH_H) + \
        box(x1 - 2, x1, y0, y1, zb - 0.01, zb + TROUGH_H)
    cut = []
    if ties:
        for y in np.arange(y0 + 40.0, y1 - 20.0, 50.0):
            cut.append(box(x0 + 3, x1 - 3, y - 2, y + 2, Z_FL - 1, zb + 1)
                       - box((x0 + x1) / 2 - 2, (x0 + x1) / 2 + 2, y - 3, y + 3, Z_FL - 2, zb + 2))
    for (px, py) in trough_pin_points():
        if x0 < px < x1 and y0 + 6 < py < y1 - 6:
            add_pin("lock", (px, py, zb), (0, 0, -1), GRIP_FLOOR)
            cut.append(thru((px, py, zb), (0, 0, -1), FLANGE_T))
    return m - union(cut) if cut else m


def make_troughs():
    out = {}
    x0, x1 = TROUGH_R
    for k, (a, b) in enumerate(zip(TROUGH_R_Y, TROUGH_R_Y[1:])):
        m = trough(x0, x1, a, b)
        if k == len(TROUGH_R_Y) - 2:        # AC strain relief at the inlet end
            zb = Z_FL + FLANGE_T
            cl = box(x0 + 2, x1 - 2, b - 14, b, zb - 0.01, zb + 16) - \
                plane_cut(circle(4.2, 48).translate(((x0 + x1) / 2, zb + 9)) +
                          rect((x0 + x1) / 2 - 3.0, (x0 + x1) / 2 + 3.0, zb + 9, zb + 20),
                          "y", b - 15, b + 1)
            m = m + cl
        out[f"trough_r_{k + 1}"] = m
    x0, x1 = LANE
    for k, (a, b) in enumerate(zip(LANE_Y, LANE_Y[1:])):
        out[f"trough_gpu_{k + 1}"] = trough(x0, x1, a, b)
    return out


def make_comb(width, slots):
    """Clip-on comb: hooks over both trough walls, finger slots hold the cables apart."""
    zb = Z_FL + FLANGE_T + TROUGH_H
    w = width                       # sits on both wall tops, legs inside the walls
    prof = rect(0.0, w, zb - 0.01, zb + 3.0) + rect(2.2, 4.2, zb - 6, zb) + \
        rect(w - 4.2, w - 2.2, zb - 6, zb)
    fingers = [rect(2 + (w - 4) * (i + 1) / (slots + 1) - 1, 2 + (w - 4) * (i + 1) / (slots + 1) + 1,
                    zb - 26, zb) for i in range(slots)]
    return plane_cut(union_cs([prof] + fingers), "y", 0.0, 8.0)


COMB_Y = {"trough_r": [300.0, 470.0], "trough_gpu": [70.0, 230.0]}



# ---- bezels, light pipe, handles, coupons ---------------------------------------------
def bezel(xc, zc, w, h, grille, mags, chev, y_back=0.0):
    plate = rrect(w, h, 10).translate((xc, zc)) - hex_grid(grille, 8.0, 1.6)
    m = plane_cut(plate, "y", y_back - BEZ_T, y_back)
    if chev:
        m = m + plane_cut(union_cs(chev), "y", y_back - BEZ_T - 1.5, y_back - BEZ_T + 0.01)
    return m - union(magnet_pockets(xc, zc, mags, y_back, -1))


def chevron_v(xc, zc, ang, size=14.0, th=2.4):
    a = math.radians(ang)
    n1 = np.array([math.cos(a + 3 * math.pi / 4), math.sin(a + 3 * math.pi / 4)])
    n2 = np.array([math.cos(a - 3 * math.pi / 4), math.sin(a - 3 * math.pi / 4)])
    c = np.array([xc, zc])
    arms = []
    for n in (n1, n2):
        p0, p1 = c, c + n * size
        d = (p1 - p0) / np.linalg.norm(p1 - p0)
        q = np.array([-d[1], d[0]]) * th / 2
        arms.append(poly([tuple(p0 - q - d * th / 2), tuple(p1 - q), tuple(p1 + q),
                          tuple(p0 + q - d * th / 2)]))
    return arms[0] + arms[1] + circle(th / 2 * 1.2, 16).translate((xc, zc))


def make_bezel_gpu():
    xc = sum(FAN_XC) / 2
    grille = circle(FAN_R).translate((FAN_XC[0], GZ)) + circle(FAN_R).translate((FAN_XC[1], GZ))
    chev = [chevron_v(xc, GZ + sz * 46.0, 90 * sz, 7.0, 2.0) for sz in (-1, 1)]
    return bezel(xc, GZ, GBEZ[0], GBEZ[1], grille, GBEZ_MAG, chev, -FACE_FL)


def make_bezel_top():
    xc, zc, w, h = TOP_AP
    bw, bh = TBEZ
    chev = [chevron_v(xc + dx, zc, 90, 3.6, 1.6) for dx in (-60.0, 60.0)]
    return bezel(xc, zc, bw, bh, rrect(w - 16, h - 4, 6).translate((xc, zc)), TBEZ_MAG, chev)


def make_light_pipe():
    x0, x1 = LIGHT_X
    z0, z1 = LIGHT_Z
    m = box(x0 + 1.2, x1 - 1.2, 0.2, PANEL_T, z0 + 0.1, z1 - 0.1)
    return m + box(x0 - 3, x1 + 3, PANEL_T, PANEL_T + 2, z0 - 3, z1 + 3)


def make_handle(left):
    xa, xb = (-8.0, 0.0) if left else (W, W + 8.0)
    outer = rrect(32.0, 116.0, 10).translate((-16.0, 88.0))
    inner = rrect(23.0, 80.0, 6).translate((-10.5, 88.0))
    m = plane_cut(outer - inner, "x", xa, xb)
    xc = (xa + xb) / 2
    up = (1, 0, 0) if left else (-1, 0, 0)
    cut = []
    for z in HANDLE_Z:
        add_pin("lock", (xc, -11.0, z), (0, 1, 0), 11.0 + 12.0)
        cut.append(hole((xc, -33.0, z), (0, 1, 0), 34.0, PIN_HOLE, up))
        cut.append(hole((xc, -33.0, z), (0, 1, 0), 22.0, PIN_HEAD_D + 0.6, up))
    return m - union(cut)


def make_coupons():
    """Seam + pin, dovetail rail + channel, puzzle joint, magnet pocket, standoff seat."""
    a = tile(0.0, 60.0, 0.0, 40.0, PANEL_T, 8.0, {"u1": "A"}, holes={"u1": [20.0]})
    TILE_PINS.clear()
    b = tile(60.0, 120.0, 0.0, 40.0, PANEL_T, 8.0, {"u0": "B"}, holes={"u0": [20.0]})
    TILE_PINS.clear()
    a = a - cyl_z(28.0, 20.0, -1.0, PANEL_T - SNAP_PANEL_T, 5.0, 32) - \
        cyl_z(28.0, 20.0, -1.0, PANEL_T + 1, SNAP_STANDOFF_HOLE / 2, 32)
    a = a - hole((12.0, 34.0, -0.01), (0, 0, 1), MAG_T + 0.2, MAG_D + 2 * CLR_PRESS)
    b = b + plane_cut(rail_cs(100.0, 0.0), "y", 0.0, 40.0).translate((0, 0, PANEL_T - 0.01))
    blk = box(-40.0, -2.0, 0.0, 40.0, 0.0, SLED_T)
    ch = plane_cut(rail_cs(-21.0, 0.0).offset(CLR_SLIDE, m3d.JoinType.Miter) +
                   rect(-21 - RAIL_W0 / 2 - CLR_SLIDE, -21 + RAIL_W0 / 2 + CLR_SLIDE, -1.0, 0.5),
                   "y", -1.0, 41.0)
    a = a + (blk - ch)
    a = a + plane_cut(rect(0, 30, 50, 80) + puzzle_tab(15.0, 80.0, "y", +1), "z", 0, LID_T)
    b = b + plane_cut(rect(0, 30, 80, 110) - puzzle_tab(15.0, 80.0, "y", +1)
                      .offset(CLR_PUZZLE, m3d.JoinType.Miter), "z", 0, LID_T).translate((60.0, -35.0, 0))
    return a, b


# ---- context (preview + fit checks only) ------------------------------------------------
def fan_model(xc, zc, y0, size, t):
    r = size / 2 - 2.5
    fr = plane_cut((rrect(size, size, 4) - circle(r)).translate((xc, zc)), "y", y0, y0 + t)
    hub = hole((xc, y0, zc), (0, 1, 0), t, size / 3)
    blades = union(box(-1, 1, y0 + 3, y0 + t - 3, size / 6 - 1, r - 1).rotate((0, a, 0))
                   .translate((xc, 0, zc)) for a in range(0, 360, 40))
    return fr + hub + blades


def cable(points, r):
    segs = []
    for p, q in zip(points, points[1:]):
        segs.append(m3d.Manifold.batch_hull([m3d.Manifold.sphere(r, 16).translate(p),
                                             m3d.Manifold.sphere(r, 16).translate(q)]))
    return union(segs)


def context():
    c = {}
    c["psu"] = (box(PSU_X0, PSU_X0 + PSU_W, PSU_Y0, PSU_Y1, PSU_Z0, PSU_TOP), "#2b2b2b")
    for k, xc in enumerate(FAN_XC):
        c[f"push_fan_{k + 1}"] = (fan_model(xc, GZ, Y_PUSH0, GFAN, GFAN_T), "#444444")
    for k, (x, z) in enumerate(EXH):
        c[f"exhaust_{k + 1}"] = (fan_model(x, z, D, 92.0, 25.0), "#444444")
    cpu = (BX1 - CPU_FROM_EDGE, BY1 - CPU_FROM_IO)
    board = box(BX0, BX1, BY0, BY1, BZ, BZ_TOP)
    for i in range(4):
        y = cpu[1] - 55 - i * 9.0
        board = board + box(BX1 - 150, BX1 - 17, y - 2.5, y + 2.5, BZ_TOP, BZ_TOP + 33)
    board = board + box(IO_X1 - IO_W + 4, IO_X1 - 4, BY1 - 30, BY1 + 2, BZ_TOP, BZ_TOP + 40)
    for k in ("A", "B"):
        xs = SLOT_X[k]
        board = board + (box(xs - 3.5, xs + 3.5, FY0 - 3, FY1 + 3, BZ_TOP, Z_CARD0 - 0.01) -
                         box(xs - 1, xs + 1, FY0, FY1, Z_CARD0 - 8.5, Z_CARD0 + 1))
    c["board"] = (board, "#1f5c3a")
    cw, cd, ch = COOLER
    c["cpu_cooler"] = (box(cpu[0] - cw / 2, cpu[0] + cw / 2, cpu[1] - cd / 2, cpu[1] + cd / 2,
                           BZ_TOP, BZ_TOP + ch), "#9a9a9a")
    for k in CARDS:
        bx0, bx1 = card_body_x(k)
        xs = SLOT_X[k]
        card = box(bx0, bx1, Y_TAIL, Y_BRK - 5, Z_CARD0, Z_CARD0 + CARD_H)
        card = card + box(xs - 0.8, xs + 0.8, FY0, FY1, Z_CARD0 - 8, Z_CARD0 + 0.01)
        bc = (bx0 + bx1) / 2
        card = card + box(bc - BRK_W / 2, bc + BRK_W / 2, Y_BRK - 1, Y_BRK, Z_CARD0 - 12, BRK_TOP)
        card = card + box(bc - 9, bc + 9, RAIL_REAR[0] + 0.4, Y_BRK, BRK_TOP, BRK_TOP + 1)
        c[f"gpu_{k}"] = (card, "#b9a66b")
    for k in ("C", "D"):            # OCuLink slot boards
        xs = SLOT_X[k]
        ax, ay = ADAPTER
        yc = (FY0 + FY1) / 2
        sb = box(xs - ax / 2, xs + ax / 2, yc - ay / 2, yc + ay / 2, BZ, BZ_TOP)
        sb = sb + (box(xs - 3.5, xs + 3.5, FY0 - 3, FY1 + 3, BZ_TOP, Z_CARD0 - 0.01) -
                   box(xs - 1, xs + 1, FY0, FY1, Z_CARD0 - 8.5, Z_CARD0 + 1))
        c[f"oculink_board_{k}"] = (sb, "#7a3b8f")
    # cables (preview only: shown, not interference-checked)
    zb = Z_FL + FLANGE_T + 4
    xr = (TROUGH_R[0] + TROUGH_R[1]) / 2
    xl = (LANE[0] + LANE[1]) / 2
    acx, acz = PSU_AC
    c["cable_ac"] = (cable([(IEC[0], Y_RI - 4, IEC[1]), (xr, Y_RI - 20, zb + 4), (xr, 300.0, zb + 4),
                            (360.0, 290.0, zb + 4), (300.0, 270.0, zb + 4), (330.0, 258.0, zb + 4),
                            (acx, PSU_Y1 + 6, acz)], 4.0), "#101010")
    c["cable_eps"] = (cable([(xl, PSU_Y0 - 10, zb), (xl, 290.0, zb), (300.0, 300.0, zb),
                             (xr, 300.0, zb + 10), (xr, BY1 - 20, zb + 10), (BX1 - 15, BY1 - 15, BZ_TOP + 6)],
                            4.0), "#202020")
    c["cable_24pin"] = (cable([(xl, PSU_Y0 - 8, zb + 6), (xl, 285.0, zb + 6), (BX1 - 20, BY0 - 8, zb + 6),
                               (BX1 - 20, BY0 + 4, BZ_TOP + 10)], 5.0), "#202020")
    gp = []
    for i, k in enumerate(CARDS):
        bx0, bx1 = card_body_x(k)
        tx = (bx0 + bx1) / 2
        gp.append(cable([(xl - 3 + i * 2, PSU_Y0 - 6, zb + 2 + i * 3),
                         (xl - 3 + i * 2, Y_TAIL - 10, zb + 2 + i * 3),
                         (xl, Y_TAIL - 10, 162.0), (tx, Y_TAIL - 6, 164.0),
                         (tx, Y_TAIL + 8, Z_CARD0 + CARD_H - 4)], 3.0))
    c["cable_gpu"] = (union(gp), "#303030")
    oc = []
    for k in ("C", "D"):
        xs = SLOT_X[k]
        oc.append(cable([(BX0 + 40.0 + (10 if k == "C" else 0), BY0 + 60, BZ_TOP + 6),
                         (OCU_GUIDE_X, BY0 + 60, Z_FL + SVC_T + 8),
                         (OCU_GUIDE_X, (FY0 + FY1) / 2, Z_FL + SVC_T + 8),
                         (xs + ADAPTER[0] / 2, (FY0 + FY1) / 2, BZ_TOP + 3)], 3.0))
    c["cable_oculink"] = (union(oc), "#4060c0")
    return c


CABLES = ("cable_ac", "cable_eps", "cable_24pin", "cable_gpu", "cable_oculink")


# ---- build ------------------------------------------------------------------------------
GROUP_EX = {"floor": (0, 0, -60), "wall_L": (-80, 0, 0), "wall_R": (80, 0, 0),
            "front": (0, -90, 0), "rear": (0, 90, 0), "lid": (0, 200, 0), "psu": (0, -280, 0),
            "tray": (0, 0, 40), "fanmod": (0, -360, 0), "gpu": (0, 0, 150), "rails": (0, 0, 20),
            "cables": (0, 0, 30), "bezel": (0, -130, 0), "trim": (0, -110, 0), "pins": (0, 0, 0)}


def build():
    """name -> (manifold world, print-up, colour, group)."""
    PINS.clear()
    P = {}

    def add(d, up, color, group):
        for k, m in d.items():
            P[k] = (m, up, color, group)

    add(make_floor(), up_of("floor"), "#5b6670", "floor")
    add(make_rails(), (0, 0, 1), "#c26a2e", "rails")
    add(make_troughs(), (0, 0, 1), "#c26a2e", "cables")
    add(make_wall("L"), up_of("wall_l"), "#6f7c87", "wall_L")
    add(make_wall("R"), up_of("wall_r"), "#6f7c87", "wall_R")
    add(make_front(), up_of("front"), "#30363d", "front")
    add(make_rear(), up_of("rear"), "#30363d", "rear")
    add(make_lids(), (0, 0, -1), "#9fb0bd", "lid")
    P["psu_sled"] = (make_psu_sled(), (0, 0, 1), "#d9a400", "psu")
    P["board_tray"] = (make_tray(), (0, 0, 1), "#c26a2e", "tray")
    P["gpu_stand"] = (make_gpu_stand(), (0, 0, 1), "#c26a2e", "gpu")
    P["gpu_clamp"] = (make_gpu_clamp(), (0, 0, 1), "#d9a400", "gpu")
    P["fan_plate"] = (make_fan_plate(), (0, 1, 0), "#d9a400", "fanmod")
    P["fan_face"] = (make_fan_face(), (0, 1, 0), "#d9a400", "fanmod")
    P["fan_duct"] = (make_fan_duct(), (0, 1, 0), "#d9a400", "fanmod")
    P["bezel_gpu"] = (make_bezel_gpu(), (0, -1, 0), "#e8b400", "fanmod")
    P["bezel_top"] = (make_bezel_top(), (0, -1, 0), "#c26a2e", "bezel")
    P["light_pipe"] = (make_light_pipe(), (0, -1, 0), "#e8f4ff", "trim")
    P["handle_L"] = (make_handle(True), (1, 0, 0), "#30363d", "trim")
    P["handle_R"] = (make_handle(False), (-1, 0, 0), "#30363d", "trim")
    xr0, xr1 = TROUGH_R
    xl0, xl1 = LANE
    for nm, (x0, x1), ys in (("trough_r", (xr0, xr1), COMB_Y["trough_r"]),
                             ("trough_gpu", (xl0, xl1), COMB_Y["trough_gpu"])):
        for i, y in enumerate(ys):
            P[f"comb_{nm[7:]}_{i + 1}"] = (make_comb(x1 - x0, 3).translate((x0, y, 0)), (0, 1, 0),
                                          "#e04080", "cables")
    return P


# ---- print orientation / export -------------------------------------------------------------
UP_ROT = {(0, 0, 1): (0, 0, 0), (0, 0, -1): (180, 0, 0), (0, 1, 0): (90, 0, 0),
          (0, -1, 0): (-90, 0, 0), (1, 0, 0): (0, -90, 0), (-1, 0, 0): (0, 90, 0)}
SHELL = ("floor", "wall_L", "wall_R", "front", "rear", "lid")


def bounds(m):
    b = m.bounding_box()
    return np.array(b[:3]), np.array(b[3:])


def orient(m, up):
    m = m.rotate(UP_ROT[tuple(int(v) for v in up)])
    lo, hi = bounds(m)
    m = m.translate((-lo[0], -lo[1], -lo[2]))
    lo, hi = bounds(m)
    if (hi - lo)[1] > (hi - lo)[0]:
        m = m.rotate((0, 0, 90))
        lo, hi = bounds(m)
        m = m.translate((-lo[0], -lo[1], 0))
    return m


def foot_relief(m, ears=False):
    lo, hi = bounds(m)
    cs = m.slice(0.05)
    if cs.is_empty():
        return m
    big = box(lo[0] - 20, hi[0] + 20, lo[1] - 20, hi[1] + 20, FOOT_RELIEF, hi[2] + 1)
    inset = m3d.Manifold.extrude(cs.offset(-FOOT_RELIEF, m3d.JoinType.Round, circular_segments=16),
                                 FOOT_RELIEF + 0.01)
    out = (m ^ big) + ((m - big) ^ inset)
    if ears:
        x0, y0, x1, y1 = cs.bounds()
        out = out + union([cyl_z(x, y, 0.0, BRIM_EAR_T, BRIM_EAR_R, 32)
                           for x in (x0, x1) for y in (y0, y1)])
    return out


def to_trimesh(m):
    import trimesh
    mesh = m.to_mesh()
    return trimesh.Trimesh(np.asarray(mesh.vert_properties)[:, :3],
                           np.asarray(mesh.tri_verts), process=False)


def overhang(tm):
    n = tm.face_normals
    c = tm.triangles_center
    down = (n[:, 2] < -math.cos(math.radians(OVERHANG_DEG)) - 1e-3) & (c[:, 2] > 0.6)
    return tm.area_faces[down].sum()


def ok(flag):
    return "OK" if flag else "FAIL"


# ---- checks ---------------------------------------------------------------------------------
EXPECTED_TOUCH = {("gpu_A", "board"), ("gpu_B", "board"), ("gpu_C", "oculink_board_C"),
                  ("gpu_D", "oculink_board_D"), ("pins_tab", "rear_1"), ("pins_tab", "rear_2"),
                  ("pins_tab", "rear_3"), ("pins_tab", "gpu_A"), ("pins_tab", "gpu_B"),
                  ("pins_tab", "gpu_C"), ("pins_tab", "gpu_D")}
FANMOD = ["fan_plate", "fan_face", "fan_duct", "bezel_gpu", "push_fan_1", "push_fan_2"]
LIDS = [f"lid_{i}{j}" for i in (1, 2) for j in (1, 2, 3)]
# label: (members, direction, steps, skip-prefixes (removed first), pre-slide y)
PATHS = {"GPU fan module -> front": (FANMOD, (0, -1, 0), (0, 5, 80, 200, 330), ["lid", "floor"], 0.0),
         "PSU sled -> front": (["psu_sled", "psu"], (0, -1, 0), (0, 5, 80, 180, AC_SLACK), [], 0.0),
         "lid -> rear": (LIDS, (0, 1, 0), (0, 5, 100, 300, 600), [], 0.0)}
for _k in CARDS:
    PATHS[f"GPU {_k} -> up"] = ([f"gpu_{_k}"], (0, 0, 1), (0, 5, 40, 100, 180),
                                ["lid", "fan_", "bezel_gpu", "push_fan", "gpu_clamp"], 0.0)
PATHS["board tray -> fwd, up"] = (["board_tray", "board", "cpu_cooler"], (0, 0, 1),
                                  (0, 5, 30, 80, 140, 200),
                                  ["lid", "fan_", "bezel_gpu", "push_fan", "gpu_"], -15.0)


def bb_overlap(a, b, pad=0.0):
    return np.all(a[0] - pad < b[1]) and np.all(b[0] - pad < a[1])


def check_fit(P, C, PN):
    print("-- fit (assembled): interference between parts, hardware and pins")
    allp = {k: v[0] for k, v in P.items()}
    allp.update({k: v[0] for k, v in C.items() if k not in CABLES})
    allp.update({f"pins_{k}": v for k, v in PN.items()})
    names = sorted(allp)
    bb = {k: bounds(allp[k]) for k in names}
    bad = 0
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            if (a, b) in EXPECTED_TOUCH or (b, a) in EXPECTED_TOUCH:
                continue
            if not bb_overlap(bb[a], bb[b]):
                continue
            v = (allp[a] ^ allp[b]).volume()
            if v > 0.5:
                bad += 1
                print(f"  {a:>16} x {b:<16} overlap {v:8.1f} mm3  FAIL")
    print(f"  {len(names)} bodies, {bad} interferences -> {ok(bad == 0)}")
    print("-- fit: clearances at mating pairs (target)")
    pairs = [("fan_duct", "gpu_A", 0.0), ("fan_duct", "gpu_D", 0.0), ("fan_face", "rail_gpu_1", CLR_SLIDE),
             ("psu_sled", "rail_psu_1", CLR_SLIDE), ("fan_face", "trough_gpu_1", 0.5),
             ("psu_sled", "trough_gpu_1", CLR_SLIDE), ("board_tray", "trough_r_1", CLR_SLIDE),
             ("gpu_D", "wall_L3", 0.3), ("gpu_B", "cpu_cooler", 3.0), ("cpu_cooler", "lid_22", 2.0),
             ("floor_L1", "floor_R1", CLR_SEAM / math.sqrt(2))]
    for a, b, tgt in pairs:
        if a in allp and b in allp:
            g = allp[a].min_gap(allp[b], 10.0)
            print(f"  {a:>12} - {b:<12} gap {g:5.2f} (>= {tgt:.2f}) {ok(g >= tgt - 0.05)}")
    print("-- service: slide / lift paths")
    lips = latch_lips()
    for label, (members, dirn, steps, skip, sy) in PATHS.items():
        mv = union([allp[k] for k in members if k in allp])
        if label.startswith("lid"):
            mv = mv - lips
        mb = bounds(mv)
        hit = []
        for s in steps:
            dv = np.array(dirn, float) * s + np.array([0, sy, 0])
            moved = mv.translate(tuple(dv))
            mbb = (mb[0] + dv, mb[1] + dv)
            for k, f in allp.items():
                if k in members or k.startswith("pins") or any(k.startswith(p) for p in skip):
                    continue
                if label.startswith("lid") and k.startswith("lid"):
                    continue
                if not bb_overlap(mbb, bb[k]):
                    continue
                if (moved ^ f).volume() > 0.5:
                    hit.append((s, k))
        hit = sorted(set(hit))
        print(f"  {label:>24}: " + ("clear" if not hit else
                                     ", ".join(f"{k}@{s:.0f}" for s, k in hit[:6])) +
              f"  {ok(not hit)}")


def report_design(P):
    print("-- layout")
    print(f"  body {W:.0f} x {D:.0f} x {H:.0f} mm (4U {4 * U:.1f}); ears -> {W + 2 * EAR_W:.1f} wide")
    for k in CARDS:
        bx0, bx1 = card_body_x(k)
        how = "board slot" if k in "AB" else "OCuLink slot board"
        print(f"  GPU {k}: slot x {SLOT_X[k]:.0f}, body x {bx0:.0f}..{bx1:.0f} ({how})")
    gaps = [card_body_x(b)[0] - card_body_x(a)[1] for a, b in zip(CARDS, CARDS[1:])]
    fan_a = 2 * math.pi * (FAN_R ** 2 - HUB_R ** 2)
    print(f"  GPU air: 2 x 120x38 push, annulus {fan_a / 100:.0f} cm2; card gaps "
          f"{', '.join(f'{g:.0f}' for g in gaps)} mm (gap fins in the sleeve)")
    print(f"  heights: card top {Z_CARD0 + CARD_H:.1f}, fans {GZ + GFAN / 2:.1f}, cooler "
          f"{BZ_TOP + COOLER[2]:.1f}, lid underside {Z_WT:.1f} -> "
          f"{ok(BZ_TOP + COOLER[2] < Z_WT - 1 and GZ + GFAN / 2 < Z_WT)}")
    ac_run = abs(Y_RI - 300) + 120 + 60
    print(f"  AC lead: run ~{ac_run:.0f} mm + {AC_SLACK:.0f} mm slack loop for the sled -> "
          f"use a {math.ceil((ac_run + AC_SLACK) / 100) / 10:.1f} m C13 lead")
    E = 2000.0
    I = LID_T ** 3 / 12
    q = LID_T * 1.07e-6 * 9.81
    span = XI1 - XI0
    sag = 5 * q * span ** 4 / (384 * E * I)
    print(f"  lid self-weight sag over {span:.0f} mm: {sag:.1f} mm -> {ok(sag < 2.5)}")
    strain = 1.5 * LID_T * LATCH_DROP / LATCH_L ** 2
    print(f"  lid latch: {LATCH_DROP:.0f} mm lift on {LATCH_L:.0f} mm -> strain {100 * strain:.1f} % "
          f"{ok(strain < 0.03)}")
    print("-- snap pins")
    for (kind, head, grip, d), n in sorted(pin_types().items()):
        lip = (PIN_LIP if kind == "lock" else SPIN_LIP) * d / PIN_D
        lip = TAB_LIP if kind == "tab" else lip
        arm_t = d / 2 - PIN_SLOT * d / PIN_D / 2
        L = grip + PIN_CLR - min(0.8, grip * 0.15)
        strain = 1.5 * arm_t * (lip + 0.15) / L ** 2
        print(f"  {kind:>7} {head:>4} d{d:.0f} grip {grip:5.2f}: {n:3d} pcs, arm strain "
              f"{100 * strain:.1f} % -> {ok(strain < 0.03)}")
    vol = sum(v[0].volume() for v in P.values()) / 1000
    print(f"  printed volume {vol:.0f} cm3 solid ~ {vol * 1.07 * 0.55 / 1000:.1f} kg ASA")


def pin_name(kind, head, grip, d):
    return f"pin_{kind}_{head}_d{d:.0f}_g{grip:g}".replace(".", "p")


def export(P, C, PN):
    print("-- STL export (print orientation)")
    for d in ("stl", "preview"):
        os.makedirs(os.path.join(OUT, d), exist_ok=True)
        for f in os.listdir(os.path.join(OUT, d)):
            if f.endswith(".stl"):
                os.remove(os.path.join(OUT, d, f))
    entries = []
    fails = 0
    worst = []
    done = set()
    for name, (m, up, color, group) in sorted(P.items()):
        key = name.rsplit("_", 1)[0] if name.startswith("comb_") else name
        core = orient(m, up)
        if key not in done:
            done.add(key)
            pm = foot_relief(core, ears=group in SHELL)
            if SHRINK != 1.0:
                pm = pm.scale((SHRINK, SHRINK, SHRINK))
            tm = to_trimesh(pm)
            tm.export(os.path.join(OUT, "stl", f"{key}.stl"))
            lo, hi = bounds(core)
            ext = hi - lo
            fits = ext[0] <= BED_MAX and ext[1] <= BED_MAX and ext[2] <= BED_MAX
            fails += not fits
            oh = overhang(tm)
            worst.append((oh, key))
            print(f"  {key:>14} {np.round(ext, 1)} {m.volume() / 1000:6.0f} cm3  "
                  f"watertight={tm.is_watertight} bed {ok(fits)}  down>{OVERHANG_DEG:.0f}deg {oh:6.0f} mm2")
        to_trimesh(m).export(os.path.join(OUT, "preview", f"{name}.stl"))
        entries.append({"name": name, "file": f"preview/{name}.stl", "color": color,
                        "group": group, "ctx": False, "ex": GROUP_EX.get(group, (0, 0, 0))})
    for (kind, head, grip, d), n in sorted(pin_types().items()):
        pm = foot_relief(orient(pin_body(kind, head, grip, d), (1, 0, 0)))
        tm = to_trimesh(pm)
        tm.export(os.path.join(OUT, "stl", f"{pin_name(kind, head, grip, d)}.stl"))
        print(f"  {pin_name(kind, head, grip, d):>30} x{n:<3} watertight={tm.is_watertight}")
    a, b = make_coupons()
    for nm, cm in (("tolerance_coupon_a", a), ("tolerance_coupon_b", b)):
        to_trimesh(foot_relief(orient(cm, (0, 0, 1)))).export(os.path.join(OUT, "stl", f"{nm}.stl"))
    for name, (m, color) in sorted(C.items()):
        to_trimesh(m).export(os.path.join(OUT, "preview", f"{name}.stl"))
        g = ("fanmod" if name in FANMOD else "gpu" if name.startswith(("gpu_", "oculink")) else
             "psu" if name == "psu" else "cables" if name in CABLES else "ctx")
        entries.append({"name": name, "file": f"preview/{name}.stl", "color": color,
                        "group": g, "ctx": True, "ex": GROUP_EX.get(g, (0, 0, 0))})
    for kind, m in PN.items():
        to_trimesh(m).export(os.path.join(OUT, "preview", f"pins_{kind}.stl"))
        entries.append({"name": f"pins_{kind}", "file": f"preview/pins_{kind}.stl",
                        "color": {"lock": "#e04040", "service": "#30a0e0", "tab": "#40c060"}[kind],
                        "group": "pins", "ctx": False, "ex": (0, 0, 0)})
    with open(os.path.join(OUT, "preview", "manifest.json"), "w") as fh:
        json.dump({"title": "4U rack case: B660-G + 4 x V100 + air cooler + 1600 W (clips + rails)",
                   "size": [W, D, H], "parts": entries}, fh, indent=1)
    worst.sort(reverse=True)
    print("  largest down-facing areas (bridges): " + ", ".join(f"{n} {a:.0f}" for a, n in worst[:6]))
    print(f"  {len(done)} printed part types ({len(P)} parts) + {sum(pin_types().values())} pins "
          f"({len(pin_types())} types) + 2 coupons, bed {ok(fails == 0)}")


def main():
    P = build()
    C = context()
    PN = placed_pins()
    report_design(P)
    check_fit(P, C, PN)
    export(P, C, PN)


if __name__ == "__main__":
    main()
