"""Rotating outdoor aeroponic grow tower, printable on a 256 x 256 bed (ASA).

The layout follows the Tower Garden style of vertical aeroponics. A pump in the
base tank pushes nutrient water up a centre pipe to a spray head at the top.
The water runs down the inside of the stacked tiers, over the roots that hang
out of the net pots, and drips back into the tank.  On top of that we add
Enova-style rotation, so every side gets the same amount of sun.

Only the tier stack turns.  The tank, the pipe and the spray head stay still.
The stack sits on a ROTOR ring that runs on 6 mm balls in matching V-grooves
in the tank lid and the rotor.  It is kept centred by those grooves, and the
top cap's bushing rides on the spray head's stub.  Water falls through the
open rotor into the lid drain, so no rotating water seal is needed.  A
28BYJ-48 stepper in a pod on the lid drives the rotor's 128T ring gear
through a 15T pinion.

  ground --- HUB + 4 LEGS (stand, tank lifts out)
             TANK_BOTTOM + N_RINGS x TANK_RING  (O-ring sealed spigot joints)
             LID  (ball race, drain, pipe collar, fill port, gland, pod mount)
             POD_BASE + POD_ROOF (28BYJ-48) + PINION
             ROTOR (ball race + ring gear + tier socket)
             N_TIERS x TIER (6 x 2" net-pot ports, stack rotated 30 deg)
             CAP (bushing on the spray-head stub)
  inside --- PIPE (1/2" PVC, cut to length) in PIPE_FOOT, SPRAY_HEAD on top,
             FLOAT_BRACKET (M10 float switch) clamps on the pipe

Parts are exported in print orientation; preview/ has assembled copies.
Run: PYTHONPATH=../../.pydeps python3 grow_tower.py
"""
import math
import os

import numpy as np
import manifold3d as m3d

SEG = 192
OUT = os.path.dirname(os.path.abspath(__file__))

# ---- parameters (mm) -------------------------------------------------------
BED = 256.0           # printer bed (Bambu X1/P1/A1)
BED_MARGIN = 3.0      # keep this far from the bed edge
CLR = 0.4             # FDM sliding-fit clearance per side
HOLE_COMP = 0.2       # FDM holes print small: added to small hole diameters
EF = 0.6              # lead-in / elephant-foot chamfer

PIPE_OD = 21.3        # 1/2" sch40 PVC (use 20.0 for metric 20 mm pipe)
PIPE_ID = 15.8

# tank: bottom cup + N_RINGS rings, radial O-ring seal at every joint
TANK_R = 118.0        # outer wall radius
TANK_WALL = 4.0
TANK_FLOOR = 5.0
SEC_H = 150.0         # height of every tank section (wall top to wall top)
N_RINGS = 2
COLLAR_T = 4.0        # socket collar thickness (outside the wall)
COLLAR_H = 20.0       # socket depth = spigot length
SPIG_T = 6.0          # spigot wall (thickened inward to carry the groove)
SEAL_GAP = 0.2        # radial clearance spigot / collar at a sealed joint
ORING = 3.0           # O-ring cord diameter
GROOVE_D = 2.4        # gland depth -> 0.4 mm squeeze (13 %) on a 3 mm cord
GROOVE_W = 3.8
FOOT_RING_R = 45.0    # locating ring on the tank floor for the pipe foot

# lid
LID_T = 6.0           # plate (holds the 2.5 mm deep ball groove)
LID_RIB_H = 10.0
R_DRAIN = 56.0        # drain opening under the rotor
RACE_R = 67.0         # ball circle radius (lid + rotor V-grooves)
BALL = 6.0            # 6 mm balls: stainless or airsoft BBs
V_DEPTH = 2.5         # 90 deg V-groove depth in each face
FILL_ANG, FILL_R, FILL_D = 180.0, 104.0, 18.0
GLAND_ANG, GLAND_R, GLAND_D = 90.0, 104.0, 12.7   # PG7 / M12 cable gland

# drive: 28BYJ-48 stepper -> 15T pinion -> 128T ring gear on the rotor
MOD = 1.5
N_GEAR, N_PIN = 128, 15
GEAR_W = 8.0
BACKLASH = 0.25       # circular backlash at the pitch circle, per gear
POD_ANG = 0.0
# 28BYJ-48: body d28 x 19, tabs on 35 mm centres (4.2 holes), shaft 8 mm
# off the body centre, d9 x 1.5 boss, d5 shaft with 3 mm flats
BYJ_BODY_D, BYJ_BODY_H = 28.0, 19.0
BYJ_TAB = 35.0
BYJ_OFF = 8.0
BYJ_BOSS = 9.0
BYJ_SHAFT, BYJ_FLAT = 5.0, 3.0
POD_WALL = 2.4
POD_FLOOR = 2.4
POD_CAV_H = 24.0
ROOF_T = 2.5
# cavity in pod coords (origin = shaft, x radial out, y tangential)
POD_X = (-23.0, 23.0)
POD_Y = (-9.0, 28.0)

# rotor + tiers (tier column = Tower-Garden-like 152 mm tube)
R_TO = 76.0           # tier column outer radius
R_TI = 72.6           # tier column inner radius (also the rotor socket bore)
R_SO = R_TI - CLR     # spigot outer
R_SI = R_SO - (R_TO - R_TI)   # spigot inner (keeps the 45 deg shoulder even)
SPIG_L = 12.0         # tier spigot length below the seat
RIM_CH = 2.0          # 45 deg seat chamfer on every socket rim
TIER_H = 122.4        # tier body height above its seat
PITCH = TIER_H - RIM_CH - CLR     # tier-to-tier spacing once seated (120)
SEAT_DROP = RIM_CH + CLR          # seat sits this far below a rim top
N_TIERS = 6
N_PORT = 6
PORT_TILT = 45.0      # port axis from vertical
PORT_ID = 52.0        # 2" net pot (50 mm body), lip rests on the mouth
PORT_WALL = 2.4
PORT_ZI = 50.0        # port axis meets the column inner face here (tier local)
PORT_R_MOUTH = 102.0  # mouth centre radius
SOCK_D = 16.0         # rotor socket depth
ROTOR_GAP_DRIP = 2.0  # drip lip tip sits this far below the rotor face

