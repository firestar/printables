"""Hyperboloid Lattice: 12 straight, tilted NFT grow tubes between a bottom
ring and a top crown, forming a ruled hyperboloid (cooling-tower hourglass).

Only the turning stack changes; the tank, lid, drive, rotor and stand are the
classic base (grow_tower.build_base).

  rotor socket -- BOWL: classic spigot, 45 deg funnel, rim with 12 shoe seats
                  12 x FOOT_SHOE: tilted socket + funnel + duct + drip spout,
                       screwed to the bowl rim (together they are the bottom ring)
  lattice ------- 12 tubes x 3 identical SEGMENTs (one 2" net-pot port each),
                  O-ring socket/spigot joints with a bayonet lug that also sets
                  the port roll; the upper segment always sits INSIDE the lower
                  socket, so water runs over every joint downhill
  top ----------- 12 x HEAD_SHOE: spigot into the top segment, closed cap, inlet
                       duct from a cup under the crown pan
                  CROWN_PAN: flat distributor pan, 12 x 8 mm outlets (one per
                       tube), inner lip around the fixed spray head
                  CROWN_LID: rain roof + bushing on the spray-head stub
  inside -------- 6 x 6 mm steel ROD, the opposite ruling (counter-twisted inner
                  hyperboloid) from bosses on the bowl rim to ROD_BRACKETs
                  under the pan.  One ruling of straight bars alone is a
                  mechanism (its lines span only 3 of the 6 rigid-body
                  motions); the counter-rods make the cage rigid, exactly as
                  in a Shukhov / cooling-tower lattice
  fixed --------- PIPE (1/2" PVC) + classic SPRAY_HEAD on top: the jets hit the
                  pan wall, so water crosses fixed -> turning without a seal

Water: pump -> pipe -> jets -> pan -> 12 outlets -> head-shoe ducts -> film on
the floor (low side) of each tilted tube -> foot-shoe duct -> drip into the
bowl -> rotor bore -> lid drain.

Run: env PYTHONPATH=/home/infra/printables/.pydeps python3 \
       grow_tower/cad/concepts/hyperboloid_lattice/hyperboloid_lattice.py
"""
import math
import os
import sys

import numpy as np
import manifold3d as m3d

HERE = os.path.dirname(os.path.abspath(__file__))
CAD = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, CAD)
import grow_tower as gt                                    # noqa: E402
from grow_tower import revolve, tube, cyl, box, vol, union, ok   # noqa: E402

NAME = "hyperboloid_lattice"
ST = 72               # circle segments for the many tube parts

# ---- lattice ---------------------------------------------------------------
N_TUBE = 12
RW = 120.0            # waist radius of the tube axes
BETA = 20.0           # tube tilt from vertical
S_HALF = 240.0        # tube axis length waist -> end joint (each side)
N_SEG = 3
SEG_L = 2 * S_HALF / N_SEG          # joint-to-joint segment length (160)

# ---- tube + joint (local z along the tube axis, 0 = spigot tip) -----------
T_RI, T_RO = 20.0, 22.4             # 40 mm bore, 2.4 wall
J_D = 20.0                          # socket depth = spigot length
SP_RO = 24.4                        # spigot outer (thick: carries the gland)
SK_RI = SP_RO + gt.SEAL_GAP         # socket bore
SK_RO = SK_RI + 2.4
GROOVE = (5.0, 8.8)                 # O-ring gland on the spigot (3 mm cord)
LUG_Z = (13.0, 16.0)                # bayonet lug on the spigot
LUG_W = 4.0
LUG_R = 26.6
POCKET = (12.5, 16.5)               # pocket in the socket wall (above ledge)
SLOT_W = 5.4
TWIST = -15.0                       # bayonet twist after insertion (signed: the
                                    # port swings in from the floor side, away
                                    # from the neighbour)
LUG_ANG = 180.0                     # lug angle in the segment frame
D_ROLL = 10.0                       # roll step segment -> segment above
ROLL0 = -25.0                       # bottom segment port roll (- = towards ceiling)
ROLLS = [ROLL0 + k * D_ROLL for k in range(N_SEG)]
SLOT_ANG = LUG_ANG + D_ROLL - TWIST  # axial slot angle in the lower frame

# ---- port (2" net pot) -----------------------------------------------------
ALPHA = 45.0          # port axis from the tube axis, leaning up-tube
Z_P = 66.0            # port axis meets the tube axis here (segment local)
L_MOUTH = 62.0        # mouth centre distance from that point
PORT_RI = gt.PORT_ID / 2
PORT_RO = PORT_RI + gt.PORT_WALL
POT_L, POT_R0, POT_R1 = 50.0, 20.0, 25.0     # net pot: length, tip r, top r
BULB_DN, BULB_UP = 18.0, 72.0                # hull reach along the tube

# ---- bottom: bowl + foot shoes ---------------------------------------------
ZS = gt.Z_RT - gt.SEAT_DROP          # spigot seat in the rotor socket
R_WI, R_WO, R_FL = 112.0, 116.0, 122.0
Z_RIM = 567.0
R_O = 100.0                          # shoe drip spout radius
DUCT_RI, DUCT_RO = 8.0, 10.4
PAD_T = 5.0
FUNNEL = 36.0                        # socket ledge -> funnel point along -u
DUCT_SLOPE = 1.1                     # drop / run of the shoe ducts

# ---- top: head shoes, pan, lid ---------------------------------------------
HB = J_D + 16.0                      # head body top (local)
Q_L = J_D + 10.0                     # inlet duct enters the head here (local)
H_RI, H_RO = 5.0, 7.4                # head duct
R_C = 102.0                          # pan outlet / head cup radius
CUP_H = 14.0
HEAD_SLOPE = 1.05
OUT_R = 4.0                          # pan outlet hole (8 mm)
CUP_R = 8.0
PAN_FLOOR = 3.0
R_LIP = 16.0                         # pan lip inner radius (sleeve r15 + 1)
R_PWI, R_PWO = 108.0, 111.0          # pan wall
SCREW = 2.2                          # M4 clearance radius
PILOT = 1.7                          # M4 self-tap pilot radius

# ---- inner counter-rods (opposite ruling) -----------------------------------
N_ROD = 6
ROD_R = 3.0                          # 6 mm steel rod (or GRP / aluminium)
R_RA = 117.0                         # rod anchor radius (bowl rim / under the pan)
ROD_SOCK = 21.0                      # blind socket depth in each anchor
ROD_END = 4.0                        # socket bottom above the anchor face

# ---- derived geometry ------------------------------------------------------
B_ = math.radians(BETA)
U = np.array([0.0, math.sin(B_), math.cos(B_)])     # tube 0 axis (upwards)
E1 = np.array([1.0, 0.0, 0.0])                       # outward at the waist
FL = np.cross(U, E1)                                 # floor side (points down)


def xy_of(s):
    return np.array([RW, s * U[1]])


def az(p):
    return math.degrees(math.atan2(p[1], p[0]))


