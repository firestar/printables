"""Gyroid Mist Shell: fogponic concept tower on the classic grow-tower base.

The turning stack is four identical SEGMENTS.  Each one is a closed 3.4 mm
inner wall (the classic tier column) wrapped in a gyroid sheet lattice that
swells like a pebble between the joints, with nine 2" net-pot pockets in a
three-start helix (3 rows x 3, rows 40 deg apart).  The lattice is only
relief OUTSIDE the solid wall: fog and drip stay in the chamber.

Roots hang into the chamber and are fed by FOG.  A 24 mm ultrasonic fogger
rides in a printed FOG_FLOAT (+ FOG_CRADLE) that slides on the centre pipe.
An 80 mm 12 V fan in a FAN_BOX under the lid draws the tank headspace and
blows it up a FAN_ROOF riser, through the lid drain (between its spokes), a
DUCT_FOOT and a DN50 PVC duct round the centre pipe to the MIST_HEAD, whose
hood throws the fog out under the cap.  The fog sinks past every root zone,
falls back through the rotor bore into the tank headspace and is drawn in
again: a closed loop.

Hybrid: pump, centre pipe and the jets in the MIST_HEAD stay as a short flush
cycle (fog alone dries the roots if the fogger fails), exactly like the
classic spray head.  The classic CAP rides on the same stub.

  turning --- 4 x SEGMENT (spigot / socket like gt.make_tier), classic CAP
  fixed   --- MIST_HEAD (jets + stub + fog hood + duct socket) on the pipe
              DUCT: DN50 PVC drain pipe, DUCT_FOOT on the lid spokes
              FAN_BOX (80 mm fan below its floor) + FAN_ROOF (riser) on the pipe
              FOG_FLOAT + FOG_CRADLE (24 mm fogger puck) slide on the pipe

Extra outputs (firmware unchanged): fogger MOSFET, fan MOSFET, see README.
Run: env PYTHONPATH=/home/infra/printables/.pydeps python3 gyroid_mist.py
"""
import math
import os
import sys
import time

import numpy as np
import manifold3d as m3d

HERE = os.path.dirname(os.path.abspath(__file__))
CAD = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, CAD)
import grow_tower as gt                                     # noqa: E402
from grow_tower import revolve, tube, cyl, box, vol, union, ok   # noqa: E402

FLIP = gt.FLIP
ASA = 1.07e-3          # g/mm3

# ---- stack: 4 segments, same pitch sum as the classic 6 x 120 ---------------
N_SEG = 4
SEG_H = 182.4                                  # body height above the seat
SEG_PITCH = SEG_H - gt.RIM_CH - gt.CLR         # 180
SEG_Z = [gt.Z_RT - gt.SEAT_DROP + k * SEG_PITCH for k in range(N_SEG)]
CAP_Z = SEG_Z[-1] + SEG_PITCH
assert abs(CAP_Z - gt.CAP_Z) < 1e-6            # classic cap + stub height reused

# net-pot pockets: 3 rows x 3, 40 deg twist per row -> 3-start helix
ROWS, PER_ROW = 3, 3
ROW_TWIST = 40.0
ROW_Z0 = 42.0          # row 0 port axis meets the inner face (segment local)
ROW_DZ = 34.0
PORTS = [(360.0 / PER_ROW * k + ROW_TWIST * j, ROW_Z0 + ROW_DZ * j)
         for j in range(ROWS) for k in range(PER_ROW)]
POT_LIP_R = 33.0       # net-pot lip + finger room kept free of lattice

# gyroid lattice skin (cylindrical gyroid: LAT_N cells round, 120 deg periodic)
LAT_N = 30
LAT_PR = 17.0          # radial period
LAT_PZ = 24.0          # vertical period (stretched -> steeper sheet)
LAT_T = 2.4            # sheet thickness (>= 2.0 after the radial scaling)
LAT_TMAX = 13.0        # skin thickness at the pebble's belly
LAT_EMBED = 0.8        # sheet starts this far inside the wall
LAT_Z0 = gt.R_TO - gt.R_SO                     # shoulder top
LAT_Z1 = SEG_H - 1.5
LAT_EDGE = 1.25        # level-set grid edge (mm)
LAT_SIMPLIFY = 0.06

# fog duct: DN50 PVC drain pipe round the centre pipe
DUCT_OD, DUCT_ID = 50.0, 46.4
SOCK_R = DUCT_OD / 2 + 0.35                    # printed socket bore
SPOKE_ANGS = [30.0 + 120 * k for k in range(3)]   # lid spokes (gt.make_lid)
SPOKE_HW = 4.0
FOOT_Z0 = gt.Z_L - gt.LID_T - 5.0              # skirt bottom, round the riser top
FOOT_LEDGE = gt.Z_L + 7.0                      # PVC rests here
FOOT_DRIP_R = 29.5

# mist head (local z = 0 at the pipe top = gt.SPRAY_Z)
JET_Z = 10.0
HEAD_STOP = -48.0      # duct top stop
HEAD_WIN_Z = -37.0     # centre of the 6 fog windows (kept under the drip ring)
HEAD_SOCK0 = -70.0
DUCT_Z0 = FOOT_LEDGE
DUCT_Z1 = gt.SPRAY_Z + HEAD_STOP - 2.0         # cut 2 mm short
HOOD_DRIP_R = 32.0