# top: spray head on the pipe, cap bushing rides on its stub
STUB_D = 16.0
SPRAY_HOLES, SPRAY_HOLE_D = 8, 2.2
HUB_ENGAGE = 16.0

# stand
HUB_T = 20.0
HUB_R = 123.5
LEG_W = 30.0
LEG_R_END = 335.0     # foot radius (670 mm footprint)
LEG_ANGS = (45.0, 135.0, 225.0, 315.0)
LEG_BOLTS_R = (60.0, 100.0)    # M5 bolts
STAKE_R, STAKE_D = 315.0, 8.5

# ---- derived stack heights (z = 0 at the tank floor underside) -------------
RC = TANK_R + SEAL_GAP + COLLAR_T          # collar outer radius
R_IN = TANK_R - TANK_WALL                  # tank inner radius
Z_LID0 = SEC_H * (N_RINGS + 1)             # lid spigot bottom = top wall top
Z_L = Z_LID0 + COLLAR_H + LID_T            # lid top face
BALL_RISE = BALL / 2 * math.sqrt(2)        # ball centre above a 90 deg V apex
Z_RB = Z_L - V_DEPTH + 2 * BALL_RISE - V_DEPTH + 0.02   # rotor underside
POD_TOP = Z_L + POD_FLOOR + POD_CAV_H + ROOF_T
GEAR_Z0 = POD_TOP + 1.0
Z_RT = GEAR_Z0 + GEAR_W                    # rotor top (= gear top)
CENTRE_DIST = MOD * (N_GEAR + N_PIN) / 2
TIER_Z = [Z_RT - SEAT_DROP + k * PITCH for k in range(N_TIERS)]
CAP_Z = TIER_Z[-1] + PITCH
SPRAY_Z = CAP_Z - 31.0                     # pipe top / spray head origin
FOOT_H = 45.0
FOOT_SOCK = 30.0
PIPE_Z0 = TANK_FLOOR + FOOT_H - FOOT_SOCK  # pipe bottom (in the foot socket)
PIPE_LEN = SPRAY_Z - PIPE_Z0


# ---- helpers ---------------------------------------------------------------
def revolve(poly, seg=SEG):
    return m3d.Manifold.revolve(m3d.CrossSection([poly]), seg)


def tube(r0, r1, z0, z1, seg=SEG):
    return revolve([(r0, z0), (r1, z0), (r1, z1), (r0, z1)], seg)


def cyl(h, r, z=0.0, x=0.0, y=0.0, seg=64):
    return m3d.Manifold.cylinder(h, r, r, seg).translate((x, y, z))


def box(x0, x1, y0, y1, z0, z1):
    return m3d.Manifold.cube((x1 - x0, y1 - y0, z1 - z0)).translate((x0, y0, z0))


def polar(r, ang):
    a = math.radians(ang)
    return r * math.cos(a), r * math.sin(a)


def vol(m):
    return m.volume() if hasattr(m, "volume") else m.get_properties().volume


def union(parts):
    return m3d.Manifold.batch_boolean(list(parts), m3d.OpType.Add)


def v_groove(r, z_face, up):
    """90 deg V-groove cutter, apex V_DEPTH into the face (up = into +z)."""
    s = 1 if up else -1
    pts = [(r - V_DEPTH, z_face - s * 0.01), (r + V_DEPTH, z_face - s * 0.01),
           (r, z_face + s * V_DEPTH)]
    return revolve(pts if up else pts[::-1])


def countersink(x, y, z_face, d, head, down=True):
    """Through hole d with a 90 deg countersink at z_face (head on that face)."""
    k = head / 2 - d / 2
    if down:      # face at z_face, material below it
        c = m3d.Manifold.cylinder(k + 0.01, d / 2, head / 2 + 0.01, 48)
        c = c.translate((x, y, z_face - k))
        return c + cyl(80, d / 2, z=z_face - 79.99, x=x, y=y, seg=32)
    c = m3d.Manifold.cylinder(k + 0.01, head / 2 + 0.01, d / 2, 48)
    c = c.translate((x, y, z_face - 0.01))
    return c + cyl(80, d / 2, z=z_face, x=x, y=y, seg=32)


# ---- involute gears ----------------------------------------------------------
def gear2d(n, m=MOD, backlash=BACKLASH, pa=20.0):
    """External involute spur gear outline (CrossSection), tooth 0 on +X."""
    pa = math.radians(pa)
    rp = m * n / 2
    rb = rp * math.cos(pa)
    ra = rp + m
    rf = rp - 1.25 * m
    inv = lambda a: math.tan(a) - a
    half = (math.pi * m / 2 - backlash) / (2 * rp) + inv(pa)

    def theta(r):
        return half - inv(math.acos(min(1.0, rb / r)))

    r0 = max(rb, rf)
    rs = np.linspace(r0, ra, 12)
    flank = [(r, theta(r)) for r in rs]
    side = [(rf - 0.3, theta(r0))] + flank
    tooth = [(r * math.cos(-t), r * math.sin(-t)) for r, t in side]
    tip = [(ra * math.cos(a), ra * math.sin(a))
           for a in np.linspace(-theta(ra), theta(ra), 5)[1:-1]]
    tooth += tip + [(r * math.cos(t), r * math.sin(t)) for r, t in side[::-1]]
    polys = []
    for k in range(n):
        a = 2 * math.pi * k / n
        c, s = math.cos(a), math.sin(a)
        polys.append([(x * c - y * s, x * s + y * c) for x, y in tooth])
    root = [(rf * math.cos(a), rf * math.sin(a))
            for a in np.linspace(0, 2 * math.pi, 4 * n, endpoint=False)]
    return m3d.CrossSection(polys + [root], m3d.FillRule.Positive)