_pd = xy_of(-S_HALF - FUNNEL)
Z_OT = Z_RIM + 12.0                                  # top of the drip spout
Z_A = Z_OT + DUCT_SLOPE * (np.hypot(*_pd) - R_O) + FUNNEL * U[2]
ZW = Z_A + S_HALF * U[2]                             # waist height


def axis_pt(s):
    return np.array([RW, 0.0, ZW]) + s * U


_q = axis_pt(S_HALF + Q_L)
Z_PB = _q[2] + 12.0 + HEAD_SLOPE * (np.hypot(_q[0], _q[1]) - R_C)  # pan underside
SPRAY_Z = Z_PB + PAN_FLOOR + 20.0                    # floor 20 below the pipe top
Z_PT = SPRAY_Z + 36.0                                # pan wall top = lid roof underside
STUB_TOP = SPRAY_Z + 34.0
ROOF_T = 3.0
PIPE_LEN = SPRAY_Z - gt.PIPE_Z0


def frame(roll, s):
    """3x4 matrix: segment-local (x = port side, z = tube axis) -> tube-0 world."""
    r = math.radians(roll)
    ex = math.cos(r) * E1 + math.sin(r) * FL
    ey = np.cross(U, ex)
    return np.column_stack([ex, ey, U, axis_pt(s)])


def inv_frame(roll, s):
    m = frame(roll, s)
    rt = m[:, :3].T
    return np.column_stack([rt, -rt @ m[:, 3]])


def place(m, roll, s, i=0):
    return m.transform(frame(roll, s)).rotate((0, 0, 360.0 / N_TUBE * i))


def spin(m, i):
    return m.rotate((0, 0, 360.0 / N_TUBE * i))


def ball(p, r, seg=ST):
    return m3d.Manifold.sphere(r, seg).translate(tuple(float(v) for v in p))


def capsule(p, q, r, seg=ST):
    return m3d.Manifold.batch_hull([ball(p, r, seg), ball(q, r, seg)])


def disc_on(p_dir, l0, l1, r, origin=(0, 0, 0), seg=ST):
    """Cylinder radius r along unit vector p_dir from l0 to l1 (from origin)."""
    c = m3d.Manifold.cylinder(l1 - l0, r, r, seg).translate((0, 0, l0))
    d = np.asarray(p_dir, float)
    ay = math.degrees(math.atan2(math.hypot(d[0], d[1]), d[2]))
    az_ = math.degrees(math.atan2(d[1], d[0]))
    return c.rotate((0, ay, 0)).rotate((0, 0, az_)).translate(tuple(origin))


def sector(r0, r1, a0, a1, z0, z1):
    n = max(4, int(abs(a1 - a0) / 2) + 2)
    pts = [(r0 * math.cos(math.radians(a)), r0 * math.sin(math.radians(a)))
           for a in np.linspace(a0, a1, n)]
    pts += [(r1 * math.cos(math.radians(a)), r1 * math.sin(math.radians(a)))
            for a in np.linspace(a1, a0, n)]
    return m3d.CrossSection([pts[::-1]]).extrude(z1 - z0).translate((0, 0, z0))


def radial_box(ang, r0, r1, t0, t1, z0, z1):
    return box(r0, r1, t0, t1, z0, z1).rotate((0, 0, ang))


# ---- joint pieces (local) ------------------------------------------------------
def spigot_cuts():
    """O-ring gland (45 deg upper flank, prints spigot-down)."""
    g = revolve([(SP_RO - 2.4, GROOVE[0]), (SP_RO + 1, GROOVE[0]),
                 (SP_RO + 1, GROOVE[1] + 3.4), (SP_RO - 2.4, GROOVE[1])], ST)
    return g


def lug():
    pts = [(SP_RO - 0.3, LUG_Z[0]), (LUG_R, LUG_Z[0] + (LUG_R - SP_RO + 0.3)),
           (LUG_R, LUG_Z[1]), (SP_RO - 0.3, LUG_Z[1])]
    l = m3d.CrossSection([pts]).extrude(LUG_W).translate((0, 0, -LUG_W / 2))
    return l.rotate((90, 0, 0)).rotate((0, 0, LUG_ANG))


def socket_cuts(z0):
    """Bayonet slot + pocket in a socket whose ledge is at local z0."""
    half = math.degrees(SLOT_W / 2 / SK_RI)
    slot = sector(SK_RI - 0.6, SK_RO + 1, SLOT_ANG - half, SLOT_ANG + half,
                  z0 + POCKET[0], z0 + J_D + 1)
    a0, a1 = sorted((SLOT_ANG, SLOT_ANG + TWIST))
    pocket = sector(SK_RI - 0.6, SK_RO + 1, a0 - half, a1 + half,
                    z0 + POCKET[0], z0 + POCKET[1])
    return slot + pocket


def socket_solid(z0):
    """Socket ring z0 .. z0 + J_D with a 45 deg flare below (outer only)."""
    return revolve([(T_RI + 0.01, z0 - (SK_RO - T_RO)), (T_RO, z0 - (SK_RO - T_RO)),
                    (SK_RO, z0), (SK_RO, z0 + J_D - gt.EF), (SK_RO - gt.EF, z0 + J_D),
                    (SK_RI + 0.8, z0 + J_D), (SK_RI, z0 + J_D - 0.8), (SK_RI, z0),
                    (T_RI + 0.01, z0)], ST)


# ---- tube segment ---------------------------------------------------------------
P_DIR = np.array([math.sin(math.radians(ALPHA)), 0.0, math.cos(math.radians(ALPHA))])


def port_point(l):
    return np.array([0.0, 0.0, Z_P]) + l * P_DIR


def port_hulls():
    """Outer / inner hull of the port bulb (outer = inner grown by >= the wall)."""
    w = gt.PORT_WALL
    o = m3d.Manifold.batch_hull([
        cyl(BULB_DN + BULB_UP + 2 * w, T_RO, z=Z_P - BULB_DN - w, seg=ST),
        disc_on(P_DIR, L_MOUTH - 12 - w, L_MOUTH + w, PORT_RO, (0, 0, Z_P))])
    o = o - disc_on(P_DIR, L_MOUTH, L_MOUTH + 40, 60, (0, 0, Z_P))
    i = m3d.Manifold.batch_hull([
        cyl(BULB_DN + BULB_UP, T_RI, z=Z_P - BULB_DN, seg=ST),
        disc_on(P_DIR, L_MOUTH - 12, L_MOUTH + 1, PORT_RI, (0, 0, Z_P))])
    return o, i


def pot():
    """2\" net pot hanging from the mouth (frustum), segment local."""
    c = m3d.Manifold.cylinder(POT_L, POT_R0, POT_R1, ST).translate((0, 0, L_MOUTH - POT_L))
    ay = ALPHA
    return c.rotate((0, ay, 0)).translate((0, 0, Z_P))