# fan box (80 mm fan under the floor) + roof with the riser
FAN, FAN_T, FAN_HOLE = 80.0, 25.0, 71.5
FAN_Y = -58.0
BOX_WALL, BOX_FLOOR, ROOF_T, GROOVE = 2.4, 3.0, 3.0, 2.5
Z_ROOF_TOP = gt.Z_L - gt.LID_T - gt.LID_RIB_H - 2.5
Z_ROOF_BOT = Z_ROOF_TOP - ROOF_T
Z_WALL_TOP = Z_ROOF_BOT + GROOVE
Z_FLOOR_TOP = Z_ROOF_BOT - 24.0
Z_FLOOR_BOT = Z_FLOOR_TOP - BOX_FLOOR
Z_FAN_BOT = Z_FLOOR_BOT - FAN_T
RISER_RI, RISER_RO = 24.5, 26.5
RISER_TOP = gt.Z_L - gt.LID_T - 0.5
INLET_R = 38.5

# fogger float (local z = 0 at the float bottom)
FOG_D, FOG_H = 50.0, 24.0       # 24 mm single-disc fogger puck (disc on top)
FOG_M, FOG_V = 120.0, 45.0      # g, cm3
CABLE_M = 20.0                  # g of cable hanging on the float
DISC_DEPTH = 32.0               # disc below the waterline (unit spec 25-40)
FL_R = 76.0
FL_GUIDE = gt.PIPE_OD / 2 + 1.0
WELL_RC = 45.0                  # well centre radius (+y, away from the float switch arm)
WELL_R = 28.4
CR_RI, CR_RO = FOG_D / 2 + 0.6, FOG_D / 2 + 2.6
WL_PREVIEW = 250.0              # waterline drawn in the preview
WL_MAX = 365.0                  # max fill mark
WL_MIN = gt.TANK_FLOOR + 90 + 10  # float lands on the float switch bracket


# ---- segment ---------------------------------------------------------------
def port_cyl(r, s0, s1, zi, ang, seg=96):
    a = math.radians(gt.PORT_TILT)
    c = m3d.Manifold.cylinder(s1 - s0, r, r, seg).rotate((0, gt.PORT_TILT, 0))
    return c.translate((gt.R_TI + s0 * math.sin(a), 0, zi + s0 * math.cos(a))).rotate((0, 0, ang))


def lat_env(z):
    """Lattice skin thickness at z: 45 deg ramp off the shoulder, pebble belly,
    quick fall to the rim.  dT/dz <= 1 keeps the cut edge at <= 45 deg."""
    if z <= LAT_Z0 or z >= LAT_Z1:
        return 0.0
    s = (z - LAT_Z0) / (LAT_Z1 - LAT_Z0)
    t = 3.0 + (LAT_TMAX - 3.0) * math.sin(math.pi * s) ** 1.5
    return min(t, z - LAT_Z0, 2.0 * (LAT_Z1 - z))


KR, KZ = 2 * math.pi / LAT_PR, 2 * math.pi / LAT_PZ
_sin, _cos, _sqrt, _atan2, _hyp = math.sin, math.cos, math.sqrt, math.atan2, math.hypot


def lat_sdf(x, y, z):
    v = _hyp(x, y) - gt.R_TO
    if v < -LAT_EMBED - 1.5 or v > LAT_TMAX + 1.5 or z <= LAT_Z0 or z >= LAT_Z1:
        return -2.0
    env = lat_env(z)
    d = min(v + LAT_EMBED, env - v, z - LAT_Z0, LAT_Z1 - z)
    if d < -1.5:
        return d
    r = v + gt.R_TO
    X, Y, Z = LAT_N * _atan2(y, x), KR * v + 0.9, KZ * z
    sx, cx, sy, cy, sz, cz = _sin(X), _cos(X), _sin(Y), _cos(Y), _sin(Z), _cos(Z)
    g = sx * cy + sy * cz + sz * cx
    gx = (cx * cy - sz * sx) * LAT_N / r
    gy = (cy * cz - sx * sy) * KR
    gz = (cz * cx - sy * sz) * KZ
    gn = max(_sqrt(gx * gx + gy * gy + gz * gz), 0.15)
    return min(LAT_T / 2 - abs(g) / gn, d)


def make_lattice():
    b = gt.R_TO + LAT_TMAX + 1.0
    t = time.time()
    lat = m3d.Manifold.level_set(lat_sdf, [-b, -b, LAT_Z0 - 0.5, b, b, LAT_Z1 + 0.5], LAT_EDGE)
    n0 = lat.num_tri()
    lat = lat.simplify(LAT_SIMPLIFY)
    print(f"  lattice level set {time.time() - t:5.1f} s, {n0} -> {lat.num_tri()} tris")
    return lat


def make_segment(lattice):
    """One segment, local z = 0 at its seat (same spigot/socket as gt.make_tier)."""
    R_SO, R_TO, R_TI, R_SI = gt.R_SO, gt.R_TO, gt.R_TI, gt.R_SI
    EF, SPIG_L, RIM_CH = gt.EF, gt.SPIG_L, gt.RIM_CH
    outer = revolve([(0, -SPIG_L), (R_SO - EF, -SPIG_L), (R_SO, -SPIG_L + EF),
                     (R_SO, 0), (R_TO, R_TO - R_SO), (R_TO, SEG_H), (0, SEG_H)])
    ro = gt.PORT_ID / 2 + gt.PORT_WALL
    tubes = [port_cyl(ro, -20, gt.PORT_L, zi, a) for a, zi in PORTS]
    lip = [port_cyl(POT_LIP_R, gt.PORT_L - 0.5, gt.PORT_L + 60, zi, a) for a, zi in PORTS]
    lat = lattice - union(lip)
    s = union([outer, lat] + tubes)
    void = revolve([(0, -SPIG_L - 1), (R_SI, -SPIG_L - 1), (R_SI, 0), (R_TI, R_TI - R_SI),
                    (R_TI, SEG_H - RIM_CH), (R_TI + RIM_CH, SEG_H),
                    (R_TI + RIM_CH, SEG_H + 1), (0, SEG_H + 1)])
    bores = [port_cyl(gt.PORT_ID / 2, -20, gt.PORT_L + 1, zi, a) for a, zi in PORTS]
    s = s - union([void] + bores)
    pieces = sorted(s.decompose(), key=vol, reverse=True)
    isl = [vol(p) for p in pieces[1:] if vol(p) > 0]
    voids = [vol(p) for p in pieces[1:] if vol(p) <= 0]
    print(f"  segment: kept 1 body, dropped {len(isl)} loose lattice crumbs ({sum(isl):.0f} mm3), "
          f"filled {len(voids)} sealed micro-voids ({-sum(voids):.0f} mm3)")
    return pieces[0]