# ---- tank ----------------------------------------------------------------------
def collar(zw):
    """Socket collar around a wall top at zw (receives the next spigot)."""
    z0 = zw - (RC - TANK_R)
    ri = TANK_R + SEAL_GAP
    return revolve([(TANK_R - 0.5, z0 - 0.5), (RC, zw), (RC, zw + COLLAR_H - EF),
                    (RC - EF, zw + COLLAR_H), (ri + 0.8, zw + COLLAR_H),
                    (ri, zw + COLLAR_H - 0.8), (ri, zw), (TANK_R - 0.5, zw)])


def spigot(zb, r_out=TANK_R, groove=True, t=SPIG_T):
    """Spigot ring zb .. zb + COLLAR_H (drops into the collar below)."""
    s = revolve([(r_out - t, zb), (r_out - EF, zb), (r_out, zb + EF),
                 (r_out, zb + COLLAR_H + 0.01), (r_out - t, zb + COLLAR_H + 0.01)])
    if groove:
        zg = zb + COLLAR_H / 2
        s = s - tube(r_out - GROOVE_D, r_out + 1, zg - GROOVE_W / 2, zg + GROOVE_W / 2)
    return s


def make_tank_bottom():
    t = tube(0, TANK_R, 0, TANK_FLOOR)
    t = t - revolve([(TANK_R - EF, -1), (TANK_R + 1, -1), (TANK_R + 1, EF)])
    t = t + tube(R_IN, TANK_R, TANK_FLOOR - 0.01, SEC_H)
    t = t + collar(SEC_H)
    t = t + tube(FOOT_RING_R + CLR, FOOT_RING_R + CLR + 3, TANK_FLOOR - 0.01, TANK_FLOOR + 4)
    return t


def make_tank_ring(k):
    """Ring k (1..N_RINGS): spigot into the section below, collar on top."""
    zb = SEC_H * k
    r = spigot(zb)
    r = r + tube(R_IN, TANK_R, zb + COLLAR_H, zb + SEC_H)
    return r + collar(zb + SEC_H)


# ---- lid -------------------------------------------------------------------------
def pod_xy(x, y):
    """Pod coords (origin at the pinion shaft) -> world XY."""
    a = math.radians(POD_ANG)
    xr = CENTRE_DIST + x
    return xr * math.cos(a) - y * math.sin(a), xr * math.sin(a) + y * math.cos(a)


POD_SCREWS = [(-12.0, -5.0), (8.0, -6.0)]   # M4 pod -> lid, clear of the motor


def make_lid():
    zp = Z_L - LID_T
    lid = tube(0, RC, zp, Z_L)
    lid = lid - revolve([(RC + 1, Z_L - EF - 1), (RC + 1, Z_L + 1), (RC - EF - 1, Z_L + 1)])
    lid = lid + spigot(Z_LID0, TANK_R - (CLR - SEAL_GAP), groove=False, t=4.0)
    r_sp = TANK_R - (CLR - SEAL_GAP) - 4.0
    for k in range(8):                                   # ribs under the plate
        rib = box(R_DRAIN + 2, r_sp + 0.5, -1.5, 1.5, zp - LID_RIB_H, zp + 0.01)
        lid = lid + rib.rotate((0, 0, 22.5 + 45 * k))
    lid = lid + tube(R_DRAIN, R_DRAIN + 3, zp - LID_RIB_H, zp + 0.01)
    # drain opening with 3 spokes to the pipe collar
    lid = lid - revolve([(0, zp - 1), (R_DRAIN, zp - 1), (R_DRAIN, Z_L - 2),
                         (R_DRAIN + 2, Z_L + 0.01), (0, Z_L + 0.01)])
    rc_in = (PIPE_OD + 0.6) / 2
    lid = lid + tube(rc_in, rc_in + 6, zp, Z_L)
    for k in range(3):
        lid = lid + box(rc_in + 3, R_DRAIN + 1, -4, 4, zp, Z_L).rotate((0, 0, 30 + 120 * k))
    lid = lid - v_groove(RACE_R, Z_L, up=False)
    x, y = polar(FILL_R, FILL_ANG)
    lid = lid - cyl(LID_T + 2, FILL_D / 2, z=zp - 1, x=x, y=y)
    x, y = polar(GLAND_R, GLAND_ANG)
    lid = lid - cyl(LID_T + 2, (GLAND_D + HOLE_COMP) / 2, z=zp - 1, x=x, y=y)
    for sx, sy in POD_SCREWS:                            # M4 self-tap pilots
        x, y = pod_xy(sx, sy)
        lid = lid - cyl(LID_T + 8, 1.7, z=Z_L - LID_T - 6, x=x, y=y, seg=24)
    return lid


def make_fill_plug():
    """Push-in plug for the fill port: cap on the lid, hollow stem, pry notch."""
    x, y = polar(FILL_R, FILL_ANG)
    p = cyl(3.0, 13.0, z=Z_L, seg=96)
    p = p + cyl(LID_T + 0.01, FILL_D / 2 - 0.25, z=Z_L - LID_T, seg=96)
    p = p - cyl(LID_T, FILL_D / 2 - 2.0, z=Z_L - LID_T - 0.01, seg=96)
    p = p - box(9.0, 14.0, -3.0, 3.0, Z_L + 1.5, Z_L + 4.0)        # pry notch
    return p.translate((x, y, 0))