def make_segment():
    top = SEG_L
    body = revolve([(T_RI, 0), (SP_RO - gt.EF, 0), (SP_RO, gt.EF), (SP_RO, J_D),
                    (T_RO, J_D + 2.0), (T_RO, top - (SK_RO - T_RO)), (SK_RO, top),
                    (SK_RO, top + J_D - gt.EF), (SK_RO - gt.EF, top + J_D),
                    (SK_RI + 0.8, top + J_D), (SK_RI, top + J_D - 0.8), (SK_RI, top),
                    (T_RI, top)], ST)
    o, i = port_hulls()
    s = body + o + lug()
    s = s - i - cyl(top + 2, T_RI, z=-1, seg=ST) - spigot_cuts() - socket_cuts(top)
    return s


# ---- head shoe (built in tube-0 world) -----------------------------------------
def head_points():
    roll = ROLLS[-1] + D_ROLL
    q = axis_pt(S_HALF + Q_L)
    a = az(q)
    i_pt = np.array([R_C * math.cos(math.radians(a)), R_C * math.sin(math.radians(a)),
                     Z_PB - 12.0])
    return roll, q, i_pt, a


def make_head_shoe():
    roll, q, i_pt, a = head_points()
    fr = lambda m: m.transform(frame(roll, S_HALF))
    spig = revolve([(T_RI, 0), (SP_RO - gt.EF, 0), (SP_RO, gt.EF), (SP_RO, J_D),
                    (T_RO, J_D + 2.0), (T_RO, HB + 0.01), (T_RI, HB + 0.01)], ST)
    spig = spig + lug() - spigot_cuts()
    body = fr(spig)
    # cap: hull of the tilted rim and a point straight above (world), 45 deg+ all round
    c_top = axis_pt(S_HALF + HB)
    cap_o = m3d.Manifold.batch_hull([fr(cyl(0.01, T_RO, z=HB, seg=ST)),
                                     ball(c_top + [0, 0, 29.0], 1.0, 24)])
    cap_i = m3d.Manifold.batch_hull([fr(cyl(0.01, T_RI, z=HB - 0.01, seg=ST)),
                                     ball(c_top + [0, 0, 25.6 - 1.0], 1.0, 24)])
    blk = radial_box(a, R_C - 14, R_FL, -13, 13, Z_PB - CUP_H, Z_PB)
    d2 = i_pt + 0.35 * (q - i_pt)
    house = m3d.Manifold.batch_hull([blk, ball(d2, H_RO)])
    duct = capsule(i_pt, q, H_RO)
    h = body + cap_o + house + duct
    cup = m3d.Manifold.batch_hull([cyl(1.0, CUP_R, z=Z_PB, x=R_C).rotate((0, 0, a)),
                                   ball(i_pt, H_RI)])
    h = h - cap_i - fr(cyl(HB + 1, T_RI, z=-1, seg=ST)) - cup - capsule(i_pt, q, H_RI)
    h = h - cyl(500, 1000, z=Z_PB, seg=32)                  # flat top (pan seat)
    for t in (-8.0, 8.0):                                   # M4 pilots under the pan
        x, y = R_FL - 5.0, t
        p = cyl(12, PILOT, z=Z_PB - 11.5, x=x, y=y, seg=24).rotate((0, 0, a))
        h = h - p
    return h


# ---- foot shoe (tube-0 world) ------------------------------------------------------
def foot_points():
    roll = ROLLS[0] - D_ROLL
    pd = axis_pt(-S_HALF - FUNNEL)
    a = az(pd)
    o_top = np.array([R_O * math.cos(math.radians(a)), R_O * math.sin(math.radians(a)), Z_OT])
    return roll, pd, o_top, a


def make_foot_shoe():
    roll, pd, o_top, a = foot_points()
    fr = lambda m: m.transform(frame(roll, -S_HALF))
    sock = fr(socket_solid(0.0))
    fo = m3d.Manifold.batch_hull([fr(cyl(0.01, SK_RO, z=0.0, seg=ST)), ball(pd, DUCT_RO)])
    fi = m3d.Manifold.batch_hull([fr(cyl(0.02, T_RI, z=0.0, seg=ST)), ball(pd, DUCT_RI)])
    duct = capsule(pd, o_top, DUCT_RO)
    ox, oy = o_top[0], o_top[1]
    shaft = cyl(Z_OT - Z_RIM, DUCT_RO, z=Z_RIM, x=ox, y=oy, seg=ST)
    pad = radial_box(a, R_O - 12, R_FL, -14, 14, Z_RIM, Z_RIM + PAD_T)
    web = m3d.Manifold.batch_hull([radial_box(a, R_O, R_FL - 2, -2, 2, Z_RIM, Z_RIM + PAD_T),
                                   ball(pd, 2.0, 16), ball(o_top, 2.0, 16)])
    f = sock + fo + duct + shaft + pad + web
    f = f - fi - capsule(pd, o_top, DUCT_RI) - fr(cyl(J_D + 1, SK_RI, z=0.0, seg=ST))
    f = f - cyl(Z_OT - Z_RIM + 2, DUCT_RI, z=Z_RIM - 1, x=ox, y=oy, seg=ST)
    f = f - fr(socket_cuts(0.0))
    drip = tube(DUCT_RI + 1.0, DUCT_RI + 2.2, Z_RIM - 1, Z_RIM + 1.2, 48).translate((ox, oy, 0))
    f = f - drip
    for t in (-9.0, 9.0):
        f = f - cyl(PAD_T + 2, SCREW, z=Z_RIM - 1, x=R_FL - 4, y=t, seg=24).rotate((0, 0, a))
    return f


# ---- bowl ------------------------------------------------------------------------
def make_bowl():
    b = revolve([(gt.R_SI, ZS - gt.SPIG_L), (gt.R_SO - gt.EF, ZS - gt.SPIG_L),
                 (gt.R_SO, ZS - gt.SPIG_L + gt.EF), (gt.R_SO, ZS),
                 (R_WO, ZS + R_WO - gt.R_SO), (R_WO, Z_RIM - 10.0), (R_FL, Z_RIM - 4.0),
                 (R_FL, Z_RIM), (R_WI, Z_RIM), (R_WI, ZS + R_WI - gt.R_SI), (gt.R_SI, ZS)])
    _, _, _, a = foot_points()
    for i in range(N_TUBE):
        for t in (-9.0, 9.0):
            p = cyl(9, PILOT, z=Z_RIM - 8.5, x=R_FL - 4, y=t, seg=24)
            b = b - p.rotate((0, 0, a + 360.0 / N_TUBE * i))
    lines, _ = rod_lines()
    for pb, _, d in lines:
        b = b + rod_anchor(pb, d)
    return b


# ---- crown -----------------------------------------------------------------------
def make_pan():
    zf = Z_PB
    p = tube(R_LIP, R_FL, zf, zf + PAN_FLOOR)
    p = p + tube(R_LIP, R_LIP + 2.4, zf, SPRAY_Z + 3.0, 96)          # inner lip
    p = p + tube(R_PWI, R_PWO, zf, Z_PT)                            # wall
    _, _, _, a = head_points()
    for i in range(N_TUBE):
        ai = a + 360.0 / N_TUBE * i
        h = cyl(PAN_FLOOR + 2, OUT_R + gt.HOLE_COMP / 2, z=zf - 1, x=R_C, seg=32)
        h = h + tube(OUT_R + 1.0, OUT_R + 2.2, zf - 1, zf + 1.0, 32).translate((R_C, 0, 0))
        for t in (-8.0, 8.0):
            h = h + cyl(PAN_FLOOR + 2, SCREW, z=zf - 1, x=R_FL - 5, y=t, seg=24)
        p = p - h.rotate((0, 0, ai))
    lines, _ = rod_lines()
    for _, pt, _ in lines:
        for t in (-8.0, 8.0):
            p = p - cyl(PAN_FLOOR + 2, SCREW, z=zf - 1, x=R_RA, y=t, seg=24).rotate((0, 0, az(pt)))
    return p