def place_seg(s, k):
    return s.translate((0, 0, SEG_Z[k]))


# ---- fog duct, mist head ------------------------------------------------------
def make_duct():
    return tube(DUCT_ID / 2, DUCT_OD / 2, DUCT_Z0, DUCT_Z1, 96)


def make_duct_foot():
    """Socket for the PVC duct, rests on the 3 lid spokes (gable notches), its
    skirt laps the riser top under the lid plate, drip edge outside the riser."""
    zl, zp = FOOT_LEDGE, gt.Z_L - gt.LID_T
    f = revolve([(27.0, FOOT_Z0), (FOOT_DRIP_R, FOOT_Z0), (FOOT_DRIP_R, zl),
                 (SOCK_R + 2.4, zl + FOOT_DRIP_R - SOCK_R - 2.4), (SOCK_R + 2.4, zl + 20),
                 (SOCK_R, zl + 20), (SOCK_R, zl), (23.0, zl), (23.0, zp + 4.6),
                 (27.0, zp + 0.6)], 128)
    hw = SPOKE_HW + 0.5                       # notch half width
    zn = gt.Z_L - 0.5                         # roof touches the spoke top edges
    notch = m3d.CrossSection([[(-hw, FOOT_Z0 - 1), (hw, FOOT_Z0 - 1), (hw, zn), (0, zn + hw),
                               (-hw, zn)]]).extrude(20).translate((0, 0, 18))
    notch = notch.rotate((90, 0, 0)).rotate((0, 0, 90))   # profile in y-z, along x
    for a in SPOKE_ANGS:
        f = f - notch.rotate((0, 0, a))
    return f


def make_mist_head():
    """Classic spray head (jets raised to JET_Z, 45 deg shoulder) plus a fog
    hood with a drip edge and a socket that takes the PVC duct top."""
    hr = gt.PIPE_OD / 2 + 0.2
    sd = gt.STUB_D / 2
    s = revolve([(SOCK_R, HEAD_SOCK0), (SOCK_R + 2.65, HEAD_SOCK0),
                 (SOCK_R + 2.65, -28), (HOOD_DRIP_R, -24), (HOOD_DRIP_R, -22),
                 (15, -5), (15, 8), (sd, 15), (sd, 33.4), (sd - 0.6, 34), (0, 34),
                 (0, 20), (8, 12), (8, 3.0), (hr, 3.0 - (hr - 8)),
                 (hr, -30), (15, -30), (15, -11), (23, -19),
                 (23, HEAD_STOP), (SOCK_R, HEAD_STOP)], 128)
    for k in range(gt.SPRAY_HOLES):
        h = m3d.Manifold.cylinder(20, (gt.SPRAY_HOLE_D + gt.HOLE_COMP) / 2,
                                  (gt.SPRAY_HOLE_D + gt.HOLE_COMP) / 2, 24)
        s = s - h.rotate((0, 90, 0)).translate((0, 0, JET_Z)).rotate((0, 0, 360 / gt.SPRAY_HOLES * k + 22.5))
    # 6 diamond fog windows under the hood (45 deg edges both ways)
    win = m3d.CrossSection([[(0, -9), (9, 0), (0, 9), (-9, 0)]]).extrude(16)
    win = win.rotate((90, 0, 0)).rotate((0, 0, 90)).translate((20, 0, HEAD_WIN_Z))
    for k in range(6):
        s = s - win.rotate((0, 0, 60 * k))
    pin = m3d.Manifold.cylinder(70, 1.7, 1.7, 24).rotate((0, 90, 0)).translate((-35, 0, HEAD_WIN_Z))
    return (s - pin).translate((0, 0, gt.SPRAY_Z))


# ---- fan box + roof -----------------------------------------------------------
def box_inner():
    c = m3d.CrossSection.circle(30.0, 96)
    sq = m3d.CrossSection.square((FAN + 2, FAN + 2), True).translate((0, FAN_Y))
    return (c + sq).hull()


def box_outer():
    return box_inner().offset(BOX_WALL, m3d.JoinType.Round, 2.0, 96)


FAN_SCREWS = [(sx * FAN_HOLE / 2, FAN_Y + sy * FAN_HOLE / 2) for sx in (-1, 1) for sy in (-1, 1)]
BOX_DRAINS = [(-20.0, 12.0), (20.0, 12.0)]


