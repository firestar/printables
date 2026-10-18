"""Bed air duct: 6" flex hose -> flat duct along the middle of a king mattress,
under the covers, ending in a louvred diffuser toward the head.  Printable on
a 256 x 256 bed (Bambu P1S), PETG (room / cooled air only).

  floor hose (6") -> ADAPTER (hangs at the foot face, round -> flat)
                  -> ELBOW (2 x ELBOW_HALF, bolted; wraps the mattress foot edge)
                  -> N_PLAIN x SEGMENT + N_VENT x SEGMENT_VENTED  (on the mattress)
                  -> DIFFUSER (top + side louvres, aimed toward the feet)

Duct profile: flat 'stadium' W x H with 45 deg pointed flanks (teardrop), so
every part, including the elbow halves lying on their cut face, prints
without supports.  Straight parts print standing (socket down), the profile
sits diagonally on the bed.  Two longitudinal webs inside resist crushing.

Joints: every part's foot-side end is a SOCKET, the head-side end is PLAIN and
slides SOCK mm into the next socket (CLR per side; tape it if it whistles).
Vented segments carry a dovetail track on each flank with a SLIDER: push it
toward the head to close the slots, toward the feet to open them.

World frame: x along the bed from the foot edge (x=0) to the head, y across,
z up, mattress top at z=0.  Parts are exported in print orientation; preview/
has assembled copies + the mattress for context.
Run: PYTHONPATH=../../.pydeps python3 bed_air.py
"""
import json
import math
import os

import numpy as np
import manifold3d as m3d

OUT = os.path.dirname(os.path.abspath(__file__))
SEG = 96

# ---- parameters (mm) -------------------------------------------------------
BED = 256.0            # printer bed (Bambu P1S)
BED_MARGIN = 3.0
CLR = 0.4              # socket clearance per side

MATTRESS_L = 2032.0    # king: 80" x 76"
MATTRESS_W = 1930.0
MATTRESS_T = 300.0     # preview only
HEAD_GAP = 200.0       # min free mattress past the diffuser nose

W = 320.0              # duct outer width (diagonal footprint 236 of 250 mm)
H = 70.0               # duct outer height (the hump under the covers)
TIP = 3.0              # half-height of the flat at each flank tip
WALL = 2.4
SOCK = 25.0            # socket depth = insertion
TAP = WALL + CLR       # 45 deg socket shoulder
SEG_LEN = 245.0        # printed length of a straight segment
PITCH = SEG_LEN - SOCK
N_PLAIN = 3            # foot end
N_VENT = 4             # torso end
WEB_X = (-80.0, 0.0, 80.0)  # longitudinal anti-crush webs
WEB_T = 1.6

# vent track + slider (vented segments)
DEPTH = 2.2            # track depth into the outer surface
PAD = 2.2              # local inner wall thickening under the track
SCLR = 0.3             # slider clearance
SLOT_H = 12.0          # slot half-height (profile height direction)
SLOT_L = 10.0          # slot length along the duct, pitch 2 x SLOT_L
TRAVEL = SLOT_L        # open <-> closed

# inlet adapter
HOSE_R = 75.0          # spigot OD 150 for 6" (152 ID) flex duct
BEAD = 2.0
SPIG_L = 50.0
LOFT_L = 150.0

# elbow over the mattress foot edge
ELB_RI = 25.0          # inner wall bend radius (= mattress corner)
RC = ELB_RI + H / 2    # centreline radius
STUB = 30.0
FIN = 7.0              # bolt flange width
FIN_T = 4.0            # flange thickness per half
BOLT_D = 3.4           # M3

# diffuser
NOSE = H / 2 - 2.0     # 45 deg wedge nose
LOUV_P = 8.0           # louvre pitch
LOUV_T = 1.6
SIDE_WIN = 12.0        # flank louvre window half-height


# ---- helpers ---------------------------------------------------------------
def box(x0, x1, y0, y1, z0, z1):
    return m3d.Manifold.cube((x1 - x0, y1 - y0, z1 - z0)).translate((x0, y0, z0))


def union(parts):
    return m3d.Manifold.batch_boolean(list(parts), m3d.OpType.Add)