def make_lid():
    hub_r = (gt.STUB_D + 0.6) / 2
    r_out = R_PWO + gt.CLR + 2.4
    l = revolve([(0, Z_PT), (r_out, Z_PT - 10.0), (r_out, Z_PT + ROOF_T - 1.0),
                 (r_out - 1.0, Z_PT + ROOF_T), (0, Z_PT + ROOF_T)])
    l = l - tube(0, R_PWO + gt.CLR, Z_PT - 11, Z_PT)                # skirt over the wall
    hub_bot = STUB_TOP - gt.HUB_ENGAGE
    l = l + tube(hub_r, hub_r + 4.5, hub_bot, Z_PT + 0.01, 96)
    l = l - cyl(STUB_TOP + 1.5 - hub_bot + 1, hub_r, z=hub_bot - 1, seg=96)
    l = l - revolve([(hub_r - 0.01, hub_bot - 1), (hub_r + 1.5, hub_bot - 1),
                     (hub_r - 0.01, hub_bot + 0.5)], 96)
    return l


def make_spray_head():
    return gt.make_spray_head().translate((0, 0, SPRAY_Z - gt.SPRAY_Z))


def pipe():
    return tube(gt.PIPE_ID / 2, gt.PIPE_OD / 2, gt.PIPE_Z0, SPRAY_Z, 64)

# ---- counter-rods -------------------------------------------------------------------
def rod_lines():
    """[(bottom anchor point, top anchor point, unit dir up)] and the rod twist.
    The rods twist the other way round; the twist is chosen so both ends land
    halfway between two shoes."""
    a_o = foot_points()[3]
    a_q = head_points()[3]
    phi = (a_o - a_q) % 30.0 + 90.0
    out = []
    for j in range(N_ROD):
        ab = a_o + 15.0 + 360.0 / N_ROD * j
        at = ab - phi
        pb = np.array([R_RA * math.cos(math.radians(ab)), R_RA * math.sin(math.radians(ab)), Z_RIM])
        pt = np.array([R_RA * math.cos(math.radians(at)), R_RA * math.sin(math.radians(at)), Z_PB])
        out.append((pb, pt, (pt - pb) / np.linalg.norm(pt - pb)))
    return out, phi


def rod_anchor(p, e):
    """Tapered boss on an anchor face through p (horizontal), rod socket along e
    (away from the face), M3 cross-pin pilot."""
    up = e[2] > 0
    z0, z1 = (Z_RIM - 0.01, Z_RIM + 3.0) if up else (Z_PB - 3.0, Z_PB)
    pad = radial_box(az(p), R_RA - 5, R_RA + 5, -11, 11, z0, z1)
    tip = ROD_END + ROD_SOCK + 3.0
    b = m3d.Manifold.batch_hull([pad, disc_on(e, tip - 0.5, tip, 6.5, tuple(p))])
    b = b - disc_on(e, ROD_END, tip + 1, ROD_R + 0.2, tuple(p))
    n = np.cross(e, [0, 0, 1.0])
    n /= np.linalg.norm(n)
    b = b - disc_on(n, -12, 12, 1.25, tuple(p + 16.0 * e))
    return b


def make_rod_bracket():
    """Top rod anchor, screwed up under the pan flange (rod 0)."""
    lines, _ = rod_lines()
    _, pt, d = lines[0]
    b = rod_anchor(pt, -d)
    for t in (-8.0, 8.0):
        b = b - cyl(12, PILOT, z=Z_PB - 11.5, x=R_RA, y=t, seg=24).rotate((0, 0, az(pt)))
    return b


def rods():
    lines, _ = rod_lines()
    return union([disc_on(d, ROD_END, np.linalg.norm(pt - pb) - ROD_END, ROD_R, tuple(pb), 32)
                  for pb, pt, d in lines])



# ---- build -------------------------------------------------------------------------
def build():
    parts, leg = gt.build_base()
    seg = make_segment()
    foot, head = make_foot_shoe(), make_head_shoe()
    pots = []
    for k in range(N_SEG):
        s0 = -S_HALF + k * SEG_L
        parts[f"segs_{k + 1}"] = union([place(seg, ROLLS[k], s0, i) for i in range(N_TUBE)])
        pots += [place(pot(), ROLLS[k], s0, i) for i in range(N_TUBE)]
    parts["bowl"] = make_bowl()
    parts["foot_shoes"] = union([spin(foot, i) for i in range(N_TUBE)])
    parts["head_shoes"] = union([spin(head, i) for i in range(N_TUBE)])
    parts["crown_pan"] = make_pan()
    parts["crown_lid"] = make_lid()
    parts["spray_head"] = make_spray_head()
    parts["net_pots"] = union(pots)
    brk = make_rod_bracket()
    parts["rod_brackets"] = union([brk.rotate((0, 0, 360.0 / N_ROD * j)) for j in range(N_ROD)])
    parts["rods"] = rods()
    return parts, leg, dict(segment=seg, foot_shoe=foot, head_shoe=head, rod_bracket=brk)


def tube0(single):
    """Tube 0 fully assembled (foot shoe .. head shoe), plus its pots."""
    seg = single["segment"]
    t = [single["foot_shoe"], single["head_shoe"]]
    t += [place(seg, ROLLS[k], -S_HALF + k * SEG_L) for k in range(N_SEG)]
    t += [place(pot(), ROLLS[k], -S_HALF + k * SEG_L) for k in range(N_SEG)]
    return union(t)


# ---- checks ------------------------------------------------------------------------
def axial_check(mv_ins, mv_fin, fixed, travel=30.0, step=1.0, wig=gt.SEAL_GAP):
    """Drop along the tube axis at the insertion roll, then the bayonet twist,
    then seated / wiggle / locked at the final roll."""
    u = U
    worst = 0.0
    for d in np.arange(travel, step / 2, -step):
        worst = max(worst, vol(mv_ins.translate(tuple(d * u)) ^ fixed))
    seat = vol(mv_fin.translate(tuple(-0.3 * u)) ^ fixed)
    wiggle = 0.0
    e2 = np.cross(U, E1)
    for a in range(0, 360, 45):
        dv = 0.9 * wig * (math.cos(math.radians(a)) * E1 + math.sin(math.radians(a)) * e2)
        wiggle = max(wiggle, vol(mv_fin.translate(tuple(dv + 0.05 * u)) ^ fixed))
    lock = vol(mv_fin.translate(tuple(1.0 * u)) ^ fixed)
    return worst, seat, wiggle, lock