def make_fan_box():
    hr = gt.PIPE_OD / 2 + 0.2
    b = box_outer().extrude(Z_WALL_TOP - Z_FLOOR_BOT).translate((0, 0, Z_FLOOR_BOT))
    b = b - box_inner().extrude(40).translate((0, 0, Z_FLOOR_TOP))
    b = b + tube(INLET_R, INLET_R + 2.0, Z_FLOOR_TOP - 0.01, Z_FLOOR_TOP + 5, 128).translate((0, FAN_Y, 0))
    b = b - cyl(10, INLET_R, z=Z_FLOOR_BOT - 1, y=FAN_Y, seg=128)
    top = Z_FLOOR_TOP + 16
    b = b + tube(hr, 15.0, Z_FLOOR_BOT, top, 96)
    b = b + box(-7, 7, 12, 25, Z_FLOOR_TOP - 0.01, top)             # clamp ears
    b = b - cyl(top - Z_FLOOR_BOT + 2, hr, z=Z_FLOOR_BOT - 1, seg=96)
    b = b - box(-0.8, 0.8, 0, 26, Z_FLOOR_TOP + 0.5, top + 1)       # clamp slit
    b = b - m3d.Manifold.cylinder(20, 1.7, 1.7, 24).rotate((0, 90, 0)).translate((-10, 19, Z_FLOOR_TOP + 9))
    for x, y in FAN_SCREWS + BOX_DRAINS:
        b = b - cyl(10, 1.7 if (x, y) in FAN_SCREWS else 1.6, z=Z_FLOOR_BOT - 1, x=x, y=y, seg=24)
    return b


def make_fan_roof():
    p = box_outer().offset(2.0, m3d.JoinType.Round, 2.0, 96).extrude(ROOF_T).translate((0, 0, Z_ROOF_BOT))
    groove = box_outer().offset(0.4, m3d.JoinType.Round, 2.0, 96) - box_inner().offset(-0.4, m3d.JoinType.Round, 2.0, 96)
    p = p - groove.extrude(GROOVE + 0.01).translate((0, 0, Z_ROOF_BOT - 0.01))
    p = p - cyl(ROOF_T + 2, RISER_RI, z=Z_ROOF_BOT - 1, seg=128)
    p = p + tube(RISER_RI, RISER_RO, Z_ROOF_TOP - 0.01, RISER_TOP, 128)
    for a in SPOKE_ANGS:      # centring ribs on the pipe, in line with the lid spokes
        p = p + box(gt.PIPE_OD / 2 + 0.4, RISER_RI + 0.1, -1.0, 1.0, Z_ROOF_BOT, RISER_TOP).rotate((0, 0, a))
    return p


def fan_dummy():
    f = box(-FAN / 2, FAN / 2, FAN_Y - FAN / 2, FAN_Y + FAN / 2, Z_FAN_BOT, Z_FLOOR_BOT)
    f = f - cyl(FAN_T - 4, 38, z=Z_FAN_BOT + 2, y=FAN_Y, seg=96)
    return f + cyl(FAN_T, 16, z=Z_FAN_BOT, y=FAN_Y, seg=48)


# ---- fogger float + cradle ------------------------------------------------------
def float_outer_profile():
    return [(FL_GUIDE, 0), (FL_R, 0), (FL_R, 8), (45, 39), (FL_GUIDE + 2.4, 8.05),
            (FL_GUIDE + 2.4, 30), (FL_GUIDE, 30)]


def make_fog_float():
    """Sealed hollow ring float sliding on the pipe; gabled 45 deg cavity, a
    chimney well at +y for the fog column and the cradle."""
    outer = revolve(float_outer_profile(), 128)
    gi = FL_GUIDE + 2.4
    c1 = 84 - 2.4 * math.sqrt(2)                       # outer roof line r + z
    c2 = -6 - 2.4 * math.sqrt(2)                       # inner roof line z - r
    zr = (c1 + c2) / 2
    cav = revolve([(gi + 2.4, 2.4), (FL_R - 2.4, 2.4), (FL_R - 2.4, c1 - FL_R + 2.4),
                   (c1 - zr, zr), (gi + 2.4, gi + 2.4 + c2)], 128)
    wall = cyl(39.0, WELL_R + 2.4, y=WELL_RC, seg=96)
    f = outer + wall - (cav - wall)
    return f - cyl(50, WELL_R, z=-5, y=WELL_RC, seg=96)


def make_fog_cradle(lip_z):
    """Tube that hangs in the float well; the fogger puck sits on its bottom lip
    (lip top at lip_z, float local).  Cone flange seats on the chimney rim."""
    z0 = lip_z - 2.4
    zf = 39.0 - (WELL_R - CR_RO)                       # cone meets the rim edge at z 39
    c = revolve([(21.0, z0), (CR_RO, z0), (CR_RO, zf), (CR_RO + 5, zf + 5), (CR_RO + 5, zf + 7),
                 (CR_RI, zf + 7), (CR_RI, lip_z), (21.0, lip_z)], 128)
    win = m3d.CrossSection([[(0, -6), (6, 0), (0, 6), (-6, 0)]]).extrude(12)
    win = win.rotate((90, 0, 0)).rotate((0, 0, 90)).translate((CR_RI - 4, 0, lip_z + 12))
    for k in range(4):
        c = c - win.rotate((0, 0, 45 + 90 * k))
    c = c - box(-3.5, 3.5, -CR_RO - 8, -CR_RI + 1, lip_z + 6, zf + 10)   # cable slot (-y)
    return c.translate((0, WELL_RC, 0))