# ---- drive pod -----------------------------------------------------------------
def pod_frame(m):
    """Pod local (x radial, y tangential, z world) -> world."""
    return m.translate((CENTRE_DIST, 0, 0)).rotate((0, 0, POD_ANG))


POD_OUT = (POD_X[0] - POD_WALL, POD_X[1] + POD_WALL, POD_Y[0] - POD_WALL, POD_Y[1] + POD_WALL)
POD_POSTS = [(POD_X[0] + 3.5, POD_Y[0] + 3.5), (POD_X[1] - 3.5, POD_Y[0] + 3.5),
             (POD_X[0] + 3.5, POD_Y[1] - 3.5), (POD_X[1] - 3.5, POD_Y[1] - 3.5)]


def make_pod_base():
    x0, x1, y0, y1 = POD_OUT
    zt = Z_L + POD_FLOOR + POD_CAV_H
    p = box(x0, x1, y0, y1, Z_L, zt)
    p = p - box(*POD_X, *POD_Y, Z_L + POD_FLOOR, zt + 1)
    for px, py in POD_POSTS:
        p = p + box(px - 3.5, px + 3.5, py - 3.5, py + 3.5, Z_L, zt)
        p = p - cyl(16, 1.3, z=zt - 15, x=px, y=py, seg=24)            # M3 pilot
    for sx, sy in POD_SCREWS:
        p = p - cyl(POD_FLOOR + 2, (4.0 + HOLE_COMP) / 2 + 0.1, z=Z_L - 1, x=sx, y=sy, seg=32)
    p = p - box(POD_X[1] - 1, x1 + 1, 5, 17, Z_L + POD_FLOOR - 0.01, Z_L + POD_FLOOR + 8)
    p = p - cyl(POD_FLOOR + 2, 2.0, z=Z_L - 1, x=POD_X[0] + 9, y=POD_Y[1] - 3)  # drain
    return pod_frame(p)


def make_pod_roof():
    x0, x1, y0, y1 = POD_OUT
    zr = Z_L + POD_FLOOR + POD_CAV_H
    o = 1.6 + CLR                                           # skirt outside the walls
    r = box(x0 - o, x1 + o, y0 - o, y1 + o, zr, zr + ROOF_T)
    skirt = box(x0 - o, x1 + o, y0 - o, y1 + o, zr - 5, zr + 0.01)
    skirt = skirt - box(x0 - CLR, x1 + CLR, y0 - CLR, y1 + CLR, zr - 6, zr + 1)
    r = r + skirt
    r = r - cyl(ROOF_T + 2, (BYJ_BOSS + 1.0) / 2, z=zr - 1, seg=48)    # shaft boss
    for sx in (-BYJ_TAB / 2, BYJ_TAB / 2):                  # motor tabs, M3 csk
        r = r - countersink(sx, BYJ_OFF, zr + ROOF_T, 3.4, 6.4)
    for px, py in POD_POSTS:
        r = r - countersink(px, py, zr + ROOF_T, 3.4, 6.4)
    return pod_frame(r)


def make_pinion():
    g = gear2d(N_PIN).extrude(GEAR_W)
    bore = m3d.CrossSection.circle((BYJ_SHAFT + HOLE_COMP) / 2, 32)
    bore = bore ^ m3d.CrossSection.square((BYJ_FLAT + 0.15, 10), True)
    g = g - bore.extrude(GEAR_W + 2).translate((0, 0, -1))
    g = g - revolve([(0, -1), (BYJ_SHAFT / 2 + 0.9, -1), (0, 0.8 + BYJ_SHAFT / 2)], 32)
    return g.rotate((0, 0, 180 / N_PIN)).translate((0, 0, GEAR_Z0))


def place_pinion(p, extra=0.0):
    return pod_frame(p.rotate((0, 0, extra)))


# ---- rotor -----------------------------------------------------------------------
def make_rotor():
    zt = Z_RB - ROTOR_GAP_DRIP
    r_tip = R_TI - (Z_RT - SOCK_D - zt)
    r = revolve([(r_tip, zt), (r_tip + 2, zt), (r_tip + 2 + ROTOR_GAP_DRIP, Z_RB),
                 (R_TO, Z_RB), (R_TO, Z_RT), (R_TI + RIM_CH, Z_RT),
                 (R_TI, Z_RT - RIM_CH), (R_TI, Z_RT - SOCK_D)])
    gear = gear2d(N_GEAR) - m3d.CrossSection.circle(R_TO - 0.1, SEG)
    r = r + gear.extrude(GEAR_W).translate((0, 0, GEAR_Z0))
    r = r - v_groove(RACE_R, Z_RB, up=True)
    # gap of the ring gear on the pod side so the pinion tooth drops in
    return r.rotate((0, 0, POD_ANG + 180 / N_GEAR))


# ---- tiers -----------------------------------------------------------------------
def port_axis(s):
    """Point on a port axis (in the r-z plane) at distance s from the inner face."""
    a = math.radians(PORT_TILT)
    return R_TI + s * math.sin(a), PORT_ZI + s * math.cos(a)


PORT_L = (PORT_R_MOUTH - R_TI) / math.sin(math.radians(PORT_TILT))


def port_cyl(r, s0, s1, seg=96):
    c = m3d.Manifold.cylinder(s1 - s0, r, r, seg).rotate((0, PORT_TILT, 0))
    x, z = port_axis(s0)
    return c.translate((x, 0, z))