def checks(p, single):
    allok = True

    def rep(flag):
        nonlocal allok
        allok &= bool(flag)
        return ok(flag)

    print("-- 1. stack drop-in (path, seated, wiggle[, twist, locked]) mm^3")
    cone = 1.5 * gt.CLR + 0.1
    bowl, foot, head, seg = p["bowl"], single["foot_shoe"], single["head_shoe"], single["segment"]
    path, seat, w = gt.drop_check(bowl, p["rotor"], 30.0, gt.CLR, cone)
    print(f"  bowl -> rotor            path {path:.4f} seated {seat:7.1f} wiggle {w:.4f} "
          f"-> {rep(path < 1e-3 and seat > 1e-3 and w < 1e-3)}")
    path, seat, w = gt.drop_check(foot, bowl + spin(foot, 1) + spin(foot, -1), 20.0, gt.CLR, 0.05)
    print(f"  foot_shoe -> bowl rim    path {path:.4f} seated {seat:7.1f} wiggle {w:.4f} "
          f"-> {rep(path < 1e-3 and seat > 1e-3 and w < 1e-3)}")
    t0 = tube0(single)
    # assembly goes layer by layer: all 12 bottom segments, then the middle ones ...
    nb = lambda m: spin(m, 1) + spin(m, -1)
    layer = foot
    lower = foot
    for k in range(N_SEG):
        s0 = -S_HALF + k * SEG_L
        fin = place(seg, ROLLS[k], s0)
        ins = place(seg, ROLLS[k] - TWIST, s0)
        layer = layer + fin
        path, seat, w, lock = axial_check(ins, fin, lower + nb(layer), travel=J_D + 2)
        tw = max(vol(place(seg, ROLLS[k] - TWIST + d, s0) ^ lower)
                 for d in np.linspace(0, TWIST, 6))
        name = "foot shoe" if k == 0 else f"segment {k}"
        print(f"  segment {k + 1} -> {name:10s} path {path:.4f} seated {seat:6.1f} wiggle {w:.4f} "
              f"twist {tw:.4f} locked {lock:5.1f} "
              f"-> {rep(path < 1e-3 and seat > 1e-3 and w < 1e-3 and tw < 1e-3 and lock > 1e-3)}")
        lower = fin
    # head insertion: same shape rolled back by TWIST about the tube axis
    rot = lambda m, d: (m.transform(inv_frame(0.0, S_HALF)).rotate((0, 0, d))
                        .transform(frame(0.0, S_HALF)))
    ins = rot(head, -TWIST)
    path, seat, w, lock = axial_check(ins, head, lower + nb(layer + head), travel=J_D + 2)
    tw = max(vol(rot(head, -TWIST + d) ^ lower) for d in np.linspace(0, TWIST, 6))
    print(f"  head_shoe -> segment 3   path {path:.4f} seated {seat:6.1f} wiggle {w:.4f} "
          f"twist {tw:.4f} locked {lock:5.1f} "
          f"-> {rep(path < 1e-3 and seat > 1e-3 and w < 1e-3 and tw < 1e-3 and lock > 1e-3)}")
    # rod brackets slide down the rod tops first, then the pan drops on everything
    lines, _ = rod_lines()
    _, pt, d = lines[0]
    brk = single["rod_bracket"]
    worst = max(vol(brk.translate(tuple(s * d)) ^ p["rods"]) for s in np.arange(20, 0.4, -1))
    print(f"  rod_bracket -> rod top   path {worst:.4f} -> {rep(worst < 1e-3)}")
    path, seat, w = gt.drop_check(p["crown_pan"], p["head_shoes"] + p["rod_brackets"], 20.0,
                                  gt.CLR, 0.05)
    print(f"  crown_pan -> head shoes  path {path:.4f} seated {seat:7.1f} wiggle {w:.4f} "
          f"-> {rep(path < 1e-3 and seat > 1e-3 and w < 1e-3)}")
    path, seat, w = gt.drop_check(p["crown_lid"], p["crown_pan"], 20.0, gt.CLR, 0.05)
    print(f"  crown_lid -> pan         path {path:.4f} seated {seat:7.1f} wiggle {w:.4f} "
          f"-> {rep(path < 1e-3 and seat > 1e-3 and w < 1e-3)}")

    print("-- 2. turning vs fixed, min gap over one 60 deg period (mm)")
    pp = pipe()
    pod = p["pod_base"] + p["pod_roof"]
    fixed = {"lid": p["lid"], "pod": pod, "pinion": p["pinion"], "pipe": pp,
             "spray_head": p["spray_head"]}
    turning = {"bowl": bowl, "foot_shoes": p["foot_shoes"], "segs_1": p["segs_1"],
               "rods": p["rods"], "crown_pan": p["crown_pan"], "crown_lid": p["crown_lid"]}
    worst = {}
    for ang in range(0, 60, 5):
        for tn, tm in turning.items():
            mv = tm.rotate((0, 0, ang))
            for sn, sm in fixed.items():
                g = mv.min_gap(sm, 10.0)
                worst[(tn, sn)] = min(worst.get((tn, sn), 99), g)
    for (tn, sn), g in sorted(worst.items()):
        lim = 0.25 if (tn, sn) == ("crown_lid", "spray_head") else 0.8
        if g < 10.0 or lim == 0.25:
            print(f"  {tn:10s} vs {sn:10s} {g:6.2f} (>= {lim}) -> {rep(g >= lim)}")
    print("  (all other pairs > 10 mm apart; lid bushing is the bearing fit)")
    print("-- 2b. turning parts among themselves")
    g = t0.min_gap(spin(t0, 1), 20.0)
    print(f"  tube vs neighbour tube (with pots)  {g:6.2f} (>= 3) -> {rep(g >= 3.0)}")
    lattice = p["segs_1"] + p["segs_2"] + p["segs_3"] + p["net_pots"] + p["foot_shoes"] \
        + p["head_shoes"] + p["crown_pan"]
    g = p["rods"].min_gap(lattice, 20.0)
    print(f"  counter-rods vs tubes / pots / shoes / pan {g:6.2f} (>= 3) -> {rep(g >= 3.0)}")
    g = vol(p["rods"] ^ (bowl + p["rod_brackets"]))
    g2 = p["rods"].min_gap(bowl + p["rod_brackets"], 5.0)
    print(f"  rods in their sockets: overlap {g:.4f} mm^3, fit gap {g2:.2f} -> {rep(g < 1e-3)}")
    g = vol(p["foot_shoes"] ^ p["bowl"]) + vol(p["head_shoes"] ^ p["crown_pan"]) \
        + vol(p["rod_brackets"] ^ (p["crown_pan"] + p["head_shoes"]))
    print(f"  shoes / brackets vs bowl / pan overlap {g:.4f} mm^3 -> {rep(g < 1e-3)}")

    print("-- 3. water path")
    s_pot = []
    for k in range(N_SEG):
        s0 = -S_HALF + k * SEG_L
        fr = frame(ROLLS[k], s0)
        tip = fr[:, :3] @ port_point(L_MOUTH - POT_L) + fr[:, 3]
        o0 = tip - axis_pt(0.0)
        o0 = o0 - (o0 @ U) * U
        # roots hang straight down; inside the tube they drift towards the floor
        sb = math.sin(B_)
        a_ = sb * sb
        b_ = 2 * sb * (o0 @ FL)
        c_ = o0 @ o0 - T_RI ** 2
        t = (-b_ + math.sqrt(b_ * b_ - 4 * a_ * c_)) / (2 * a_)
        hit = o0 + t * sb * FL
        ang = math.degrees(math.acos(np.clip(hit @ FL / T_RI, -1, 1)))
        inside = math.sqrt(o0 @ o0) < T_RI
        s_pot.append((k, t, ang))
        pot_out = vol(pot() - (port_hulls()[1] + cyl(SEG_L, T_RI, seg=ST)))
        print(f"  port {k + 1} (roll {ROLLS[k]:+.0f}): pot tip {math.sqrt(o0 @ o0):4.1f} mm off axis "
              f"(inside bore {inside}), pot clear of walls ({pot_out:.2f} mm^3); "
              f"roots reach the film after {t:5.1f} mm, {ang:4.1f} deg from the floor line "
              f"-> {rep(inside and pot_out < 1.0 and t < 120 and ang < 35)}")
    # port lips stay above the film: lowest mouth point vs floor line
    for k in range(N_SEG):
        fr = frame(ROLLS[k], 0)
        side = math.degrees(math.acos((fr[:, :3] @ np.array([1, 0, 0])) @ -FL))
        print(f"  port {k + 1} opens {side:5.1f} deg from the ceiling line (< 90 = upper half) "
              f"-> {rep(side < 90)}")
    _, pd, o_top, _ = foot_points()
    _, q, i_pt, _ = head_points()
    sf = (pd[2] - o_top[2]) / np.hypot(*(pd[:2] - o_top[:2]))
    sh = (i_pt[2] - q[2]) / np.hypot(*(i_pt[:2] - q[:2]))
    print(f"  duct slopes: head {math.degrees(math.atan(sh)):.0f} deg, foot "
          f"{math.degrees(math.atan(sf)):.0f} deg downhill; joints: upper spigot inside the lower "
          f"socket, bore {2 * T_RI:.0f} mm continuous -> {rep(sf > 0.5 and sh > 0.5)}")
    print(f"  foot spout r={R_O:.0f}+{DUCT_RI + 2.2:.1f} (drip groove) inside bowl wall r={R_WI:.0f} "
          f"-> {rep(R_O + DUCT_RI + 2.2 < R_WI)}")
    zt = gt.Z_RB - gt.ROTOR_GAP_DRIP
    r_tip = gt.R_TI - (gt.Z_RT - gt.SOCK_D - zt)
    print(f"  bowl funnel -> spigot bore r={gt.R_SI:.1f} -> rotor drip lip r={r_tip:.1f} "
          f"< drain r={gt.R_DRAIN:.0f} -> {rep(r_tip < gt.R_DRAIN)}")
    print(f"  pan outlet r={OUT_R:.0f} + drip groove {OUT_R + 2.2:.1f} inside head cup r={CUP_R:.0f}, "
          f"outlets r={R_C:.0f} inside pan wall r={R_PWI:.0f} -> "
          f"{rep(OUT_R + 2.2 < CUP_R and R_C + OUT_R < R_PWI)}")
    jet = SPRAY_Z + 6.0
    print(f"  jets z={jet:.0f} hit the pan wall (r={R_PWI:.0f}, top z={Z_PT:.0f}) under the roof; "
          f"lip top z={SPRAY_Z + 3:.0f} < jet bottom {jet - 1.1:.1f} -> "
          f"{rep(SPRAY_Z + 3 < jet - 1.1 < Z_PT)}")
    cd, a_h = 0.6, math.pi * OUT_R ** 2 * 1e-6
    for lph in (400, 800):
        v = lph / 3.6e6 / N_TUBE / (cd * a_h)
        h = v * v / 2 / 9.81 * 1000
        print(f"  pan head at {lph} L/h: {h:4.1f} mm < lip {SPRAY_Z + 3 - Z_PB - PAN_FLOOR:.0f} mm "
              f"-> {rep(h < SPRAY_Z + 3 - Z_PB - PAN_FLOOR)}")
    print(f"  pan overflow (blocked outlets): over the lip, down the pipe (r={gt.PIPE_OD / 2:.1f}) "
          f"into the bowl -> drain")
    return allok, t0