def float_balance():
    """Waterline (float local) for the float + cradle + fogger, and lip height
    that puts the disc DISC_DEPTH under it."""
    env = revolve(float_outer_profile(), 128) + cyl(39.0, WELL_R + 2.4, y=WELL_RC, seg=96)
    env = env - cyl(50, WELL_R, z=-5, y=WELL_RC, seg=96)
    fl = make_fog_float()
    lip = 0.0
    for _ in range(4):
        cr = make_fog_cradle(lip)
        m_plastic = (vol(fl) + vol(cr)) * ASA                   # g
        load = m_plastic + FOG_M + CABLE_M - FOG_V - vol(cr) / 1000.0   # g of water to displace
        lo, hi = 0.0, 39.0
        for _ in range(40):
            mid = (lo + hi) / 2
            below = vol(env.trim_by_plane((0, 0, -1), -mid))
            lo, hi = (mid, hi) if below / 1000.0 < load else (lo, mid)
        wl = (lo + hi) / 2
        lip = wl - DISC_DEPTH - FOG_H
    return wl, lip, m_plastic, load


# ---- checks --------------------------------------------------------------------
def overhang(m, how_rot):
    """Area (mm2) of down-facing faces steeper than 45 / 60 deg from vertical in
    print orientation, ignoring the bed layer."""
    m = how_rot(m) if how_rot else m
    tm = gt.to_trimesh(m)
    z0 = tm.bounds[0][2]
    n = tm.face_normals
    a = tm.area_faces
    zc = tm.triangles_center[:, 2]
    off = zc > z0 + 0.3
    m45 = (n[:, 2] < -math.cos(math.radians(45)) - 1e-3) & off
    m60 = (n[:, 2] < -math.cos(math.radians(30))) & off
    # largest connected patch steeper than 60 deg (gyroid saddles are small islands)
    import trimesh
    adj = tm.face_adjacency
    adj = adj[m60[adj[:, 0]] & m60[adj[:, 1]]]
    big = 0.0
    if m60.any():
        comps = trimesh.graph.connected_components(adj, nodes=np.nonzero(m60)[0], min_len=1)
        big = max(a[c].sum() for c in comps)
    return a[m45].sum(), a[m60].sum(), big, tm.area


def clip_z(m, z0, z1):
    return m.trim_by_plane((0, 0, 1), z0).trim_by_plane((0, 0, -1), -z1)