def clean(m):
    """Drop zero-volume sliver components left by coplanar booleans."""
    return m3d.Manifold.compose([c for c in m.decompose() if c.volume() > 1.0])


def vol(m):
    return m.volume()


def profile(off=0.0):
    """Duct profile in (x = width, y = height), offset outward by off."""
    r = H / 2
    yc = W / 2 - r * math.sqrt(2) + TIP
    pts = []
    for s in (-1, 1):
        for k in range(SEG):
            a = 2 * math.pi * k / SEG
            pts.append((s * yc + r * math.cos(a), r * math.sin(a)))
        pts += [(s * W / 2, TIP), (s * W / 2, -TIP)]
    cs = m3d.CrossSection.hull_points(pts)
    return cs.offset(off, m3d.JoinType.Round, circular_segments=SEG) if off else cs


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


def prism(cs, z0, z1):
    return m3d.Manifold.extrude(cs, z1 - z0).translate((0, 0, z0))


def xform(m, rows):
    return m.transform(np.array(rows, dtype=float))


def to_world_bed(m, x0):
    """Local (x width, y height, z along) -> world, running +x on the mattress."""
    return xform(m, [[0, 0, 1, x0], [1, 0, 0, 0], [0, 1, 0, H / 2]])


def to_world_hang(m, z0):
    """Local -> world, running +z (up) at the foot face, centred x = -H/2."""
    return xform(m, [[0, 1, 0, -H / 2], [-1, 0, 0, 0], [0, 0, 1, z0]])


O, I = profile(), profile(-WALL)
SO, SI = profile(WALL + CLR), profile(CLR)


def socket_end():
    """Outer, inner solids for the socket + shoulder at local z = 0."""
    outer = loft([(SO, 0), (SO, SOCK), (O, SOCK + TAP)])
    inner = loft([(SI, -1), (SI, SOCK), (I, SOCK + TAP)])
    return outer, inner


def webs(z0, z1):
    return union(box(x - WEB_T / 2, x + WEB_T / 2, -H / 2, H / 2, z0, z1)
                 for x in WEB_X) ^ prism(O, z0, z1)


# ---- straight segment ------------------------------------------------------
def make_segment():
    so, si = socket_end()
    outer = so + prism(O, SOCK + TAP - 1e-3, SEG_LEN)
    inner = si + prism(I, SOCK + TAP - 1e-3, SEG_LEN + 1)
    return outer - inner + webs(SOCK + TAP, SEG_LEN)


# vent track: dovetail on each flank (narrower at the surface)
T0 = SOCK + TAP + 5.0                  # track start, open at the plain end
SLOTS = [T0 + 2 * SLOT_L * (k + 1) for k in range(20)
         if T0 + 2 * SLOT_L * (k + 1) + SLOT_L <= SEG_LEN - SOCK - 5]


def trapezoid(s, shrink=0.0):
    """Dovetail region on flank s (+1/-1) in profile coords."""
    xo, xi = W / 2 + 10, W / 2 - 32
    ao, ai = 14.0 - shrink, 30.0 - shrink
    pts = [(xi, -ai), (xo, -ao), (xo, ao), (xi, ai)]
    pts = [(s * x, y) for x, y in pts]
    if s < 0:
        pts = pts[::-1]
    return m3d.CrossSection([pts])


def slot_cut(s, z, zlen=SLOT_L):
    x0, x1 = (W / 2 - 42, W / 2 + 5) if s > 0 else (-W / 2 - 5, -W / 2 + 42)
    return box(x0, x1, -SLOT_H, SLOT_H, z, z + zlen)


def make_segment_vented():
    seg = make_segment()
    zt = SEG_LEN + 1
    for s in (1, -1):
        pad = (prism(I, T0 - 5, SEG_LEN) - prism(I.offset(-PAD, m3d.JoinType.Round), T0 - 6, zt)) \
            ^ prism(trapezoid(s, -6.0), T0 - 6, zt)
        seg = seg + pad
        band = prism(O, T0, zt) - prism(O.offset(-DEPTH, m3d.JoinType.Round), T0 - 1, zt + 1)
        seg = seg - (band ^ prism(trapezoid(s), T0, zt))
        seg = seg - union(slot_cut(s, z) for z in SLOTS)
    return seg