def mass_torque(single, p):
    print("-- 5. mass / torque budget")
    rho, fill = 1.07e-3, 0.85                       # g/mm3, walls are mostly perimeters
    g = {n: vol(m) * rho * fill for n, m in
         [("segment", single["segment"]), ("foot_shoe", single["foot_shoe"]),
          ("head_shoe", single["head_shoe"]), ("rod_bracket", single["rod_bracket"]),
          ("bowl", p["bowl"]), ("crown_pan", p["crown_pan"]), ("crown_lid", p["crown_lid"])]}
    g["steel rods"] = vol(p["rods"]) * 7.85e-3 / N_ROD
    qty = {"segment": N_TUBE * N_SEG, "foot_shoe": N_TUBE, "head_shoe": N_TUBE,
           "rod_bracket": N_ROD, "steel rods": N_ROD}
    stack = sum(g[n] * qty.get(n, 1) for n in g)
    rotor = vol(p["rotor"]) * rho * fill
    for n in g:
        print(f"  {n:10s} {g[n]:6.0f} g x{qty.get(n, 1)}")
    water = (0.05 * N_TUBE + 0.18 + 0.05) * 1000     # films + pan + bowl, g
    plants = N_TUBE * N_SEG * 150.0                  # mature: pot, media, roots, leaves
    hw = 30 + 36 * 2                                 # screws + O-rings
    w_kg = (stack + rotor + water + plants + hw) / 1000
    print(f"  turning stack {stack / 1000:.2f} kg + rotor {rotor / 1000:.2f} + water "
          f"{water / 1000:.2f} + plants {plants / 1000:.1f} (36 x 150 g) + hardware "
          f"{hw / 1000:.2f} = {w_kg:.1f} kg")
    n = w_kg * 9.81
    t_race = [c * n * gt.RACE_R / 1000 for c in (0.005, 0.01)]
    # bushing: side load from 1 kg plant imbalance at r=150 + 10 N wind, mu 0.3
    h_lever = (STUB_TOP - gt.Z_RB) / 1000
    f_side = (1.0 * 9.81 * 0.15) / h_lever + 10.0 / 2
    t_bush = 0.3 * f_side * (gt.STUB_D / 2) / 1000
    tot = t_race[1] + t_bush
    print(f"  ball race {t_race[0]:.3f}-{t_race[1]:.3f} N m, bushing {t_bush:.3f} N m "
          f"(side load {f_side:.1f} N) -> worst {tot:.3f} N m = {tot / 0.2 * 100:.0f} % of 0.2 "
          f"-> {ok(tot < 0.1)}")
    # wind: frontal area of the lattice + foliage
    a_lat = (2 * RW + 2 * T_RO) / 1000 * (S_HALF * 2 * U[2]) / 1000 * 0.45
    a_fol = 0.12
    for v in (5.0, 10.0):
        f = 0.5 * 1.2 * v * v * 1.1 * (a_lat + a_fol)
        print(f"  wind {v:.0f} m/s: drag {f:5.1f} N on {a_lat + a_fol:.2f} m2; yaw torque if 10 % "
              f"of it acts at r=0.15 m: {0.1 * f * 0.15:.2f} N m")
    # lattice stiffness: pin-jointed bars from the fixed bottom ring to a rigid crown
    ea_t = 2000.0 * math.pi * (T_RO ** 2 - T_RI ** 2)     # ASA tube, E ~2 GPa
    ea_r = 200000.0 * math.pi * ROD_R ** 2              # steel rod
    c = np.array([0, 0, Z_PB])
    bars = []
    for i in range(N_TUBE):
        a = math.radians(360.0 / N_TUBE * i)
        rz = np.array([[math.cos(a), -math.sin(a), 0], [math.sin(a), math.cos(a), 0], [0, 0, 1]])
        bars.append(("tube", rz @ axis_pt(S_HALF) - c, rz @ U, ea_t / (2 * S_HALF)))
    for pb, pt, d in rod_lines()[0]:
        bars.append(("rod", pt - c, d, ea_r / np.linalg.norm(pt - pb)))

    def solve(sel):
        K = np.zeros((6, 6))
        js = []
        for kind, top, n_, k in bars:
            if kind not in sel:
                continue
            j = np.concatenate([n_, np.cross(top, n_)])
            js.append((kind, j, k))
            K += k * np.outer(j, j)
        return K, js

    K, _ = solve(("tube",))
    r_t = np.linalg.matrix_rank(K, tol=1e-9 * np.abs(K).max())
    K, js = solve(("tube", "rod"))
    r_all = np.linalg.matrix_rank(K, tol=1e-9 * np.abs(K).max())
    w_top = 9.81 * (plants / 3 + g["crown_pan"] + g["crown_lid"] + 12 * g["head_shoe"]) / 1000
    f_w = 12.0                                         # half the 10 m/s drag, at the crown
    load = np.array([f_w, 0, -w_top, 0, 0, 0])
    dsp = np.linalg.solve(K, load)
    ft = [k * (j @ dsp) for kind, j, k in js if kind == "tube"]
    fr = [k * (j @ dsp) for kind, j, k in js if kind == "rod"]
    print(f"  lattice rank: tubes alone {r_t}/6 (one ruling = mechanism), tubes + {N_ROD} "
          f"counter-rods {r_all}/6; {f_w:.0f} N wind + {w_top:.0f} N crown load: sway "
          f"{1000 * math.hypot(dsp[0], dsp[1]):.0f} um, tube force {min(ft):.0f}..{max(ft):.0f} N, "
          f"rod force {min(fr):.0f}..{max(fr):.0f} N -> {ok(r_all == 6)}")
    return stack, w_kg