def checks(p, seg, wl):
    allok = True

    def line(txt, flag):
        nonlocal allok
        allok &= bool(flag)
        print(f"  {txt} -> {ok(flag)}")

    print("-- 1. stack drop-in (path, seated, wiggle)")
    cone = 1.5 * gt.CLR + 0.1
    s1, s2 = p["seg_1"], p["seg_2"]
    jz1, jz2 = SEG_Z[0], SEG_Z[1]
    cap = gt.make_cap()
    seq = [("seg_1 -> rotor", clip_z(s1, jz1 - 20, jz1 + 40), p["rotor"], gt.CLR, cone),
           ("seg_2 -> seg_1", clip_z(s2, jz2 - 20, jz2 + 40), clip_z(s1, jz2 - 60, jz2 + 40),
            gt.CLR, cone),
           ("cap -> seg_4", cap, clip_z(p["seg_4"], CAP_Z - 60, CAP_Z + 40), gt.CLR, cone),
           ("duct_foot -> lid", p["duct_foot"], p["lid"], 0.45, 0.6),
           ("fan_roof -> fan_box", p["fan_roof"], p["fan_box"], 0.35, 0.05),
           ("fog_cradle -> float", p["fog_cradle"], p["fog_float"], 0.5, 0.6)]
    for name, mv, fx, wig, lift in seq:
        path, seat, w = gt.drop_check(mv, fx, 30.0, wig, lift)
        line(f"{name:20s} path {path:.4f} seated {seat:7.1f} wiggle {w:.4f} mm^3",
             path < 1e-3 and seat > 1e-3 and w < 1e-3)

    print("-- 2. turning vs fixed clearances, swept over 120 deg (min gap, mm)")
    pod = p["pod_base"] + p["pod_roof"]
    fixed = {"lid": p["lid"], "pod": pod, "pinion": p["pinion"], "pipe": gt.pipe(),
             "duct": p["duct"], "duct_foot": p["duct_foot"], "riser": p["fan_roof"],
             "mist_head": p["mist_head"]}
    turning = {"rotor": p["rotor"], "seg_1": s1, "seg_2": s2, "seg_4": p["seg_4"], "cap": cap}
    skip = {("rotor", "pinion"), ("rotor", "mist_head"), ("seg_1", "mist_head"),
            ("seg_2", "mist_head"), ("seg_2", "lid"), ("seg_2", "pod"), ("seg_2", "pinion"),
            ("seg_4", "lid"), ("seg_4", "pod"), ("seg_4", "pinion"), ("cap", "lid"),
            ("cap", "pod"), ("cap", "pinion"), ("cap", "riser"), ("cap", "duct_foot"),
            ("seg_4", "riser"), ("seg_4", "duct_foot"), ("seg_2", "riser"),
            ("seg_2", "duct_foot"), ("cap", "mist_head")}   # cap bushing: own check below
    worst = {}
    for ang in range(0, 120, 15):
        for tn, tm in turning.items():
            mv = tm.rotate((0, 0, ang))
            for sn, sm in fixed.items():
                if (tn, sn) in skip:
                    continue
                g = mv.min_gap(sm, 10.0)
                worst[(tn, sn)] = min(worst.get((tn, sn), 99), g)
    for (tn, sn), g in sorted(worst.items()):
        line(f"{tn:6s} vs {sn:10s} {g:6.2f}{'+' if g >= 10 else ' '}", g >= 0.8)
    g = p["mist_head"].min_gap(cap, 10.0)
    line(f"mist_head vs cap bushing {g:5.2f} (classic stub fit)", g >= 0.25)
    for name, a_, b_, lo in [("riser vs lid", p["fan_roof"], p["lid"], 0.3),
                             ("fan_roof vs tank", p["fan_roof"], p["tank_ring_2"], 1.0),
                             ("fan_box vs tank", p["fan_box"], p["tank_ring_2"], 1.0),
                             ("duct_foot vs riser", p["duct_foot"], p["fan_roof"], 0.3),
                             ("duct vs foot+head", p["duct"], p["duct_foot"] + p["mist_head"], 0.0),
                             ("fog_float vs pipe", p["fog_float"], gt.pipe(), 0.5),
                             ("fog_float vs bracket", p["fog_float"] + p["fog_cradle"],
                              p["float_bracket"], 0.5),
                             ("fan_box vs pipe", p["fan_box"], gt.pipe(), 0.0)]:
        g = a_.min_gap(b_, 10.0)
        line(f"{name:22s}{g:6.2f}", g >= lo - 1e-6 and vol(a_ ^ b_) < 1e-3)

    print("-- 3. water + fog path")
    jet = gt.SPRAY_Z + JET_Z - SEG_Z[-1]
    bore_top = max(zi for _, zi in PORTS) + gt.PORT_ID / 2 * math.sqrt(2)
    line(f"flush jets at top-segment z={jet:.1f} > port bore tops z={bore_top:.1f} + 3", jet > bore_top + 3)
    # every bore opens into the chamber, no two bores (or a bore and the rim) merge
    bores = [port_cyl(gt.PORT_ID / 2, -20, gt.PORT_L + 1, zi, a) for a, zi in PORTS]
    shell = tube(gt.R_TI, 200, -50, 250, 192)
    worst = max(vol(bores[i] ^ bores[j] ^ shell) for i in range(len(bores)) for j in range(i))
    lo_b = min(zi for _, zi in PORTS) - gt.PORT_ID / 2 * math.sqrt(2)
    line(f"{len(PORTS)} ports/segment x {N_SEG} = {len(PORTS) * N_SEG} plants, bores overlap "
         f"{worst:.3f} mm3, lowest bore edge z={lo_b:.1f} > shoulder {LAT_Z0:.1f}",
         worst < 1e-3 and lo_b > LAT_Z0 + 1 and len(PORTS) * N_SEG == 36)
    # inner wall is closed except the bores: wall ring minus segment == bores
    ring = tube(gt.R_TI + 0.01, gt.R_TO - 0.01, LAT_Z0 + 0.5, SEG_H - gt.RIM_CH - 0.5, 192)
    open_v = vol(ring - seg)
    bore_v = vol(ring ^ union(bores))
    line(f"inner wall open {open_v:.0f} mm3 = bores {bore_v:.0f} mm3 (no leak through the skin)",
         abs(open_v - bore_v) < 0.01 * bore_v + 5)
    r_tip = gt.R_TI - (gt.Z_RT - gt.SOCK_D - (gt.Z_RB - gt.ROTOR_GAP_DRIP))
    line(f"wall film leaves the rotor lip at r={r_tip:.1f} < drain r={gt.R_DRAIN}", r_tip < gt.R_DRAIN)
    line(f"hood drip r={HOOD_DRIP_R}, foot drip r={FOOT_DRIP_R} > riser r={RISER_RO} (no water "
         f"into the riser), < drain r={gt.R_DRAIN}",
         RISER_RO + 1 < FOOT_DRIP_R <= HOOD_DRIP_R < gt.R_DRAIN)
    a_duct = math.pi * ((DUCT_ID / 2) ** 2 - (gt.PIPE_OD / 2) ** 2)
    rc = gt.PIPE_OD / 2 + 0.3 + 6
    a_lid = math.pi * (23.0 ** 2 - rc ** 2) - 3 * 8 * (23.0 - rc)
    a_win = 6 * 0.5 * 18 * 18
    a_ret = math.pi * (r_tip ** 2 - (FOOT_DRIP_R) ** 2)
    line(f"fog path areas: duct {a_duct:.0f}, lid pass {a_lid:.0f}, hood windows {a_win:.0f}, "
         f"return via rotor bore {a_ret:.0f} mm2", min(a_duct, a_lid, a_win) > 400 and a_ret > a_duct)
    fog_z = gt.SPRAY_Z + HEAD_WIN_Z - SEG_Z[-1]
    zi_top = max(zi for _, zi in PORTS)
    line(f"fog leaves the hood at top-segment z={fog_z:.1f} > top-row port axis z={zi_top:.0f}, "
         f"sinks past all 36 root zones (open chamber)", fog_z > zi_top)
    d_lip = min(math.hypot(x, y - FAN_Y) for x, y in BOX_DRAINS) - INLET_R - 2
    line(f"plenum condensate drains {d_lip:.0f} mm outside the fan inlet lip", d_lip > 5)
    cr_top = 39.0 - (WELL_R - CR_RO) + 7
    line(f"fogger float: waterline {wl:.1f} mm above its base, disc {DISC_DEPTH:.0f} mm deep; "
         f"cradle top {WL_MAX + cr_top - wl:.0f} at max fill {WL_MAX:.0f} < fan intake {Z_FAN_BOT:.1f}",
         0 < wl < 30 and WL_MAX + cr_top - wl < Z_FAN_BOT - 2)
    return allok