def make_tier():
    """One tier, local z = 0 at its seat, ports at 0, 60, ... deg."""
    outer = revolve([(0, -SPIG_L), (R_SO - EF, -SPIG_L), (R_SO, -SPIG_L + EF),
                     (R_SO, 0), (R_TO, R_TO - R_SO), (R_TO, TIER_H), (0, TIER_H)])
    ro = PORT_ID / 2 + PORT_WALL
    tubes = [port_cyl(ro, -20, PORT_L).rotate((0, 0, 360 / N_PORT * j)) for j in range(N_PORT)]
    t = union([outer] + tubes)
    void = revolve([(0, -SPIG_L - 1), (R_SI, -SPIG_L - 1), (R_SI, 0), (R_TI, R_TI - R_SI),
                    (R_TI, TIER_H - RIM_CH), (R_TI + RIM_CH, TIER_H),
                    (R_TI + RIM_CH, TIER_H + 1), (0, TIER_H + 1)])
    bores = [port_cyl(PORT_ID / 2, -20, PORT_L + 1).rotate((0, 0, 360 / N_PORT * j))
             for j in range(N_PORT)]
    return t - union([void] + bores)


def place_tier(t, k):
    return t.rotate((0, 0, 30 * k)).translate((0, 0, TIER_Z[k]))


# ---- top -------------------------------------------------------------------------
def make_cap():
    hub_r = (STUB_D + 0.6) / 2
    c = revolve([(R_SI, -SPIG_L), (R_SO - EF, -SPIG_L), (R_SO, -SPIG_L + EF), (R_SO, 0),
                 (R_TO, R_TO - R_SO), (R_TO + 2, R_TO - R_SO), (R_TO + 2, 7.8),
                 (0, 7.8), (0, R_TO - R_SO), (R_TI, R_TO - R_SO), (R_SI, 0)])
    stub_top = SPRAY_Z + 34.0 - CAP_Z
    hub_bot = stub_top - HUB_ENGAGE
    c = c + tube(hub_r, hub_r + 4.5, hub_bot, R_TO - R_SO + 0.01, 96)
    c = c - cyl(stub_top + 1.5 - hub_bot + 1, hub_r, z=hub_bot - 1, seg=96)   # blind bore
    c = c - revolve([(hub_r - 0.01, hub_bot - 1), (hub_r + 1.5, hub_bot - 1),
                     (hub_r - 0.01, hub_bot + 0.5)], 96)
    return c.translate((0, 0, CAP_Z))


def make_spray_head():
    """Local z = 0 at the pipe top: sleeve on the pipe, chamber, jets, stub."""
    s = revolve([(PIPE_OD / 2 + 0.2, -30), (15, -30), (15, 14), (STUB_D / 2, 14),
                 (STUB_D / 2, 33.4), (STUB_D / 2 - 0.6, 34), (0, 34), (0, 20),
                 (8, 12), (8, 3.0), (PIPE_OD / 2 + 0.2, 3.0 - (PIPE_OD / 2 + 0.2 - 8))])
    for k in range(SPRAY_HOLES):
        h = m3d.Manifold.cylinder(20, (SPRAY_HOLE_D + HOLE_COMP) / 2,
                                  (SPRAY_HOLE_D + HOLE_COMP) / 2, 24)
        s = s - h.rotate((0, 90, 0)).translate((0, 0, 6)).rotate((0, 0, 360 / SPRAY_HOLES * k + 22.5))
    pin = m3d.Manifold.cylinder(20, 1.7, 1.7, 24).rotate((0, 90, 0)).translate((0, 0, -15))
    return (s - pin).translate((0, 0, SPRAY_Z))


def make_pipe_foot():
    z0 = TANK_FLOOR
    f = cyl(5.0, FOOT_RING_R, z=z0, seg=128)
    f = f + cyl(FOOT_H, 22.0, z=z0, seg=96)
    f = f - cyl(FOOT_SOCK + 1, (PIPE_OD + 0.4) / 2, z=z0 + FOOT_H - FOOT_SOCK, seg=96)
    f = f - cyl(FOOT_H - FOOT_SOCK - 3 + 0.01, 5.0, z=z0 + 3, seg=48)
    # 1/2" hose barb, tangent to the base disc so it prints without support
    zc = z0 + 5.0 + 7.25
    barb = m3d.Manifold.cylinder(26, 6.25, 6.25, 48)
    for k in range(3):
        barb = barb + m3d.Manifold.cylinder(5, 7.25, 6.25, 48).translate((0, 0, 8 + 6 * k))
    barb = barb.rotate((0, 90, 0)).translate((18, 0, zc))
    f = f + barb
    f = f - m3d.Manifold.cylinder(40, 4.0, 4.0, 32).rotate((0, 90, 0)).translate((0, 0, zc))
    return f


def make_float_bracket():
    """Clamp on the pipe; arm holds an M10 vertical float switch."""
    ri = PIPE_OD / 2 + 0.15
    ro = ri + 4.0
    ring = m3d.CrossSection.circle(ro, 96) - m3d.CrossSection.circle(ri, 96)
    arm = m3d.CrossSection.square((40, 14)).translate((ro - 2, -7))
    boss = m3d.CrossSection.circle(10, 64).translate((ro + 40, 0))
    ears = m3d.CrossSection.square((10, 12)).translate((-ro - 8, -6))
    cs = ring + arm + boss + ears
    cs = cs - m3d.CrossSection.square((ro + 10, 2.0)).translate((-ro - 9, -1.0))
    cs = cs - m3d.CrossSection.circle(5.2 + HOLE_COMP / 2, 48).translate((ro + 40, 0))
    b = cs.extrude(10.0)
    pinch = m3d.Manifold.cylinder(20, 1.7, 1.7, 24).rotate((90, 0, 0)).translate((-ro - 4, 10, 5))
    return b - pinch