def make_slider(s=1):
    """Slider for flank s, in segment-local coords at the OPEN position."""
    tz = trapezoid(s, SCLR)
    band = O.offset(-SCLR, m3d.JoinType.Round) - O.offset(-DEPTH + SCLR, m3d.JoinType.Round)
    L = SEG_LEN - T0 - TRAVEL
    m = prism(band ^ tz, T0, T0 + L)
    m = m - union(slot_cut(s, z) for z in SLOTS)
    # grip grooves across the apex, in the solid between two slots
    zg = SLOTS[len(SLOTS) // 2] + SLOT_L + 1.0
    for k in range(3):
        z = zg + k * 3.0
        g = box(W / 2 - SCLR - 0.8, W / 2 + 1, -8, 8, z, z + 1.2)
        m = m - (g if s > 0 else g.mirror((1, 0, 0)))
    return m


# ---- diffuser --------------------------------------------------------------
DZ0, DZ1 = SOCK + TAP + 12.0, SEG_LEN - NOSE - 10.0   # louvre window span


def louvres_top():
    """Top window with slats tilted 45 deg toward the foot (local -z)."""
    yt, yb = H / 2 + 1, H / 2 - 7.0
    dz = yt - yb
    slats = []
    z = DZ0 + dz
    while z + LOUV_T <= DZ1:
        poly = [(z, yb), (z + LOUV_T, yb), (z + LOUV_T - dz, yt), (z - dz, yt)]
        cs = m3d.CrossSection([poly])
        sl = m3d.Manifold.extrude(cs, 2 * W).translate((0, 0, -W))
        # (u=z, v=y, w=x) -> (x, y, z)
        slats.append(xform(sl, [[0, 0, 1, 0], [0, 1, 0, 0], [1, 0, 0, 0]]))
        z += LOUV_P
    xw = W / 2 - H / 2 * math.sqrt(2) + TIP - 12      # inside the top flat
    win = box(-xw, xw, H / 2 - WALL - 1, H / 2 + 1, DZ0, DZ1)
    keep = union(box(x - WEB_T / 2 - 1, x + WEB_T / 2 + 1, -H, H, DZ0, DZ1) for x in WEB_X)
    win = win - keep
    region = box(-xw - 1, xw + 1, yb, yt, DZ0, DZ1) ^ prism(O, DZ0, DZ1)   # 1 mm into the frame
    return win, union(slats) ^ region


def louvres_side(s):
    """Flank window, slats tilted 45 deg toward the foot and outward."""
    r = H / 2
    yc = W / 2 - r * math.sqrt(2) + TIP
    xo = W / 2 + 1
    dz = xo - (W / 2 - 14.0)
    slats = []
    z = DZ0 + dz
    while z + LOUV_T <= DZ1:
        poly = [(z, W / 2 - 14.0), (z + LOUV_T, W / 2 - 14.0), (z + LOUV_T - dz, xo), (z - dz, xo)]
        cs = m3d.CrossSection([poly])
        sl = m3d.Manifold.extrude(cs, 2 * H).translate((0, 0, -H))
        # (u=z, v=x, w=y) -> (x, y, z)
        sl = xform(sl, [[0, 1, 0, 0], [0, 0, 1, 0], [1, 0, 0, 0]])
        slats.append(sl if s > 0 else sl.mirror((1, 0, 0)))
        z += LOUV_P
    # window through the wall shell only, so the chevron above/below stays as a frame
    x0, x1 = (yc, xo + 1) if s > 0 else (-xo - 1, -yc)
    shell = prism(O, DZ0, DZ1) - prism(I, DZ0 - 1, DZ1 + 1)
    win = shell ^ box(x0, x1, -SIDE_WIN, SIDE_WIN, DZ0, DZ1)
    region = box(min(s * (W / 2 - 14.0), s * xo), max(s * (W / 2 - 14.0), s * xo),
                 -SIDE_WIN - 1, SIDE_WIN + 1, DZ0, DZ1)
    return win, union(slats) ^ region ^ prism(O, DZ0, DZ1)


def make_diffuser():
    so, si = socket_end()
    zn = SEG_LEN - NOSE
    outer = so + prism(O, SOCK + TAP - 1e-3, zn) + \
        loft([(O, zn - 1e-3), (O.offset(-NOSE, m3d.JoinType.Round), SEG_LEN)])
    ni = NOSE - 1.0
    inner = si + prism(I, SOCK + TAP - 1e-3, zn - 1) + \
        loft([(I, zn - 1 - 1e-3), (I.offset(-ni, m3d.JoinType.Round), zn - 1 + ni)])
    d = outer - inner + webs(SOCK + TAP, zn)
    w, sl = louvres_top()
    d = d - w + sl
    for s in (1, -1):
        w, sl = louvres_side(s)
        d = d - w + sl
    return d


# ---- inlet adapter (round hose spigot -> flat socket) ----------------------
ADP_LEN = SPIG_L + LOFT_L + TAP + SOCK


def make_adapter():
    c0, c1 = circle(HOSE_R), circle(HOSE_R + BEAD)
    ci = circle(HOSE_R - WALL)
    z1 = SPIG_L + LOFT_L
    outer = union([loft([(c0, 0), (c1, 6), (c1, 9), (c0, 12)]),
                   loft([(c0, 11), (c0, SPIG_L), (O, z1), (SO, z1 + TAP), (SO, ADP_LEN)])])
    inner = loft([(ci, -1), (ci, SPIG_L), (I, z1), (SI, z1 + TAP), (SI, ADP_LEN + 1)])
    return outer - inner


# ---- elbow -----------------------------------------------------------------
def swap(cs):
    """(x width, y height) -> (r = RC + height, h = width) for revolve.
    Swapping axes mirrors, so each contour is reversed to keep its winding."""
    return m3d.CrossSection([[(RC + y, x) for x, y in p][::-1] for p in cs.to_polygons()])


def bend_to_world(m):
    """Revolve frame (arc u -> v about w) -> world: centre (x=ELB_RI, z=-ELB_RI),
    u -> +z (the mattress leg), v -> -x (the hanging leg), w -> -y."""
    return xform(m, [[0, -1, 0, ELB_RI], [0, 0, -1, 0], [1, 0, 0, -ELB_RI]])


def make_elbow():
    ring = O - I
    arc = bend_to_world(m3d.Manifold.revolve(swap(ring), 192, 90.0))
    stub_b = to_world_bed(prism(ring, 0, STUB), ELB_RI)
    stub_h = to_world_hang(prism(ring, 0, STUB), -ELB_RI - STUB)
    # flanges on the split plane (y = 0) at the top/bottom walls
    fl = []
    for r0, r1 in ((RC + H / 2 - 0.5, RC + H / 2 + FIN), (RC - H / 2 - FIN, RC - H / 2 + 0.5)):
        cs = m3d.CrossSection([[(r0, -FIN_T), (r1, -FIN_T), (r1, FIN_T), (r0, FIN_T)]])
        fl.append(bend_to_world(m3d.Manifold.revolve(cs, 192, 90.0)))
    e = union([arc, stub_b, stub_h] + fl)
    # bolt holes, symmetric about the 45 deg plane
    holes = []
    cx, cz = ELB_RI, -ELB_RI
    for rr in (RC + H / 2 + FIN / 2, RC - H / 2 - FIN / 2):
        angs = (15.0, 45.0, 75.0) if rr > RC else (30.0, 60.0)
        for a in angs:
            t = math.radians(a)
            holes.append((cx - rr * math.sin(t), cz + rr * math.cos(t)))
    for x, z in holes:
        c = m3d.Manifold.cylinder(30, BOLT_D / 2, BOLT_D / 2, 32).translate((0, 0, -15))
        e = e - c.rotate((90, 0, 0)).translate((x, 0, z))
    return e


# ---- assembly --------------------------------------------------------------
X_SEG0 = ELB_RI + STUB - SOCK                         # segment 1 socket start


def seg_x(k):
    return X_SEG0 + PITCH * k


def build():
    seg, vseg = clean(make_segment()), clean(make_segment_vented())
    sl_p, sl_n = make_slider(1), make_slider(-1)
    dif, adp, elb = clean(make_diffuser()), clean(make_adapter()), clean(make_elbow())
    half = elb ^ box(-500, 500, 0, 500, -500, 500)
    parts = {}
    parts["adapter"] = to_world_hang(adp, -ELB_RI - STUB - ADP_LEN + SOCK)
    parts["elbow_a"] = half
    parts["elbow_b"] = elb ^ box(-500, 500, -500, 0, -500, 500)
    n = N_PLAIN + N_VENT
    for k in range(n):
        vented = k >= N_PLAIN
        parts[f"seg_{k + 1}"] = to_world_bed(vseg if vented else seg, seg_x(k))
        if vented:
            parts[f"slider_{k + 1}a"] = to_world_bed(sl_p, seg_x(k))
            parts[f"slider_{k + 1}b"] = to_world_bed(sl_n, seg_x(k))
    parts["diffuser"] = to_world_bed(dif, seg_x(n))
    singles = dict(adapter=adp, elbow_half=half, segment=seg, segment_vented=vseg,
                   slider=sl_p, diffuser=dif)
    return parts, singles


# ---- checks ----------------------------------------------------------------
def to_trimesh(m):
    import trimesh
    mesh = m.to_mesh()
    verts = np.asarray(mesh.vert_properties)[:, :3]
    return trimesh.Trimesh(verts, np.asarray(mesh.tri_verts), process=False)


def bed_fit(tm):
    pts = tm.vertices[:, :2]
    best = (1e9, 0)
    for a in range(0, 90):
        c, s = math.cos(math.radians(a)), math.sin(math.radians(a))
        p = pts @ np.array([[c, -s], [s, c]])
        best = min(best, (max(np.ptp(p[:, 0]), np.ptp(p[:, 1])), a))
    return best


def ok(flag):
    return "OK" if flag else "FAIL"


def report(parts, singles):
    n = N_PLAIN + N_VENT
    end = seg_x(n) + SEG_LEN
    hose = math.pi * 76.2 ** 2
    duct = I.area() - len(WEB_X) * WEB_T * (H - 2 * WALL)
    print("-- layout")
    print(f"  duct {W:.0f} x {H:.0f} mm, {n} segments ({N_PLAIN} plain + {N_VENT} vented) "
          f"+ diffuser, nose at x={end:.0f} of {MATTRESS_L:.0f} "
          f"({MATTRESS_L - end:.0f} mm free) -> {ok(MATTRESS_L - end >= HEAD_GAP)}")
    print(f"  flow area: 6in hose {hose / 100:.0f} cm2, duct {duct / 100:.0f} cm2 "
          f"({100 * duct / hose:.0f} %), spigot bore {math.pi * (HOSE_R - WALL) ** 2 / 100:.0f} cm2")
    print("-- fit (overlap mm3 / min gap mm between neighbours)")
    names = ["adapter", "elbow_a", "elbow_b"] + [f"seg_{k + 1}" for k in range(n)] + ["diffuser"]
    pairs = [("adapter", "elbow_a"), ("adapter", "elbow_b"), ("elbow_a", "seg_1"),
             ("elbow_b", "seg_1")] + [(names[2 + k], names[3 + k]) for k in range(1, n + 1)]
    allok = True
    for a, b in pairs:
        ov = vol(parts[a] ^ parts[b])
        g = parts[a].min_gap(parts[b], 5.0)
        good = ov < 1e-2
        allok &= good
        print(f"  {a:9s} / {b:9s} overlap {ov:8.3f}  gap {g:5.2f} -> {ok(good)}")
    k0 = N_PLAIN + 1
    for sfx in "ab":
        s, g = parts[f"slider_{k0}{sfx}"], parts[f"seg_{k0}"]
        shut = s.translate((TRAVEL, 0, 0))
        nxt = parts[f"seg_{k0 + 1}"]
        o1, o2, o3 = vol(s ^ g), vol(shut ^ g), vol(shut ^ nxt)
        gp = s.min_gap(g, 5.0)
        good = max(o1, o2, o3) < 1e-2
        allok &= good
        print(f"  slider {sfx} open/closed overlap {o1:.3f}/{o2:.3f}/{o3:.3f} gap {gp:.2f} "
              f"-> {ok(good)}")
    # slot alignment: open = slot holes coincide, closed = fully covered
    sp = make_slider(1)
    win = union(slot_cut(1, z) for z in SLOTS) ^ (prism(O, 0, SEG_LEN) - prism(I, -1, SEG_LEN + 1))
    print(f"  slots: {len(SLOTS)} per side, slider blocks open {vol(win ^ sp):.1f} mm3 / "
          f"closed {vol(win ^ sp.translate((0, 0, TRAVEL))):.1f} mm3")
    return allok


ORIENT = {
    "adapter": (None, "spigot down"),
    "elbow_half": (lambda m: m.rotate((90, 0, 0)), "cut face down"),
    "segment": (None, "socket down"),
    "segment_vented": (None, "socket down"),
    "slider": (lambda m: m.rotate((0, 90, 0)), "apex down"),
    "diffuser": (None, "socket down"),
}
QTY = {"elbow_half": 2, "segment": N_PLAIN, "segment_vented": N_VENT, "slider": 2 * N_VENT}


def meta(name):
    if name.startswith("seg_"):
        k = int(name[4:])
        return ("#e9e4d8" if k % 2 else "#dcd5c4", 2 + k)
    if name.startswith("slider"):
        return ("#d0763a", 2 + int(name[7:-1]))
    return {"adapter": ("#5b7fa6", 0), "elbow_a": ("#4a6d94", 1), "elbow_b": ("#4a6d94", 1),
            "diffuser": ("#5b7fa6", 10), "mattress": ("#cfd8e3", -99, 0.35),
            "hose": ("#555555", -99)}[name]


def context():
    mat = box(0, MATTRESS_L, -MATTRESS_W / 2, MATTRESS_W / 2, -MATTRESS_T, 0)
    z0 = -ELB_RI - STUB - ADP_LEN + SOCK
    hose = m3d.Manifold.cylinder(260, HOSE_R + BEAD + 1.5, HOSE_R + BEAD + 1.5, 96) \
        .translate((-H / 2, 0, z0 - 250 + 40))
    hose = hose - m3d.Manifold.cylinder(300, HOSE_R, HOSE_R, 96).translate((-H / 2, 0, z0 - 280))
    return {"mattress": mat, "hose": hose}


def export(parts, singles):
    import trimesh  # noqa: F401
    print("-- STL export (print orientation)")
    os.makedirs(os.path.join(OUT, "stl"), exist_ok=True)
    os.makedirs(os.path.join(OUT, "preview"), exist_ok=True)
    allok = True
    for name, m in singles.items():
        rot, how = ORIENT[name]
        tm = to_trimesh(rot(m) if rot else m)
        tm.apply_translation(-np.array([tm.bounds[0][0] + tm.extents[0] / 2,
                                        tm.bounds[0][1] + tm.extents[1] / 2, tm.bounds[0][2]]))
        tm.export(os.path.join(OUT, "stl", f"{name}.stl"))
        side, ang = bed_fit(tm)
        fits = side <= BED - 2 * BED_MARGIN and tm.extents[2] <= BED - BED_MARGIN
        allok &= fits and tm.is_watertight
        print(f"  {name:15s} x{QTY.get(name, 1)}  {how:13s} size {np.round(tm.extents, 1)} "
              f"footprint {side:5.1f} @ {ang:2d} deg  {tm.volume / 1000:5.0f} cm3  "
              f"watertight={tm.is_watertight} bed {ok(fits)}")
    entries = []
    for name, m in list(parts.items()) + list(context().items()):
        to_trimesh(m).export(os.path.join(OUT, "preview", f"{name}.stl"))
        c = meta(name)
        entries.append({"name": name, "file": f"preview/{name}.stl", "color": c[0], "lvl": c[1],
                        "opacity": c[2] if len(c) > 2 else 1.0})
    with open(os.path.join(OUT, "preview", "manifest.json"), "w") as fh:
        json.dump({"title": f"Bed air duct: 6in hose -> {W:.0f} x {H:.0f} mm flat duct, king bed",
                   "parts": entries}, fh, indent=1)
    print(f"  all parts fit + watertight -> {ok(allok)}")
    return allok


def main():
    parts, singles = build()
    report(parts, singles)
    export(parts, singles)


if __name__ == "__main__":
    main()