def mass_report(singles):
    print("-- 5. mass / torque budget")
    seg_g = vol(singles["segment"]) * ASA
    cap_g = vol(gt.make_cap()) * ASA
    rot_g = vol(gt.make_rotor()) * ASA
    asa = N_SEG * seg_g + cap_g + rot_g
    media = 36 * 0.150                          # wet 2" pot + media + seedling
    film = 0.3                                  # condensate on wall / lattice / roots
    mature = 36 * 0.200                         # extra once plants are grown
    print(f"  turning ASA: 4 x segment {seg_g:.0f} g + cap {cap_g:.0f} g + rotor {rot_g:.0f} g "
          f"= {asa / 1000:.2f} kg (thin walls print solid)")
    allok = True
    for label, kg, lim in (("planted", asa / 1000 + media + film, 0.5),
                           ("mature", asa / 1000 + media + film + mature, 0.75)):
        w = kg * 9.81
        t_ball = [mu * w * gt.RACE_R / 1000 for mu in (0.005, 0.01)]
        t_bush = 0.3 * 10.0 * (gt.STUB_D / 2 + 0.3) / 1000      # 10 N side load at the cap
        t = t_ball[1] + t_bush
        flag = t < 0.2 * lim
        allok &= flag
        print(f"  {label:8s} {kg:5.1f} kg: ball race {t_ball[0]:.3f}-{t_ball[1]:.3f} N m + bushing "
              f"{t_bush:.3f} = {t:.3f} N m = {t / 0.2 * 100:.0f} % of 0.2 N m (limit {lim * 100:.0f} %) "
              f"-> {ok(flag)}")
    return allok