def pipe():
    return tube(PIPE_ID / 2, PIPE_OD / 2, PIPE_Z0, SPRAY_Z, 64)


# ---- stand -------------------------------------------------------------------------
def make_hub():
    h = cyl(HUB_T, HUB_R, z=-HUB_T, seg=SEG)
    cav = cyl(15.0, 116.0, z=-HUB_T - 0.01, seg=SEG) - cyl(16, 32.0, z=-HUB_T - 1)
    for a in LEG_ANGS:
        cav = cav - box(0, 130, -(LEG_W / 2 + CLR + 4), LEG_W / 2 + CLR + 4,
                        -HUB_T - 1, 0).rotate((0, 0, a))
    for a in LEG_ANGS:
        cav = cav - box(0, 130, -2, 2, -HUB_T - 1, 0).rotate((0, 0, a + 45))
    h = h - cav
    for a in LEG_ANGS:
        h = h - box(32.0, 130, -(LEG_W / 2 + CLR), LEG_W / 2 + CLR,
                    -HUB_T - 0.01, -5.0).rotate((0, 0, a))
        for r in LEG_BOLTS_R:
            x, y = polar(r, a)
            h = h - countersink(x, y, 0.0, 5.5, 10.5)
    return h


def make_leg():
    """Leg in local coords: x = radius along the leg, z world, width in y."""
    prof = [(32.4, -HUB_T), (LEG_R_END, -HUB_T), (LEG_R_END, 0.0), (160.0, 15.0),
            (TANK_R + 0.8, 15.0), (TANK_R + 0.8, 0.4), (HUB_R + CLR, 0.4),
            (HUB_R + CLR, -5.0 - CLR), (32.4, -5.0 - CLR)]
    leg = m3d.CrossSection([prof]).extrude(LEG_W).translate((0, 0, -LEG_W / 2))
    leg = leg.rotate((90, 0, 0))                       # profile x-z, width along y
    for r in LEG_BOLTS_R:
        leg = leg - cyl(40, (5.0 + HOLE_COMP) / 2 + 0.1, z=-HUB_T - 1, x=r, seg=32)
        nut = m3d.CrossSection.circle(8.3 / math.sqrt(3), 6).extrude(5.0)
        leg = leg - nut.translate((r, 0, -HUB_T - 0.01))
    leg = leg - cyl(60, STAKE_D / 2, z=-HUB_T - 1, x=STAKE_R, seg=32)
    return leg


def place_leg(leg, a):
    return leg.rotate((0, 0, a))


# ---- checks ------------------------------------------------------------------------
def drop_check(moving, fixed, travel, wig=CLR, lift=0.05, step=0.5):
    """Lower `moving` onto `fixed` from `travel` mm above.  Returns (worst
    overlap along the path down to `step` above the seat, overlap pushed
    0.3 mm past the seat, sideways wiggle at `lift` above the seat).  Cone
    seats need lift > wiggle, flat seats do not."""
    worst = 0.0
    for d in np.arange(travel, step / 2, -step):
        worst = max(worst, vol(moving.translate((0, 0, d)) ^ fixed))
    wiggle = 0.0
    for a in range(0, 360, 45):
        dx, dy = polar(0.9 * wig, a)
        wiggle = max(wiggle, vol(moving.translate((dx, dy, lift)) ^ fixed))
    return worst, vol(moving.translate((0, 0, -0.3)) ^ fixed), wiggle


def bed_fit(tm):
    """Smallest square side the part's footprint needs over all Z rotations."""
    pts = tm.vertices[:, :2]
    best = (1e9, 0)
    for a in range(0, 90, 1):
        c, s = math.cos(math.radians(a)), math.sin(math.radians(a))
        p = pts @ np.array([[c, -s], [s, c]])
        side = max(np.ptp(p[:, 0]), np.ptp(p[:, 1]))
        best = min(best, (side, a))
    return best


def to_trimesh(m):
    import trimesh
    mesh = m.to_mesh()
    verts = np.asarray(mesh.vert_properties)[:, :3]
    return trimesh.Trimesh(verts, np.asarray(mesh.tri_verts), process=False)


def ok(flag):
    return "OK" if flag else "FAIL"


def build_base():
    """Everything below the turning stack: stand, tank, lid, drive, rotor,
    pipe foot.  Shared by the classic tower and every concept tower."""
    parts = {}
    parts["tank_bottom"] = make_tank_bottom()
    for k in range(1, N_RINGS + 1):
        parts[f"tank_ring_{k}"] = make_tank_ring(k)
    parts["lid"] = make_lid()
    parts["fill_plug"] = make_fill_plug()
    parts["pod_base"] = make_pod_base()
    parts["pod_roof"] = make_pod_roof()
    parts["pinion"] = place_pinion(make_pinion())
    parts["rotor"] = make_rotor()
    parts["pipe_foot"] = make_pipe_foot()
    parts["float_bracket"] = make_float_bracket().translate((0, 0, TANK_FLOOR + 90))
    parts["hub"] = make_hub()
    leg = make_leg()
    for i, a in enumerate(LEG_ANGS):
        parts[f"leg_{i + 1}"] = place_leg(leg, a)
    return parts, leg


def build():
    parts, leg = build_base()
    tier = make_tier()
    for k in range(N_TIERS):
        parts[f"tier_{k + 1}"] = place_tier(tier, k)
    parts["cap"] = make_cap()
    parts["spray_head"] = make_spray_head()
    return parts, tier, leg