def overhang(tm):
    """Down-facing area steeper than 45 deg (cm2), excluding the bed face."""
    n = tm.face_normals
    a = tm.area_faces
    zmin = tm.bounds[0][2]
    low = tm.vertices[tm.faces][:, :, 2].max(axis=1) < zmin + 0.3
    bad = (n[:, 2] < -math.cos(math.radians(44))) & ~low
    flat = bad & (n[:, 2] < -0.99)
    return a[bad & ~flat].sum() / 100, a[flat].sum() / 100


# ---- section ----------------------------------------------------------------------
def section(parts):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Polygon

    cols = {"tank": "#3d4a3f", "lid": "#56645a", "fill_plug": "#56645a", "hub": "#2b2b2b",
            "leg": "#2b2b2b", "pod": "#7a6a55", "pinion": "#c9a227", "rotor": "#b8862e",
            "bowl": "#b0a27a", "foot_shoes": "#8c7b55", "segs": "#e8e2d0",
            "head_shoes": "#8c7b55", "crown_pan": "#cfc6aa", "crown_lid": "#a89c78",
            "spray_head": "#4a90c2", "pipe": "#9fb7c9", "pipe_foot": "#4a90c2",
            "float_bracket": "#4a90c2", "net_pots": "#5a8f3a", "rods": "#555555",
            "rod_brackets": "#8c7b55"}

    def colr(n):
        for k_, c in cols.items():
            if n.startswith(k_):
                return c
        return "#999"

    fig, axs = plt.subplots(1, 2, figsize=(17, 15), dpi=100)
    # (a) through the axis (y = 0) and (b) the tangent plane x = RW of tube 0
    mats = [np.array([[1, 0, 0, 0], [0, 0, 1, 0], [0, -1, 0, 0]], float),
            np.array([[0, 1, 0, 0], [0, 0, 1, 0], [1, 0, 0, -RW]], float)]
    titles = ["(a) cut through the axis (plane y = 0)",
              "(b) cut along tube 0 (tangent plane x = waist radius)"]
    for ax, mt, ti in zip(axs, mats, titles):
        seen = set()
        for name, m in parts.items():
            if name.startswith(("leg", "hub")) and ax is axs[1]:
                continue
            key = name.rstrip("0123456789").rstrip("_")
            for poly in m.transform(mt).slice(0.0).to_polygons():
                ax.add_patch(Polygon(poly, closed=True, fc=colr(name), ec="k", lw=0.3,
                                     label=key if key not in seen else None))
                seen.add(key)
        ax.set_aspect("equal")
        ax.grid(alpha=0.25)
        ax.set_title(ti)
        ax.set_xlabel("mm")
    blue = dict(arrowstyle="->", color="#1f77b4", lw=2.2)
    ax = axs[0]
    ax.annotate("", (0, SPRAY_Z + 6), (0, gt.TANK_FLOOR + 80), arrowprops=blue)
    for s in (1, -1):
        ax.annotate("", (s * (R_PWI - 2), SPRAY_Z + 4), (s * 16, SPRAY_Z + 6), arrowprops=blue)
        ax.annotate("", (s * 75, ZS - 25), (s * 100, Z_RIM - 5), arrowprops=blue)
    ax.annotate("pan: 12 outlets -> head shoes", (R_C, Z_PB), (40, Z_PT + 80),
                arrowprops=dict(arrowstyle="->"), fontsize=9)
    ax.annotate("bowl -> rotor bore -> lid drain", (80, ZS + 5), (130, ZS - 90),
                arrowprops=dict(arrowstyle="->"), fontsize=9)
    ax.set_xlim(-gt.LEG_R_END, gt.LEG_R_END)
    ax.set_ylim(-gt.HUB_T - 20, Z_PT + 120)
    ax.legend(loc="upper left", fontsize=7)
    ax = axs[1]
    # floor line of tube 0 in the tangent plane: offset T_RI towards FL
    f0, f1 = axis_pt(S_HALF + Q_L) + T_RI * FL, axis_pt(-S_HALF) + T_RI * FL
    ax.annotate("", (f1[1], f1[2]), (f0[1], f0[2]), arrowprops=blue)
    _, pd, o_top, _ = foot_points()
    _, q, i_pt, _ = head_points()
    ax.annotate("film on the tube floor\n(low side), roots hang into it", (f1[1] + 40, f1[2] + 200),
                (f1[1] + 120, f1[2] + 260), arrowprops=dict(arrowstyle="->"), fontsize=9)
    ax.annotate("O-ring bayonet joint:\nupper spigot inside lower socket",
                tuple(axis_pt(-S_HALF + SEG_L)[1:]), (-260, axis_pt(-S_HALF + SEG_L)[2] + 40),
                arrowprops=dict(arrowstyle="->"), fontsize=9)
    ax.set_xlim(-300, 300)
    ax.set_ylim(Z_RIM - 120, Z_PT + 60)
    fig.suptitle(f"Hyperboloid Lattice: {N_TUBE} tubes x {N_SEG} ports = {N_TUBE * N_SEG} plants, "
                 f"{Z_PT + ROOF_T + gt.HUB_T:.0f} mm on the stand", fontsize=14)
    os.makedirs(os.path.join(HERE, "preview"), exist_ok=True)
    fig.savefig(os.path.join(HERE, "preview", "section_2d.png"), bbox_inches="tight")
    print("  wrote preview/section_2d.png")