# ---- section --------------------------------------------------------------------
def section(preview_parts, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Polygon

    def cut(m, ang):
        return m.rotate((0, 0, -ang)).rotate((-90, 0, 0)).slice(0.0).to_polygons()

    col = {"seg": "#d8cfae", "cap": "#cfc6aa", "mist": "#4a90c2", "duct": "#b7c7b0",
           "fan": "#7a6a55", "fog": "#e07b39", "fogger": "#333333", "pipe": "#9fb7c9",
           "rotor": "#b8862e", "lid": "#56645a", "tank": "#3d4a3f", "pod": "#7a6a55",
           "pinion": "#c9a227", "hub": "#2b2b2b", "leg": "#2b2b2b", "float": "#4a90c2",
           "pipe_foot": "#4a90c2", "fill": "#56645a"}

    def color(n):
        for k in sorted(col, key=len, reverse=True):
            if n.startswith(k):
                return col[k]
        return "#999999"

    fig, axs = plt.subplots(1, 2, figsize=(15, 15), dpi=100)
    for ax, ang, ttl in ((axs[0], 0.0, "cut at 0 deg (pockets, drive pod)"),
                         (axs[1], 90.0, "cut at 90 deg (fogger well +, fan box -)")):
        for name, m in preview_parts.items():
            for poly in cut(m, ang):
                ax.add_patch(Polygon(poly, closed=True, fc=color(name), ec="k", lw=0.3))
        blue = dict(arrowstyle="->", color="#1f77b4", lw=2)
        fog = dict(arrowstyle="->", color="#8a3ffc", lw=2)
        zj = gt.SPRAY_Z + JET_Z
        ax.annotate("", (0, zj - 15), (0, gt.TANK_FLOOR + 60), arrowprops=dict(blue, lw=1.5))
        for s in (1, -1):
            ax.annotate("", (s * (gt.R_TI - 2), zj - 6), (s * 14, zj), arrowprops=blue)
            ax.annotate("", (s * (gt.R_TI - 4), gt.Z_RT + 30), (s * (gt.R_TI - 4), zj - 30),
                        arrowprops=dict(blue, lw=1, ls="--"))
            ax.annotate("", (s * 50, gt.Z_L - 30), (s * 52, gt.Z_RB - 3), arrowprops=dict(blue, lw=1))
            # fog: out of the hood, down the chamber, back to the headspace
            ax.annotate("", (s * 60, gt.SPRAY_Z - 60), (s * 34, gt.SPRAY_Z - 35), arrowprops=fog)
            ax.annotate("", (s * 45, gt.Z_RT + 60), (s * 45, gt.SPRAY_Z - 80),
                        arrowprops=dict(fog, ls=":"))
            ax.annotate("", (s * 40, gt.Z_L - 25), (s * 42, gt.Z_RT + 40), arrowprops=dict(fog, lw=1))
        ax.annotate("", (8 if ang else 18, gt.SPRAY_Z - 60), (18, gt.Z_L + 20), arrowprops=fog)
        if ang:
            wl = WL_PREVIEW
            ax.plot([-gt.R_IN, gt.R_IN], [wl, wl], color="#1f77b4", lw=1, ls="--")
            ax.annotate("", (WELL_RC, 360), (WELL_RC, wl), arrowprops=fog)
            ax.annotate("", (FAN_Y, Z_FAN_BOT - 2), (WELL_RC - 30, 375), arrowprops=fog)
            ax.annotate("", (-12, RISER_TOP - 3), (FAN_Y + 10, Z_FLOOR_TOP + 4), arrowprops=fog)
            ax.text(WELL_RC + 32, wl - 25, "fogger float\n(slides on pipe)", fontsize=9)
            ax.text(FAN_Y - 70, Z_FAN_BOT - 35, "80 mm fan\n(box under lid)", fontsize=9)
            ax.text(-gt.R_IN + 6, wl + 6, "waterline", fontsize=8, color="#1f77b4")
        else:
            ax.text(70, gt.SPRAY_Z - 20, "mist head: jets (flush)\n+ fog hood", fontsize=9)
            ax.text(-gt.R_IN - 5, gt.SPRAY_Z - 300, "gyroid skin\noutside a\nsolid wall", fontsize=9)
            ax.text(-25, (gt.Z_L + gt.SPRAY_Z) / 2, "DN50\nduct", fontsize=8)
        ax.set_xlim(-170, 170)
        ax.set_ylim(WL_PREVIEW - 70, CAP_Z + 40)
        ax.set_aspect("equal")
        ax.grid(alpha=0.25)
        ax.set_title(ttl, fontsize=10)
    fig.suptitle("Gyroid Mist Shell: blue = flush water, purple = fog loop", fontsize=13)
    fig.savefig(path, bbox_inches="tight")


# ---- main ------------------------------------------------------------------------
ORIENT = {
    "segment": (None, "spigot down"),
    "mist_head": (FLIP, "stub down+brim"),
    "duct_foot": (None, "skirt down"),
    "fan_box": (None, "floor down"),
    "fan_roof": (None, "plate down"),
    "fog_float": (None, "base down"),
    "fog_cradle": (None, "lip down"),
}


def main():
    print("-- build")
    parts, leg = gt.build_base()
    seg = make_segment(make_lattice())
    for k in range(N_SEG):
        parts[f"seg_{k + 1}"] = place_seg(seg, k)
    parts["duct"] = make_duct()
    parts["duct_foot"] = make_duct_foot()
    parts["mist_head"] = make_mist_head()
    parts["fan_box"] = make_fan_box()
    parts["fan_roof"] = make_fan_roof()
    wl, lip, m_pl, load = float_balance()
    zf = WL_PREVIEW - wl
    parts["fog_float"] = make_fog_float().translate((0, 0, zf))
    parts["fog_cradle"] = make_fog_cradle(lip).translate((0, 0, zf))
    print(f"  float + cradle {m_pl:.0f} g, displaces {load:.0f} g, waterline {wl:.1f} mm, "
          f"lip at {lip:.1f} mm (float local)")
    print(f"  stack: {N_SEG} segments x {SEG_PITCH:.0f} pitch, cap seat z={CAP_Z:.1f}, height "
          f"{CAP_Z + 8 + gt.HUB_T:.0f} mm on the stand; duct PVC DN50 cut to {DUCT_Z1 - DUCT_Z0:.0f} mm")

    allok = checks(parts, seg, wl)

    singles = {"segment": seg, "mist_head": parts["mist_head"], "duct_foot": parts["duct_foot"],
               "fan_box": parts["fan_box"], "fan_roof": parts["fan_roof"],
               "fog_float": make_fog_float(), "fog_cradle": make_fog_cradle(lip)}
    print("-- 4. print checks (triangles, overhang area in print orientation)")
    for n, m in singles.items():
        rot = ORIENT[n][0]
        a45, a60, big, area = overhang(m, rot)
        tri_ok = m.num_tri() < 1.5e6
        allok &= tri_ok
        print(f"  {n:11s} {m.num_tri():8d} tris {ok(tri_ok)}  overhang >45: {a45:7.0f} mm2 "
              f"({a45 / area * 100:4.1f} %), >60: {a60:6.0f} mm2, largest >60 patch {big:5.1f} mm2")
    preview = {}
    for n in parts:
        if n.startswith(("seg_", "duct", "mist", "fan_", "fog_")):
            preview[n] = parts[n]
        elif n.startswith("leg"):
            preview[n] = f"preview/{n}.stl"
        else:
            preview[n] = f"preview/{n}.stl"
    preview["pipe"] = "preview/pipe.stl"
    preview["cap"] = "preview/cap.stl"
    preview["fan"] = fan_dummy()
    puck = cyl(FOG_H, FOG_D / 2, z=lip, y=WELL_RC, seg=64)
    preview["fogger"] = (puck + cyl(1.0, 13, z=lip + FOG_H, y=WELL_RC, seg=48)).translate((0, 0, zf))
    meta = {n: gt.base_meta(n) for n in preview if isinstance(preview[n], str) and n != "cap"}
    for k in range(N_SEG):
        meta[f"seg_{k + 1}"] = ("#e3dcc2" if k % 2 == 0 else "#d3caa9", 4 + 1.2 * k, True)
    meta["cap"] = ("#cfc6aa", 4 + 1.2 * N_SEG + 0.6, True)
    meta["mist_head"] = ("#4a90c2", 4 + 1.2 * N_SEG)
    meta["duct"] = ("#b7c7b0", 3.0)
    meta["duct_foot"] = ("#7a6a55", 2.6)
    meta["fan_box"] = ("#7a6a55", 1.0)
    meta["fan_roof"] = ("#8f7d63", 1.5)
    meta["fan"] = ("#2b2b2b", 0.6)
    meta["fog_float"] = ("#e07b39", 0.0)
    meta["fog_cradle"] = ("#c9662a", -0.3)
    meta["fogger"] = ("#333333", -0.5)
    qty = {"segment": N_SEG}
    allok &= gt.export_set(HERE, singles, ORIENT, qty, preview, meta,
                           f"Gyroid Mist Shell: {N_SEG} segments x {len(PORTS)} pockets, fog loop")
    allok &= mass_report(singles)
    sec = {n: m for n, m in parts.items() if not n.startswith(("leg", "hub"))}
    sec["pipe"] = gt.pipe()
    sec["cap"] = gt.make_cap()
    sec["fan"] = fan_dummy()
    sec["fogger"] = preview["fogger"]
    section(sec, os.path.join(HERE, "preview", "section_2d.png"))
    print(f"-- all checks -> {ok(allok)}")


if __name__ == "__main__":
    main()