def checks(p, tier):
    print("-- assembly (drop-in paths, seated contact, wiggle)")
    tank = p["tank_bottom"]
    cone = 1.5 * CLR + 0.1                     # 45 deg seat: lift clears the wiggle
    seq = [("tank_ring_1 -> bottom", p["tank_ring_1"], tank, SEAL_GAP, 0.05)]
    stack = tank + p["tank_ring_1"]
    for k in range(2, N_RINGS + 1):
        seq.append((f"tank_ring_{k} -> ring", p[f"tank_ring_{k}"], stack, SEAL_GAP, 0.05))
        stack = stack + p[f"tank_ring_{k}"]
    seq.append(("lid -> tank", p["lid"], stack, CLR, 0.05))
    seq.append(("tier_1 -> rotor", p["tier_1"], p["rotor"], CLR, cone))
    seq.append(("tier_2 -> tier_1", p["tier_2"], p["tier_1"], CLR, cone))
    seq.append(("cap -> tier_6", p["cap"], p[f"tier_{N_TIERS}"], CLR, cone))
    for name, mv, fx, wig, lift in seq:
        path, seat, w = drop_check(mv, fx, 30.0, wig, lift)
        print(f"  {name:22s} path {path:.4f} seated {seat:7.1f} wiggle {w:.4f} mm^3 "
              f"-> {ok(path < 1e-3 and seat > 1e-3 and w < 1e-3)}")

    print("-- clearances (min gap, mm)")
    rotor, lid = p["rotor"], p["lid"]
    pod = p["pod_base"] + p["pod_roof"]
    pp = pipe()
    stationary = {"lid": lid, "pod": pod, "pipe": pp, "pinion": p["pinion"]}
    turning = {"rotor": rotor, "tier_1": p["tier_1"], "cap": p["cap"]}
    # rotor/tier_1 sweep: check at several rotor angles
    worst = {}
    for ang in range(0, 60, 10):            # 6-port symmetry: 60 deg covers it
        for tn, tm in turning.items():
            mv = tm.rotate((0, 0, ang))
            for sn, sm in stationary.items():
                if (tn, sn) in (("rotor", "pinion"), ("cap", "lid"), ("cap", "pod"),
                                ("cap", "pinion")):
                    continue                # meshes by design / far apart
                g = mv.min_gap(sm, 10.0)
                worst[(tn, sn)] = min(worst.get((tn, sn), 99), g)
    for (tn, sn), g in sorted(worst.items()):
        print(f"  {tn:7s} vs {sn:7s} {g:6.2f} -> {ok(g >= 0.8)}")
    g = p["spray_head"].min_gap(p["cap"], 10.0)
    print(f"  spray_head vs cap     {g:6.2f} -> {ok(g >= 0.25)}")
    for name, a_, b_, lo in [("leg_1 vs hub", p["leg_1"], p["hub"], 0.3),
                             ("leg_1 vs tank", p["leg_1"], tank, 0.3),
                             ("pipe_foot vs tank", p["pipe_foot"], tank, 0.0),
                             ("float_brkt vs pipe", p["float_bracket"], pp, 0.1),
                             ("pod_base vs lid", p["pod_base"], lid, 0.0),
                             ("pinion vs pod_roof", p["pinion"], p["pod_roof"], 0.8)]:
        g = a_.min_gap(b_, 10.0)
        print(f"  {name:21s}{g:6.2f} -> {ok(g >= lo - 1e-6 and vol(a_ ^ b_) < 1e-3)}")
    jet = SPRAY_Z + 6.0 - TIER_Z[-1]
    bore_top = PORT_ZI + (PORT_ID / 2) * math.sqrt(2)
    print(f"  spray jets at top-tier z={jet:.1f}, port bores end z={bore_top:.1f} "
          f"-> {ok(jet > bore_top + 3)}")
    print(f"  ball face gap  {Z_RB - Z_L:.2f} mm (ball {BALL} in two {V_DEPTH} mm V-grooves)")

    print("-- gear mesh (128T ring vs 15T pinion, through one tooth pitch)")
    pin0 = make_pinion()
    worst = 0.0
    for t in np.linspace(0, 1, 9):
        dg = t * 360 / N_GEAR
        ov = vol(rotor.rotate((0, 0, dg)) ^ place_pinion(pin0, -dg * N_GEAR / N_PIN))
        worst = max(worst, ov)
    loose = vol(rotor ^ place_pinion(pin0).translate((-0.6, 0, 0)))
    print(f"  overlap {worst:.4f} mm^3 -> {ok(worst < 1e-3)}  "
          f"(pushed 0.6 mm into mesh: {loose:.1f} mm^3, proves engagement)")


def report():
    vol_l = math.pi * R_IN ** 2 * (Z_LID0 - TANK_FLOOR - 10) / 1e6
    rev_min = N_GEAR / N_PIN / 15.0                    # 28BYJ-48 ~15 rpm max
    print("-- tower")
    print(f"  tank        {2 * RC:.0f} mm OD, ~{vol_l:.1f} L to 10 mm under the lid ribs")
    print(f"  lid top     z={Z_L:.0f}  rotor top z={Z_RT:.1f}  cap seat z={CAP_Z:.1f}")
    print(f"  height      {CAP_Z + 8 + HUB_T:.0f} mm on the stand ({N_TIERS} tiers x "
          f"{N_PORT} = {N_TIERS * N_PORT} plants)")
    print(f"  pipe        1/2in PVC cut to {PIPE_LEN:.0f} mm (lift ~{SPRAY_Z / 1000 + 0.1:.2f} m head)")
    print(f"  gear        {N_GEAR}:{N_PIN} = {N_GEAR / N_PIN:.2f}:1, "
          f"{2048 * N_GEAR / N_PIN:.0f} full steps/rev, fastest ~{rev_min:.1f} min/rev")
    print(f"  balls       {int(2 * math.pi * RACE_R / (BALL + 0.4))} max on the {2 * RACE_R:.0f} mm circle")
    print(f"  O-ring      {N_RINGS} x {ORING} mm cord, ~{2 * math.pi * (TANK_R - GROOVE_D + ORING / 2):.0f} mm each")