# ---- export -------------------------------------------------------------------------
FLIP = gt.FLIP


def export(parts, single):
    singles = {"segment": single["segment"], "foot_shoe": single["foot_shoe"],
               "head_shoe": single["head_shoe"], "rod_bracket": single["rod_bracket"],
               "bowl": parts["bowl"], "crown_pan": parts["crown_pan"],
               "crown_lid": parts["crown_lid"]}
    orient = {"segment": (None, "spigot down"), "foot_shoe": (None, "pad down"),
              "head_shoe": (FLIP, "pad down"), "rod_bracket": (FLIP, "pad down"),
              "bowl": (None, "spigot down"), "crown_pan": (None, "floor down"),
              "crown_lid": (FLIP, "roof down")}
    qty = {"segment": N_TUBE * N_SEG, "foot_shoe": N_TUBE, "head_shoe": N_TUBE,
           "rod_bracket": N_ROD}
    preview = {n: f"preview/{n}.stl" for n in
               ("tank_bottom", "tank_ring_1", "tank_ring_2", "lid", "fill_plug", "pod_base",
                "pod_roof", "pinion", "rotor", "pipe_foot", "float_bracket", "hub",
                "leg_1", "leg_2", "leg_3", "leg_4")}
    meta = {n: gt.base_meta(n) for n in preview}
    mine = {"pipe": (pipe(), ("#9fb7c9", 2)), "bowl": (parts["bowl"], ("#b0a27a", 4, True)),
            "foot_shoes": (parts["foot_shoes"], ("#8c7b55", 4.6, True)),
            "segs_1": (parts["segs_1"], ("#e8e2d0", 5.4, True)),
            "segs_2": (parts["segs_2"], ("#d9d2bd", 6.4, True)),
            "segs_3": (parts["segs_3"], ("#e8e2d0", 7.4, True)),
            "net_pots": (parts["net_pots"], ("#5a8f3a", 6.4, True)),
            "rods": (parts["rods"], ("#555555", 6.4, True)),
            "head_shoes": (parts["head_shoes"], ("#8c7b55", 8.2, True)),
            "rod_brackets": (parts["rod_brackets"], ("#8c7b55", 8.6, True)),
            "spray_head": (parts["spray_head"], ("#4a90c2", 9.0)),
            "crown_pan": (parts["crown_pan"], ("#cfc6aa", 9.6, True)),
            "crown_lid": (parts["crown_lid"], ("#a89c78", 10.4, True))}
    for n, (m, c) in mine.items():
        preview[n] = m
        meta[n] = c
    res = gt.export_set(HERE, singles, orient, qty, preview, meta,
                        f"Hyperboloid Lattice: {N_TUBE} tubes x {N_SEG} ports", target_z=760.0)
    print("-- print overhangs > 45 deg (cm2: sloped / flat ceilings), excluding the bed face")
    for n, m in singles.items():
        rot, how = orient[n]
        tm = gt.to_trimesh(rot(m) if rot else m)
        a, f = overhang(tm)
        print(f"  {n:10s} {a:5.1f} / {f:5.1f}")
    return res


def report():
    print("-- hyperboloid lattice")
    L = 2 * S_HALF
    ends = math.hypot(RW, S_HALF * U[1])
    print(f"  {N_TUBE} tubes, axis length {L:.0f} mm joint-to-joint, tilt {BETA:.0f} deg, "
          f"waist r={RW:.0f} at z={ZW:.0f}, ends r={ends:.0f} "
          f"(z={Z_A:.0f} .. {Z_A + L * U[2]:.0f}), twist {2 * math.degrees(math.atan(S_HALF * U[1] / RW)):.0f} deg")
    print(f"  segment {SEG_L:.0f} mm + {J_D:.0f} socket, ports rolled {ROLLS} deg, "
          f"bayonet step {D_ROLL:+.0f} deg")
    print(f"  pipe 1/2in PVC cut to {PIPE_LEN:.0f} mm; pan floor z={Z_PB:.0f}; height "
          f"{Z_PT + ROOF_T + gt.HUB_T:.0f} mm on the stand")
    w0 = np.array([RW, 0, 0])
    a = math.radians(360 / N_TUBE)
    w1 = np.array([RW * math.cos(a), RW * math.sin(a), 0])
    u1 = np.array([-U[1] * math.sin(a), U[1] * math.cos(a), U[2]])
    c = np.cross(U, u1)
    print(f"  axis-to-axis closest approach {abs((w1 - w0) @ c) / np.linalg.norm(c):.1f} mm "
          f"(tube od {2 * T_RO:.1f}, socket od {2 * SK_RO:.1f})")
    lines, phi = rod_lines()
    pb, pt, d = lines[0]
    rl = np.linalg.norm(pt - pb) - 2 * ROD_END
    rw = min(np.linalg.norm(np.cross(pb + t * (pt - pb), [0, 0, 1])) for t in np.linspace(0, 1, 201))
    print(f"  {N_ROD} counter-rods d{2 * ROD_R:.0f} cut to {rl:.0f} mm, twist {-phi:.0f} deg, "
          f"tilt {math.degrees(math.acos(d[2])):.0f} deg, waist r={rw:.0f}")


def main():
    parts, leg, single = build()
    report()
    allok, _ = checks(parts, single)
    print(f"  checks 1-3 all -> {ok(allok)}")
    print("-- 4. bed fit + watertight")
    export(parts, single)
    mass_torque(single, parts)
    sec = {n: m for n, m in parts.items() if n not in ("net_pots",)}
    sec["pipe"] = pipe()
    sec["net_pots"] = parts["net_pots"]
    section(sec)


if __name__ == "__main__":
    main()