# print orientation: (rotation, comment)
FLIP = lambda m: m.rotate((180, 0, 0))
PRINT_ORIENT = {
    "tank_bottom": (None, "floor down"),
    "tank_ring": (None, "spigot down"),
    "lid": (FLIP, "top face down"),
    "fill_plug": (FLIP, "cap down"),
    "pod_base": (None, "floor down"),
    "pod_roof": (FLIP, "top face down"),
    "pinion": (None, "flat"),
    "rotor": (FLIP, "gear face down"),
    "tier": (None, "spigot down"),
    "cap": (FLIP, "top face down"),
    "spray_head": (None, "sleeve down"),
    "pipe_foot": (None, "base down"),
    "float_bracket": (None, "flat"),
    "hub": (FLIP, "top face down"),
    "leg": (lambda m: m.rotate((90, 0, 0)), "on its side"),
}


# viewer colour, explode level, turns-with-the-stack for the base parts
BASE_META = {
    "hub": ("#2b2b2b", -2), "leg": ("#2b2b2b", -2),
    "tank_bottom": ("#3d4a3f", -1), "tank_ring_1": ("#46544a", 0),
    "tank_ring_2": ("#3d4a3f", 1), "pipe_foot": ("#4a90c2", -1),
    "float_bracket": ("#4a90c2", -0.5), "pipe": ("#9fb7c9", 2), "lid": ("#56645a", 2),
    "fill_plug": ("#56645a", 2.4), "pod_base": ("#7a6a55", 2.2),
    "pod_roof": ("#7a6a55", 2.6), "pinion": ("#c9a227", 3),
    "rotor": ("#b8862e", 3.4, True),
}


def base_meta(name):
    key = name if name in BASE_META else name.rstrip("0123456789").rstrip("_")
    return BASE_META[key]


def export_set(out_dir, singles, orient, qty, preview, meta, title, target_z=620.0):
    """Write print-oriented STLs to out_dir/stl, assembled copies to
    out_dir/preview and out_dir/preview/manifest.json for viewer.html.
    singles: {name: part}, orient: {name: (fn|None, how)}, qty: {name: n},
    preview: {name: part (assembled) or path of an existing STL relative to
    this folder}, meta: {name: (colour, explode level[, turns])}."""
    import json
    import trimesh
    print("-- STL export (print orientation)")
    os.makedirs(os.path.join(out_dir, "stl"), exist_ok=True)
    os.makedirs(os.path.join(out_dir, "preview"), exist_ok=True)
    allok = True
    for name, m in singles.items():
        rot, how = orient[name]
        m = rot(m) if rot else m
        tm = to_trimesh(m)
        tm.apply_translation(-np.array([tm.bounds[0][0] + tm.extents[0] / 2,
                                        tm.bounds[0][1] + tm.extents[1] / 2, tm.bounds[0][2]]))
        tm.export(os.path.join(out_dir, "stl", f"{name}.stl"))
        side, ang = bed_fit(tm)
        fits = side <= BED - 2 * BED_MARGIN
        allok &= fits and tm.is_watertight
        print(f"  {name:14s} x{qty.get(name, 1)}  {how:14s} size {np.round(tm.extents, 1)} "
              f"footprint {side:5.1f} @ {ang:2d} deg  vol {tm.volume / 1000:6.0f} cm3  "
              f"watertight={tm.is_watertight} bed {ok(fits)}")
    entries = []
    rel = os.path.relpath(out_dir, OUT)
    for name, m in preview.items():
        if isinstance(m, str):
            f = m
        else:
            to_trimesh(m).export(os.path.join(out_dir, "preview", f"{name}.stl"))
            f = os.path.normpath(os.path.join(rel, "preview", f"{name}.stl"))
        c = meta[name]
        entries.append({"name": name, "file": f.replace(os.sep, "/"), "color": c[0],
                        "lvl": c[1], "spin": bool(c[2]) if len(c) > 2 else False})
    with open(os.path.join(out_dir, "preview", "manifest.json"), "w") as fh:
        json.dump({"title": title, "target_z": target_z, "parts": entries}, fh, indent=1)
    print(f"  all parts fit + watertight -> {ok(allok)}")
    return allok


BASE_SINGLES = ("tank_bottom", "tank_ring", "lid", "fill_plug", "pod_base", "pod_roof",
                "pinion", "rotor", "pipe_foot", "float_bracket", "hub", "leg")


def export(parts, tier, leg):
    singles = {n: parts[n] for n in BASE_SINGLES if n in parts}
    singles["tank_ring"] = parts["tank_ring_1"]      # all rings are identical
    singles["leg"] = leg
    singles.update(tier=tier, cap=parts["cap"], spray_head=parts["spray_head"])
    qty = {"tank_ring": N_RINGS, "tier": N_TIERS, "leg": len(LEG_ANGS)}
    preview = dict(parts, pipe=pipe())
    meta = {n: base_meta(n) for n in preview if not n.startswith(("tier", "cap", "spray"))}
    for k in range(N_TIERS):
        meta[f"tier_{k + 1}"] = ("#e8e2d0" if k % 2 == 0 else "#d9d2bd", 4 + k, True)
    meta["spray_head"] = ("#4a90c2", 9.6)
    meta["cap"] = ("#cfc6aa", 10.4, True)
    export_set(OUT, singles, PRINT_ORIENT, qty, preview, meta,
               f"Classic: {N_TIERS} tiers x {N_PORT} ports")


def main():
    parts, tier, leg = build()
    report()
    checks(parts, tier)
    export(parts, tier, leg)


if __name__ == "__main__":
    main()
