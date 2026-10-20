"""Home "MagicBand reader" (park-entry touchpoint look), wall-mounted beside a
front door, outdoors.  ASA shells + TPU 95A gaskets, every part prints on a
256 x 256 bed (Bambu P1S) without supports.

    wall --- WALL_BRACKET (plate + sconce shelf, cable bore into the wall)
               |  4 x M3 from below
             ARM_BASE (neck boss + bar + pod, hollow cable channel)
             /                                  \\
         NECK (cup hugs the ball)               POD_CAP (sloped, oval finger
             |  3 x M3 from inside the ball      funnel + R503 fingerprint)
         BALL_REAR (service opening -> REAR_HATCH + tamper switch, faces wall)
             |  4 x M3 seam screws through FACE_CARRIER tabs
         BALL_FRONT (face opening) holding the face stack:
             HALO_RING (translucent) + FACE_DISC (+ MICKEY_INLAY or blank)
             FACE_CARRIER behind it: WS2812B ring, PN532, speaker duct,
             ELECTRONICS_TRAY (ESP32-S3, MAX98357A, MAX3485, 5 V + 3.3 V bucks,
             protection board)
    indoors: CONTROLLER_BOX + CONTROLLER_LID (PETG; ESP32 DevKit, relay ...)

World frame: wall = plane y = 0 (indoor side y < 0), z up, face points +y,
arm runs +x parallel to the wall from the neck (x = 0) to the pod (x = POD_X).
Ball parts are modelled in a ball frame (origin = ball centre, +y = face axis)
and moved to (0, YC, ZC).  The pod cap uses a local frame (a = x, b = downhill
on the sloped top, w = top normal).

Joints are stacked so gaskets (modelled at their FREE thickness GASKET_T) sit
in GASKET_GAP gaps -> the overlap is their compression, reported by the fit
check.  The face carrier tabs are clamped between ball_rear lugs and
ball_front bosses by the seam screws, so the carrier also presses the halo
onto the face gasket.

Run: PYTHONPATH=../../.pydeps python3 magicband.py
Outputs stl/ (print orientation), preview/ (assembled + context + manifest).
"""
import json
import math
import os

import numpy as np
import manifold3d as m3d

OUT = os.path.dirname(os.path.abspath(__file__))
SEG = 160

# ---- parameters (mm) -------------------------------------------------------
BED = 256.0            # printer bed (Bambu P1S)
BED_MARGIN = 3.0
OVERHANG = 45.0        # max overhang from vertical, deg
GASKET_T = 1.5         # TPU gasket free thickness
GASKET_GAP = 1.0       # assembled gap -> 0.5 mm (33 %) compression
INSERT_R = 2.0         # M3 heat-set insert hole (D4.0, e.g. M3 x 5.7 x 4.6)

# ball (ball frame)
R_BALL = 75.0          # 150 mm ball
T_SHELL = 3.0
FACE_Y = 50.0          # flat face plane ahead of the centre
R_BORE = 52.0          # face opening (visible halo edge)
SEAT_Y = 44.0          # collar seat behind the face (face gasket)
SEAM_Y = 30.0          # ball_front / ball_rear seam, forward of the centre
REAR_Y = -33.0         # rear service opening plane (hidden, faces the wall)
HATCH_T = 4.0
WALL_GAP = 15.0        # hatch back -> wall
R_SCREW = 60.5         # seam + hatch screw circle
SEAM_ANG = (45.0, 135.0, 225.0, 315.0)
HATCH_ANG = (0.0, 90.0, 180.0, 270.0)
TAMPER_ANG = 22.5
FLAT_R = 20.0          # hidden flat under the ball where the neck seats

# face stack (ball frame, r about the y axis)
HALO_Y0 = 40.0         # halo shoulder back face (sits on the carrier)
HALO_SH = 43.0         # shoulder front -> face gasket
R_HALO_LIP = 44.3      # visible halo ring r 44.3 .. 51.7
R_HALO_IN = 46.3
R_HALO_OUT = 51.7
R_HALO_SH = 55.5
DISC_Y0 = 44.6         # face disc back
R_DISC = 44.0
STROKE = 3.0           # Mickey outline stroke
INLAY_CLR = 0.08       # inlay press-fit clearance per side
SPK_HOLES = 7
SPK_HOLE_D = 2.0
SPK_V = 31.0           # speaker hole row height on the face

# electronics in the ball
N_LED = 42             # WS2812B 144/m ring (42 x 6.94 mm = 292 mm strip)
R_LED = N_LED * 1000.0 / 144 / (2 * math.pi)
LED_W, LED_H = 10.0, 3.0
LED_FLOOR = 36.5
PN_W, PN_H, PN_T = 42.7, 40.4, 1.6     # elechouse PN532 V3
PN_Z = -8.0            # board centre height (Mickey head centre)
PN_FRONT = 41.0        # antenna face y
PN_HOLE_INSET = 3.0
SPK_D, SPK_T = 40.0, 6.0               # 40 mm speaker
SPK_Z = 31.0
CARRIER_Y = SEAM_Y     # carrier back = seam plane
BOARDS = {             # tray boards: x0, x1, y0, y1, height (ball frame, on tray)
    "esp32s3": (-40.0, -14.6, 4.0, 22.0, 5.0),     # ESP32-S3-Zero class 25.4 x 18
    "max98357a": (-10.0, 9.0, 4.0, 22.0, 4.0),
    "buck": (13.0, 35.0, 3.5, 22.0, 6.0),          # 5 V 3 A (Pololu D24V30F5 / MP1584)
    "max3485": (-22.0, 22.0, -24.0, -10.0, 12.0),
    "buck3v3": (25.5, 43.3, -22.0, -11.5, 4.0),     # 3.3 V 0.5 A (Pololu D24V5F3)
    "protect": (-43.3, -25.3, -27.0, -12.0, 8.0),   # SS54 + SMBJ15A + SM712 perfboard
}
TRAY_Z = -25.0         # tray top

# neck + arm (world)
Z_BOSS = 40.0          # arm neck boss top
NECK_H = 32.0
R_NECK = 22.0
R_CUP = 32.0
R_BOSS = 26.0
BAR_W, BAR_H = 36.0, 30.0
POD_X = 165.0          # pod axis from the neck axis (park proportion)
R_POD = 40.0
Z_POD = 95.0           # pod top centre
POD_TILT = 30.0        # top faces the visitor
CAP_H = 14.0
POD_SCREW_R = 33.0
POD_SCREW_ANG = (0.0, 220.0, 320.0)
CH_W, CH_H = 16.0, 10.0  # cable channel, 50 deg roof above
FLOOR = 3.0

# R503 (GROW): flange 28, M25 body 19 high (M25 nut)
R503_FLANGE = (14.0, 2.0)
R503_BODY = (12.5, 17.0)
R503_NUT = (17.0, 4.0)
FUNNEL = (16.0, 23.0, 9.5)  # oval finger recess: semi-axes across / downhill, depth
R503_PANEL = -13.5     # underside of the sensor boss (w), nut clamps here

# wall bracket
XB = 80.0              # bracket centre under the bar
PLATE_X = (40.0, 120.0)
PLATE_Z = (-96.0, 20.0)
PLATE_T = 8.0
BORE_R = 6.0           # 4-core 6 mm cable
BORE_DROP = 30.0       # deg below horizontal toward the wall

# controller box (indoor, PETG)
CB_L, CB_W, CB_H, CB_T = 136.0, 90.0, 42.0, 2.4
CB_BOARDS = {
    "ctl_devkit": (12.0, 67.0, 12.0, 40.0, 13.0),
    "ctl_relay": (72.0, 122.0, 12.0, 38.0, 19.0),
    "ctl_max3485": (12.0, 56.0, 52.0, 66.0, 12.0),
    "ctl_buck": (62.0, 84.0, 52.0, 69.0, 6.0),
    "ctl_terminal": (96.0, 116.0, 56.0, 68.0, 12.0),
}

# derived
YC = WALL_GAP + HATCH_T + GASKET_GAP - REAR_Y        # ball centre y
FLAT_D = math.sqrt(R_BALL ** 2 - FLAT_R ** 2)
ZN0 = Z_BOSS + GASKET_GAP                            # neck bottom
ZF = ZN0 + NECK_H                                    # neck flat top
ZC = ZF + GASKET_GAP + FLAT_D                        # ball centre z
RI = R_BALL - T_SHELL
S, G = SEAM_Y, GASKET_GAP
TS, TC = math.sin(math.radians(POD_TILT)), math.cos(math.radians(POD_TILT))
POD_N = np.array([0.0, TS, TC])
POD_P = np.array([POD_X, YC, Z_POD])
POD_RIM = -CAP_H - GASKET_GAP                         # pod rim w
TAN_OK = math.tan(math.radians(50.0))                 # 50 deg design slope (> 45)


# ---- helpers ---------------------------------------------------------------
def box(x0, x1, y0, y1, z0, z1):
    return m3d.Manifold.cube((x1 - x0, y1 - y0, z1 - z0)).translate((x0, y0, z0))


def union(parts):
    parts = [p for p in parts if not p.is_empty()]
    return m3d.Manifold.batch_boolean(parts, m3d.OpType.Add)


def clean(m):
    """Drop zero-volume sliver components left by coplanar booleans."""
    return m3d.Manifold.compose([c for c in m.decompose() if c.volume() > 1.0])


def vol(m):
    return m.volume()


def xform(m, rows):
    return m.transform(np.array(rows, dtype=float))


def poly(pts):
    """CrossSection from one contour, made counter-clockwise."""
    a = sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1]))
    return m3d.CrossSection([pts if a > 0 else pts[::-1]])


def zcyl(r, z0, z1, x=0.0, y=0.0, seg=SEG):
    return m3d.Manifold.cylinder(z1 - z0, r, r, seg).translate((x, y, z0))


def zcone(r0, r1, z0, z1, x=0.0, y=0.0, seg=SEG):
    return m3d.Manifold.cylinder(z1 - z0, r0, r1, seg).translate((x, y, z0))


def z2y(m, x=0.0, y0=0.0, z=0.0):
    """Local z axis -> world +y (local y -> world -z)."""
    return xform(m, [[1, 0, 0, x], [0, 0, 1, y0], [0, -1, 0, z]])


def ycyl(r, y0, y1, x=0.0, z=0.0, seg=SEG):
    return z2y(m3d.Manifold.cylinder(y1 - y0, r, r, seg), x, y0, z)


def ycone(r0, r1, y0, y1, x=0.0, z=0.0, seg=SEG):
    return z2y(m3d.Manifold.cylinder(y1 - y0, r0, r1, seg), x, y0, z)


def blind_y(r, y0, y1, x=0.0, z=0.0):
    """Blind hole along +y ending in a 50 deg drill-point cone (no flat ceiling)."""
    return ycyl(r, y0, y1, x, z, 48) + ycone(r, 0.05, y1, y1 + r * 1.2, x, z, 48)


def yrev(pts):
    """Revolve a (r, y) profile about the y axis."""
    return z2y(m3d.Manifold.revolve(poly(pts), SEG))


def at_ang(m, deg):
    """Rotate about the y axis so local +x (radial) points to deg in the x-z plane."""
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return xform(m, [[c, 0, -s, 0], [0, 1, 0, 0], [s, 0, c, 0]])


def radial_box(r0, r1, y0, y1, half_t, deg):
    return at_ang(box(r0, r1, y0, y1, -half_t, half_t), deg)


def polar(r, deg):
    return r * math.cos(math.radians(deg)), r * math.sin(math.radians(deg))


def xprism(cs, x0, x1, yoff=0.0, zoff=0.0):
    """Extrude a (y, z) section along +x."""
    m = m3d.Manifold.extrude(cs, x1 - x0)
    return xform(m, [[0, 0, 1, x0], [1, 0, 0, yoff], [0, 1, 0, zoff]])


def face_prism(cs, y0, y1):
    """Extrude a face-view section (u = right as seen from the front, v = up)
    along +y from y0 to y1 (ball frame)."""
    m = m3d.Manifold.extrude(cs, y1 - y0)
    return xform(m, [[-1, 0, 0, 0], [0, 0, 1, y0], [0, 1, 0, 0]])


def teardrop_cs(r):
    """Circle + 40 deg roof toward +y: horizontal holes print without support."""
    tip = r / math.sin(math.radians(40.0))
    pts = [(r * math.cos(2 * math.pi * k / 48), r * math.sin(2 * math.pi * k / 48)) for k in range(48)]
    return m3d.CrossSection.hull_points(pts + [(0.0, tip)])


def tear_z(r, x, y, z0, z1):
    """Hole along z, roof toward +y."""
    return m3d.Manifold.extrude(teardrop_cs(r), z1 - z0).translate((x, y, z0))


def tear_y(r, x, z, y0, y1):
    """Hole along y, roof toward +z."""
    m = m3d.Manifold.extrude(teardrop_cs(r), y1 - y0)
    return xform(m, [[-1, 0, 0, x], [0, 0, 1, y0], [0, 1, 0, z]])


def tear_x(r, y, z, x0, x1):
    """Hole along x, roof toward +z."""
    m = m3d.Manifold.extrude(teardrop_cs(r), x1 - x0)
    return xform(m, [[0, 0, 1, x0], [1, 0, 0, y], [0, 1, 0, z]])


def rot_to_z(u):
    """Rotation matrix taking unit vector u to +z."""
    u = np.asarray(u, float) / np.linalg.norm(u)
    z = np.array([0.0, 0.0, 1.0])
    c = float(u @ z)
    if c < -1 + 1e-9:
        return np.diag([1.0, -1.0, -1.0])
    v = np.cross(u, z)
    vx = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    return np.eye(3) + vx + vx @ vx / (1 + c)


def cyl_between(p0, p1, r):
    p0, p1 = np.asarray(p0, float), np.asarray(p1, float)
    d = p1 - p0
    rot = rot_to_z(d).T                      # +z -> d
    m = m3d.Manifold.cylinder(float(np.linalg.norm(d)), r, r, 64)
    return m.transform(np.hstack([rot, p0[:, None]]))


def to_ball(m):
    return m.translate((0.0, YC, ZC))


def to_pod(m):
    """Pod-cap frame (a = x, b = downhill, w = top normal) -> world."""
    return xform(m, [[1, 0, 0, POD_X], [0, TC, TS, YC], [0, -TS, TC, Z_POD]])


def pod_slab(m, w0=None, w1=None):
    """Keep w0 <= w <= w1 (w measured along the sloped-top normal)."""
    d = float(POD_N @ POD_P)
    if w0 is not None:
        m = m.trim_by_plane(tuple(POD_N), d + w0)
    if w1 is not None:
        m = m.trim_by_plane(tuple(-POD_N), -(d + w1))
    return m


def ycut(m, y0, y1):
    return m.trim_by_plane((0, 1, 0), y0).trim_by_plane((0, -1, 0), -y1)


SPH = m3d.Manifold.sphere(R_BALL, SEG)
SPH_I = m3d.Manifold.sphere(RI, SEG)


# ---- logo (swap this function for a custom icon) ---------------------------
def logo_mickey(stroke=STROKE):
    """Mickey-head outline: outline of head + two ears, face-view coords (mm).
    Returns (stroke region, bridges) - bridges keep the island attached."""
    rh, re = 18.0, 10.8
    hc = (0.0, -10.0)
    ex = 1.25 * rh * math.cos(math.radians(45))
    ears = [(hc[0] - ex, hc[1] + ex), (hc[0] + ex, hc[1] + ex)]
    shape = m3d.CrossSection.circle(rh, 128).translate(hc)
    for c in ears:
        shape = shape + m3d.CrossSection.circle(re, 96).translate(c)
    band = shape.offset(stroke / 2, m3d.JoinType.Round, circular_segments=96) - \
        shape.offset(-stroke / 2, m3d.JoinType.Round, circular_segments=96)
    bw = 1.6
    bridges = [m3d.CrossSection.square((bw, 6.0)).translate((hc[0] - bw / 2, hc[1] - rh - 3)),
               m3d.CrossSection.square((6.0, bw)).translate((hc[0] - rh - 3, hc[1] - bw / 2)),
               m3d.CrossSection.square((6.0, bw)).translate((hc[0] + rh - 3, hc[1] - bw / 2))]
    for cx, cy in ears:
        bridges.append(m3d.CrossSection.square((bw, 6.0)).translate((cx - bw / 2, cy + re - 3)))
    br = bridges[0]
    for b in bridges[1:]:
        br = br + b
    return band, br


LOGO = logo_mickey


# ---- ball ------------------------------------------------------------------
def seam_notch():
    return union(radial_box(55.0, 68.0, S - 6, S + 3, 5.6, a) for a in SEAM_ANG)


def make_ball_front():
    shell = ycut(SPH - SPH_I, S + G, FACE_Y)
    collar = ycut(SPH, SEAT_Y, FACE_Y)
    bosses = union(at_ang(ycyl(4.0, S + 3, FACE_Y, x=R_SCREW), a) for a in SEAM_ANG) ^ SPH
    spig = yrev([(62.5, S - 5), (65.0, S - 5), (65.0, S + G), (67.5, S + G),
                 (67.5, S + G + 5.0 / 0.8), (62.5, S + G)]) ^ SPH
    m = union([shell, collar, bosses, spig - seam_notch()])
    m = m - ycyl(R_BORE, 0, FACE_Y + 1)
    m = m - union(at_ang(ycyl(INSERT_R, S + 2.9, S + 9, x=R_SCREW), a) for a in SEAM_ANG)
    return m


def tamper_pos():
    return polar(59.7, TAMPER_ANG)


def make_ball_rear():
    shell = ycut(SPH - SPH_I, REAR_Y, S)
    lug_cs = poly([(56.0, S), (74.0, S), (74.0, S - 8 - 1.2 * 18), (56.0, S - 8)])
    lug = m3d.Manifold.extrude(lug_cs, 9.0).translate((0, 0, -4.5))
    lugs = union(at_ang(lug, a) for a in SEAM_ANG) ^ SPH
    hl = union(radial_box(56.0, 66.0, REAR_Y, REAR_Y + 8, 5.0, a) for a in HATCH_ANG) ^ SPH
    tb = radial_box(55.0, 65.0, REAR_Y, REAR_Y + 9, 9.0, TAMPER_ANG) ^ SPH
    pad = zcone(17 + 1.19 * (80 - FLAT_D + 7), 17.0, -80.0, -FLAT_D + 7) ^ SPH
    m = union([shell, lugs, hl, tb, pad]).trim_by_plane((0, 0, 1), -FLAT_D)
    cuts = []
    for a in SEAM_ANG:
        cuts += [at_ang(ycyl(1.7, S - 31, S + 1, x=R_SCREW), a),
                 at_ang(ycyl(3.0, S - 40, S - 5, x=R_SCREW), a),
                 at_ang(ycone(3.0, 1.7, S - 5, S - 5 + 1.3 * 1.2, x=R_SCREW), a)]
    for a in HATCH_ANG:
        cuts.append(at_ang(blind_y(INSERT_R, REAR_Y - 1, REAR_Y + 6, x=R_SCREW), a))
    cuts += [radial_box(56.6, 62.8, REAR_Y + 3, REAR_Y + 10, 6.6, TAMPER_ANG),
             at_ang(ycyl(1.6, REAR_Y - 1, REAR_Y + 3.1, x=59.7), TAMPER_ANG)]
    cuts.append(tear_z(7.0, 0, 0, -80, -60))
    for a in (0.0, 120.0, 240.0):
        x, y = polar(14.0, a)
        cuts.append(tear_z(1.7, x, y, -80, -60))
    return m - union(cuts)


def make_rear_hatch():
    y1 = REAR_Y - G
    m = ycyl(67.0, y1 - HATCH_T, y1)
    m = m - union(at_ang(ycyl(1.7, y1 - HATCH_T - 1, y1 + 1, x=R_SCREW), a) for a in HATCH_ANG)
    x, z = tamper_pos()
    return m + ycyl(1.4, y1 - 0.01, REAR_Y - 0.05, x=x, z=z)


# ---- face stack ------------------------------------------------------------
def make_halo():
    return yrev([(R_HALO_IN, HALO_Y0), (R_HALO_SH, HALO_Y0), (R_HALO_SH, HALO_SH),
                 (R_HALO_OUT, HALO_SH), (R_HALO_OUT, FACE_Y), (R_HALO_LIP, FACE_Y),
                 (R_HALO_LIP, 48.0), (R_HALO_IN, 45.8)])


def disc_body():
    return yrev([(0.0, DISC_Y0), (46.0, DISC_Y0), (46.0, 45.7), (R_DISC, 47.9),
                 (R_DISC, FACE_Y), (0.0, FACE_Y)])


def speaker_holes():
    cs = None
    for k in range(SPK_HOLES):
        c = m3d.CrossSection.circle(SPK_HOLE_D / 2, 32).translate(((k - (SPK_HOLES - 1) / 2) * 3.0, SPK_V))
        cs = c if cs is None else cs + c
    return face_prism(cs, DISC_Y0 - 0.1, FACE_Y + 0.1)


def make_face_disc(logo=LOGO):
    d = disc_body() - speaker_holes()
    if logo is None:
        return d
    band, br = logo()
    cut = face_prism(band.offset(INLAY_CLR, m3d.JoinType.Round), DISC_Y0 - 0.1, FACE_Y + 0.1) - \
        face_prism(br, DISC_Y0 - 0.2, DISC_Y0 + 2.0)
    return d - cut


def make_inlay(logo=LOGO):
    band, br = logo()
    m = face_prism(band.offset(-INLAY_CLR, m3d.JoinType.Round), DISC_Y0, FACE_Y)
    return m - face_prism(br.offset(0.15, m3d.JoinType.Miter), DISC_Y0 - 0.1, DISC_Y0 + 2.15)


def pn_holes():
    hx, hz = PN_W / 2 - PN_HOLE_INSET, PN_H / 2 - PN_HOLE_INSET
    return [(sx * hx, PN_Z + sz * hz) for sx in (-1, 1) for sz in (-1, 1)]


SPK_SCREWS = [(0.0, SPK_Z + 22.5)] + [(sx * 22.5 * math.cos(math.radians(30)), SPK_Z - 11.25)
                                      for sx in (-1, 1)]
TRAY_SCREWS = [(-35.0, -12.0), (35.0, -12.0)]
PUSHERS = [(-33.0, -20.0), (33.0, -20.0)]
DUCT = (12.0, 27.0, 35.0)  # half width, z0, z1 (inside)


def make_face_carrier():
    y0 = CARRIER_Y
    parts = [ycyl(56.2, y0, y0 + 2),
             yrev([(40.0, y0 + 2), (56.2, y0 + 2), (56.2, HALO_Y0), (51.6, HALO_Y0),
                   (51.6, LED_FLOOR), (41.2, LED_FLOOR), (41.2, LED_FLOOR + 1.5), (40.0, LED_FLOOR + 1.5)])]
    for a in SEAM_ANG:   # tabs clamped by the seam screws
        parts.append(at_ang(m3d.Manifold.batch_hull([ycyl(3.2, y0, S + 3, x=R_SCREW),
                                                     box(50.0, 54.0, y0, S + 3, -3.2, 3.2)]), a))
    for x, z in pn_holes():
        parts.append(ycyl(2.5, y0 + 1, PN_FRONT - PN_T, x=x, z=z))
    for x, z in PUSHERS:
        parts.append(ycyl(1.6, y0 + 1, DISC_Y0 - 0.1, x=x, z=z))
    hw, dz0, dz1 = DUCT
    parts.append(box(-hw - 1.2, hw + 1.2, y0 + 1, DISC_Y0 - 0.1, dz0 - 1.2, dz1 + 1.2))
    for x, z in SPK_SCREWS[1:]:
        parts.append(ycyl(3.0, y0 + 1, y0 + 5.5, x=x, z=z))
    for x, z in TRAY_SCREWS:
        parts.append(ycyl(3.0, y0 + 1, y0 + 8, x=x, z=z))
    m = union(parts)
    cuts = [box(-hw, hw, y0 - 1, DISC_Y0 + 1, dz0, dz1),            # sound duct
            ycyl(2.5, y0 - 1, LED_FLOOR + 0.5, x=0, z=-R_LED),     # LED feed
            box(-8.0, 8.0, y0 - 1, y0 + 3, -37.0, -33.0)]           # PN532 wires
    for a in SEAM_ANG:
        cuts.append(at_ang(ycyl(1.7, y0 - 1, S + 4, x=R_SCREW), a))
    for x, z in pn_holes():
        cuts.append(ycyl(1.1, y0 + 3, PN_FRONT, x=x, z=z))
    for x, z in SPK_SCREWS:
        cuts.append(blind_y(1.1, y0 - 1, y0 + 5 if z < 50 else y0 + 7, x=x, z=z))
    for x, z in TRAY_SCREWS:
        cuts.append(blind_y(1.25, y0 - 1, y0 + 7.5, x=x, z=z))
    return m - union(cuts)


def make_tray():
    yf = CARRIER_Y
    parts = [box(-45, 45, -30, yf - 3, TRAY_Z - 3, TRAY_Z),
             box(-45, 45, yf - 3, yf, TRAY_Z - 3, -6.0)]
    for x in (-45.0, 42.0):
        g = xprism(poly([(yf - 3, TRAY_Z), (yf - 3, TRAY_Z + 13), (yf - 16, TRAY_Z)]), x, x + 3)
        parts.append(g)
    for x0, x1, y0, y1, _ in BOARDS.values():
        parts.append(box(x0 - 1.6, x1 + 1.6, y0 - 1.6, y1 + 1.6, TRAY_Z, TRAY_Z + 2.5) -
                     box(x0 - 0.3, x1 + 0.3, y0 - 0.3, y1 + 0.3, TRAY_Z - 1, TRAY_Z + 3))
    m = union(parts)
    cuts = [tear_y(1.7, x, z, yf - 4, yf + 1) for x, z in TRAY_SCREWS]
    cuts.append(zcyl(5.0, TRAY_Z - 4, TRAY_Z + 1, x=30.0, y=-3.0))
    return m - union(cuts)


# ---- neck + arm --------------------------------------------------------------
NECK_TOP_SCREWS = [polar(14.0, a) for a in (0.0, 120.0, 240.0)]
NECK_BOT_SCREWS = [polar(16.0, a) for a in (60.0, 180.0, 300.0)]


def make_neck():
    body = union([zcyl(R_NECK, ZN0, ZF - 12, y=YC), zcone(R_NECK, R_CUP, ZF - 12, ZF + 1, y=YC),
                  zcyl(R_CUP, ZF + 1, ZF + 6, y=YC)])
    cup = m3d.Manifold.sphere(R_BALL + G, SEG).translate((0, YC, ZC)).trim_by_plane((0, 0, 1), ZF)
    m = body - cup - zcyl(8.0, ZN0 - 1, ZF + 10, y=YC)
    cuts = [zcyl(INSERT_R, ZF - 6, ZF + 1, x=x, y=YC + y) for x, y in NECK_TOP_SCREWS]
    cuts += [zcyl(INSERT_R, ZN0 - 1, ZN0 + 6, x=x, y=YC + y) + zcone(INSERT_R, 0.05, ZN0 + 6, ZN0 + 6 + 2.4,
                                                                x=x, y=YC + y) for x, y in NECK_BOT_SCREWS]
    return m - union(cuts)


def channel_cs():
    h = CH_W / 2
    return poly([(-h, FLOOR), (h, FLOOR), (h, FLOOR + CH_H), (0.0, FLOOR + CH_H + h * TAN_OK),
                 (-h, FLOOR + CH_H)])


def pod_screw_ab(deg):
    """Pod-frame (a, b) of a cap screw axis that crosses w = -18.5 at radius 33."""
    x, y = polar(POD_SCREW_R, deg)
    return x, (y + 18.5 * TS) / TC


def pod_col_xy(deg):
    x, y = polar(POD_SCREW_R, deg)
    return POD_X + x, YC + y


def make_arm_base():
    boss = zcyl(R_BOSS, 0, Z_BOSS - 3, y=YC) + zcone(R_BOSS, R_BOSS - 3, Z_BOSS - 3, Z_BOSS, y=YC)
    h = BAR_W / 2
    bar = xprism(poly([(-h, 0), (h, 0), (h, BAR_H - 6), (h - 6, BAR_H), (-h + 6, BAR_H),
                       (-h, BAR_H - 6)]), 0, POD_X, yoff=YC)
    pod = pod_slab(zcyl(R_POD, 0, 200, x=POD_X, y=YC), w1=POD_RIM)
    m = union([boss, bar, pod])
    m = m - union([zcyl(11.0, FLOOR, Z_BOSS + 1, y=YC), xprism(channel_cs(), 0, POD_X, yoff=YC),
                   zcyl(R_POD - 3, FLOOR, 200, x=POD_X, y=YC)])
    cols = union(zcyl(5.5, FLOOR - 0.5, 200, x=x, y=y) for x, y in map(pod_col_xy, POD_SCREW_ANG))
    m = m + pod_slab(cols, w1=POD_RIM)
    cuts = [zcyl(BORE_R, -1, FLOOR + 1, x=XB, y=YC), zcyl(1.5, -1, FLOOR + 1, x=POD_X + 20, y=YC)]
    for x, y in NECK_BOT_SCREWS:
        cuts += [zcyl(3.0, -1, Z_BOSS - 8, x=x, y=YC + y),
                 zcone(3.0, 1.7, Z_BOSS - 8, Z_BOSS - 8 + 1.3 * 1.2, x=x, y=YC + y),
                 zcyl(1.7, Z_BOSS - 8, Z_BOSS + 1, x=x, y=YC + y)]
    for x, y in BRACKET_SCREWS:
        cuts += [zcyl(INSERT_R, -1, 6, x=x, y=y), zcone(INSERT_R, 0.05, 6, 6 + 2.4, x=x, y=y)]
    for d in POD_SCREW_ANG:
        a, b = pod_screw_ab(d)
        cuts.append(to_pod(zcyl(INSERT_R, POD_RIM - 7, POD_RIM + 0.1, x=a, y=b, seg=32)))
    return m - union(cuts)


def make_pod_cap():
    outer = pod_slab(zcyl(R_POD, 0, 200, x=POD_X, y=YC), -CAP_H, 0.0)
    cav = pod_slab(zcyl(R_POD - 5.4, 0, 200, x=POD_X, y=YC), -40.0, -3.0)
    m = outer - cav
    bosses = union(to_pod(zcyl(4.5, -CAP_H, -2.9, *pod_screw_ab(d), seg=48)) for d in POD_SCREW_ANG)
    m = m + (bosses ^ zcyl(R_POD, 0, 200, x=POD_X, y=YC))
    m = m + to_pod(zcyl(22.0, R503_PANEL, -2.9))
    spig = pod_slab(zcyl(R_POD - 3.4, 0, 200, x=POD_X, y=YC) - zcyl(R_POD - 5.4, 0, 200, x=POD_X, y=YC),
                    -CAP_H - 6, -CAP_H + 1)
    spig = spig - union(zcyl(7.5, 0, 200, x=x, y=y) for x, y in map(pod_col_xy, POD_SCREW_ANG))
    m = m + spig
    fa, fb, fd = FUNNEL                        # semi-axes (across, downhill), depth
    top = fd + 0.5
    sa = (14.2 + (fa - 14.2) * top / fd) / 14.2
    sb = (14.2 + (fb - 14.2) * top / fd) / 14.2
    funnel = m3d.Manifold.extrude(m3d.CrossSection.circle(14.2, SEG), top, 0, 0.0, (sa, sb)).translate((0, 0, -fd))
    cuts = [to_pod(funnel), to_pod(zcone(12.75, 14.2, -fd - 1.6, -fd)),
            to_pod(zcyl(12.75, R503_PANEL - 1, -fd - 1.5))]
    for d in POD_SCREW_ANG:
        cuts.append(to_pod(zcyl(1.7, -CAP_H - 1, 1.0, *pod_screw_ab(d), seg=32)))
    return m - union(cuts)


# ---- wall bracket ------------------------------------------------------------
BRACKET_SCREWS = [(XB + sx * 19.0, YC + sy * 12.0) for sx in (-1, 1) for sy in (-1, 1)]
WALL_SCREWS = [(x, z) for x in (PLATE_X[0] + 10, PLATE_X[1] - 10) for z in (10.0, PLATE_Z[0] + 10)]


def bore_axis():
    a = np.array([XB, YC, 0.0])
    b = np.array([XB, 1.0, -(YC - 1.0) * math.tan(math.radians(BORE_DROP))])
    return a, b


def make_bracket():
    y0, y1 = G, G + PLATE_T
    z0, z1 = PLATE_Z
    plate = xprism(poly([(y0, z0), (y1, z0), (y1, z1), (y0, z1 + 6)]), *PLATE_X)
    pad = box(XB - 30, XB + 30, y1, YC + BAR_W / 2, -10, 0)
    yw = YC + BAR_W / 2
    web = xprism(poly([(y1, -10), (yw, -10), (y1, -10 - (yw - y1) * TAN_OK)]), XB - 12, XB + 12)
    m = union([plate, pad, web])
    a, b = bore_axis()
    d = (b - a) / np.linalg.norm(b - a)
    cuts = [cyl_between(a - 12 * d, b + 6 * d, BORE_R)]
    vg = poly([(XB - 4.2, 0.5), (XB + 4.2, 0.5), (XB, 7.0)])
    cuts.append(m3d.Manifold.extrude(vg, b[2] - z0 + 1).translate((0, 0, z0 - 1)))
    for x, z in WALL_SCREWS:
        cuts += [ycyl(2.3, 0, y1 + 1, x=x, z=z, seg=48), ycone(2.3, 4.6, y1 - 2.31, y1 + 0.01, x=x, z=z, seg=48)]
    for x, y in BRACKET_SCREWS:
        cuts.append(tear_z(1.7, x, y, -11, 1))
    return m - union(cuts)


# ---- controller box ------------------------------------------------------------
CB_BOSSES = [(x, y) for x in (6.9, CB_L - 6.9) for y in (6.9, CB_W - 6.9)]


def make_controller_box():
    t = CB_T
    m = box(0, CB_L, 0, CB_W, 0, CB_H) - box(t, CB_L - t, t, CB_W - t, t, CB_H + 1)
    m = m + union(zcyl(4.5, 0, CB_H, x=x, y=y, seg=48) for x, y in CB_BOSSES)
    for x0, x1, y0, y1, _ in CB_BOARDS.values():
        m = m + (box(x0 - 1.6, x1 + 1.6, y0 - 1.6, y1 + 1.6, t, t + 2.5) -
                 box(x0 - 0.3, x1 + 0.3, y0 - 0.3, y1 + 0.3, 0, t + 3))
    cuts = [zcyl(INSERT_R, CB_H - 8, CB_H + 1, x=x, y=y, seg=32) for x, y in CB_BOSSES]
    cuts += [tear_x(6.25, y, 20.0, -1, t + 1) for y in (25.0, 65.0)]      # PG7 glands
    cuts.append(tear_x(4.0, 45.0, 18.0, CB_L - t - 1, CB_L + 1))          # DC jack
    for x in (30.0, 96.0):
        cuts += [zcyl(2.25, -1, t + 1, x=x, y=76.0, seg=32), zcone(2.25, 4.5, t - 2.25, t + 0.01, x=x, y=76.0, seg=32)]
    return m - union(cuts)


def make_controller_lid():
    t = CB_T
    m = box(0, CB_L, 0, CB_W, CB_H, CB_H + t)
    lip = box(t + 0.3, CB_L - t - 0.3, t + 0.3, CB_W - t - 0.3, CB_H - 4, CB_H) - \
        box(t + 1.9, CB_L - t - 1.9, t + 1.9, CB_W - t - 1.9, CB_H - 5, CB_H + 1)
    lip = lip - union(zcyl(5.2, CB_H - 5, CB_H + 1, x=x, y=y, seg=48) for x, y in CB_BOSSES)
    m = m + lip
    return m - union(zcyl(1.7, CB_H - 1, CB_H + t + 1, x=x, y=y, seg=32) for x, y in CB_BOSSES)


def cb_to_world(m):
    """Controller box local (floor on z = 0) -> on the indoor wall face."""
    return xform(m, [[1, 0, 0, 160.0], [0, 0, -1, -40.0], [0, 1, 0, -240.0]])


# ---- gaskets -------------------------------------------------------------------
def make_gaskets():
    gk = {}
    gk["face_gasket"] = to_ball(yrev([(52.3, HALO_SH), (R_HALO_SH, HALO_SH),
                                      (R_HALO_SH, HALO_SH + GASKET_T), (52.3, HALO_SH + GASKET_T)]))
    gk["seam_gasket"] = to_ball(yrev([(65.7, S), (68.4, S), (68.4, S + GASKET_T), (65.7, S + GASKET_T)]))
    yh = REAR_Y - G
    hg = yrev([(64.3, yh), (67.0, yh), (67.0, yh + GASKET_T), (64.3, yh + GASKET_T)])
    hg = hg + union(at_ang(ycyl(4.5, yh, yh + GASKET_T, x=R_SCREW, seg=48), a) for a in HATCH_ANG)
    hg = hg - union(at_ang(ycyl(1.8, yh - 1, yh + 3, x=R_SCREW, seg=32), a) for a in HATCH_ANG)
    gk["hatch_gasket"] = to_ball(hg)
    ng = zcyl(19.5, ZF, ZF + GASKET_T, y=YC) - zcyl(8.5, ZF - 1, ZF + 3, y=YC)
    gk["neck_gasket"] = ng - union(zcyl(1.8, ZF - 1, ZF + 3, x=x, y=YC + y, seg=32) for x, y in NECK_TOP_SCREWS)
    bg = zcyl(21.5, Z_BOSS, Z_BOSS + GASKET_T, y=YC) - zcyl(11.5, Z_BOSS - 1, Z_BOSS + 3, y=YC)
    gk["neck_base_gasket"] = bg - union(zcyl(1.8, Z_BOSS - 1, Z_BOSS + 3, x=x, y=YC + y, seg=32)
                                        for x, y in NECK_BOT_SCREWS)
    ring = zcyl(R_POD - 0.3, 0, 200, x=POD_X, y=YC) - zcyl(R_POD - 3.2, 0, 200, x=POD_X, y=YC)
    pads = union(to_pod(zcyl(5.5, POD_RIM - 1, POD_RIM + 3, *pod_screw_ab(d), seg=48)) for d in POD_SCREW_ANG)
    pg = pod_slab(ring + pads, POD_RIM, POD_RIM + GASKET_T)
    gk["pod_gasket"] = pg - union(to_pod(zcyl(1.8, POD_RIM - 1, POD_RIM + 3, *pod_screw_ab(d), seg=32))
                                  for d in POD_SCREW_ANG)
    gk["r503_washer"] = to_pod(zcyl(16.5, R503_PANEL - GASKET_T, R503_PANEL) -
                               zcyl(12.8, R503_PANEL - 3, R503_PANEL + 1))
    wg = box(PLATE_X[0] + 1, PLATE_X[1] - 1, 0, GASKET_T, PLATE_Z[0] + 1, PLATE_Z[1] + 5)
    wg = wg - union(ycyl(2.6, -1, 3, x=x, z=z, seg=32) for x, z in WALL_SCREWS)
    gk["bracket_gasket"] = wg - box(XB - 6.5, XB + 6.5, -1, 3, PLATE_Z[0] - 2, -22.0)
    return gk


# ---- component dummies ---------------------------------------------------------
def components():
    c = {}
    c["pn532"] = to_ball(box(-PN_W / 2, PN_W / 2, PN_FRONT - PN_T, PN_FRONT, PN_Z - PN_H / 2, PN_Z + PN_H / 2) +
                         box(-12.5, 12.5, PN_FRONT - PN_T - 2.5, PN_FRONT - PN_T, PN_Z - 12.5, PN_Z + 12.5))
    c["speaker"] = to_ball(ycyl(SPK_D / 2, CARRIER_Y - SPK_T, CARRIER_Y, z=SPK_Z) +
                           ycyl(11.0, CARRIER_Y - SPK_T - 5, CARRIER_Y - SPK_T, z=SPK_Z))
    c["led_strip"] = to_ball(yrev([(R_LED - LED_W / 2, LED_FLOOR), (R_LED + LED_W / 2, LED_FLOOR),
                                   (R_LED + LED_W / 2, LED_FLOOR + LED_H), (R_LED - LED_W / 2, LED_FLOOR + LED_H)]))
    for name, (x0, x1, y0, y1, h) in BOARDS.items():
        c[name] = to_ball(box(x0, x1, y0, y1, TRAY_Z, TRAY_Z + h))
    sw = radial_box(56.8, 62.6, REAR_Y + 3.1, REAR_Y + 9.5, 6.4, TAMPER_ANG) + \
        at_ang(ycyl(1.2, REAR_Y, REAR_Y + 3.1, x=59.7, seg=32), TAMPER_ANG)
    c["tamper_switch"] = to_ball(sw)
    rf, rb, rn = R503_FLANGE, R503_BODY, R503_NUT
    fl0 = -FUNNEL[2] - 0.17
    c["r503"] = to_pod(union([zcyl(rf[0], fl0, fl0 + rf[1]), zcyl(rb[0], fl0 - rb[1], fl0),
                              zcyl(rn[0], R503_PANEL - G - rn[1], R503_PANEL - G)]))
    for name, (x0, x1, y0, y1, h) in CB_BOARDS.items():
        c[name] = cb_to_world(box(x0, x1, y0, y1, CB_T, CB_T + h))
    return c


def context():
    wall = box(-160, 340, -40, 0, -270, 280)
    band = m3d.CrossSection.circle(32.0, 96) - m3d.CrossSection.circle(29.0, 96)
    mb = xprism(band, -9, 9, yoff=YC + FACE_Y + 35, zoff=ZC)
    return {"wall": wall, "magicband": mb}


# ---- build -------------------------------------------------------------------
def build():
    singles = {
        "ball_front": make_ball_front(), "ball_rear": make_ball_rear(), "rear_hatch": make_rear_hatch(),
        "face_carrier": make_face_carrier(), "electronics_tray": make_tray(),
        "halo_ring": make_halo(), "face_disc": make_face_disc(), "face_disc_blank": make_face_disc(None),
        "mickey_inlay": make_inlay(), "neck": make_neck(), "arm_base": make_arm_base(),
        "pod_cap": make_pod_cap(), "wall_bracket": make_bracket(),
        "controller_box": make_controller_box(), "controller_lid": make_controller_lid(),
    }
    singles = {k: clean(v) for k, v in singles.items()}
    ball_local = ("ball_front", "ball_rear", "rear_hatch", "face_carrier", "electronics_tray",
                  "halo_ring", "face_disc", "mickey_inlay")
    parts = {}
    for k, v in singles.items():
        if k == "face_disc_blank":
            continue
        if k in ball_local:
            parts[k] = to_ball(v)
        elif k.startswith("controller"):
            parts[k] = cb_to_world(v)
        else:
            parts[k] = v
    gk = {k: clean(v) for k, v in make_gaskets().items()}
    parts.update(gk)
    for k, v in gk.items():
        singles[k] = v
    return parts, singles


# ---- checks ------------------------------------------------------------------
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


def overhang_area(tm):
    n = tm.face_normals
    down = (n[:, 2] < -math.cos(math.radians(OVERHANG)) - 1e-3) & (tm.triangles_center[:, 2] > 0.2)
    return tm.area_faces[down].sum()


def ok(flag):
    return "OK" if flag else "FAIL"


def bbox(m):
    b = m.bounding_box()
    return np.array(b[:3]), np.array(b[3:])


def bbox_hit(a, b, pad=0.0):
    (a0, a1), (b0, b1) = a, b
    return bool(np.all(a0 - pad <= b1) and np.all(b0 - pad <= a1))


# gasket -> clamping partners (the first is where the compression shows)
GASKET_PARTNERS = {
    "face_gasket": ("ball_front", "halo_ring"), "seam_gasket": ("ball_front", "ball_rear"),
    "hatch_gasket": ("ball_rear", "rear_hatch"), "neck_gasket": ("ball_rear", "neck"),
    "neck_base_gasket": ("neck", "arm_base"), "pod_gasket": ("pod_cap", "arm_base"),
    "bracket_gasket": ("wall_bracket", "wall"), "r503_washer": ("r503", "pod_cap"),
}


def report(parts):
    comps, ctx = components(), context()
    allok = True
    print("-- layout")
    hatch_back = YC + REAR_Y - G - HATCH_T
    print(f"  ball D{2 * R_BALL:.0f} centre (0, {YC:.1f}, {ZC:.1f}), face plane y={YC + FACE_Y:.1f}, "
          f"opening D{2 * R_BORE:.0f}, hatch back {hatch_back:.1f} mm off the wall -> "
          f"{ok(abs(hatch_back - WALL_GAP) < 0.01)}")
    print(f"  neck D{2 * R_NECK:.0f} x {NECK_H:.0f} (cup D{2 * R_CUP:.0f}), pod D{2 * R_POD:.0f} at "
          f"x={POD_X:.0f}, top {Z_POD:.0f} tilted {POD_TILT:.0f} deg, LED ring {N_LED} LEDs "
          f"(r {R_LED:.1f}, strip {N_LED * 1000 / 144:.0f} mm)")
    nfc = FACE_Y - PN_FRONT
    print(f"  NFC: PN532 antenna face -> outer face {nfc:.1f} mm (<= 10) -> {ok(nfc <= 10.0)}")
    allok &= nfc <= 10.0
    print("-- fit (all assembled pairs, overlap mm3; gaskets: compression mm)")
    objs = dict(parts)
    objs.update(comps)
    objs["wall"] = ctx["wall"]
    names = list(objs)
    bb = {k: bbox(v) for k, v in objs.items()}
    gpairs = {(g, p) for g, ps in GASKET_PARTNERS.items() for p in ps}
    n_pairs, worst = 0, (0.0, "")
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            if a in comps and b in comps or {a, b} <= {"wall"}:
                continue
            if not bbox_hit(bb[a], bb[b]):
                continue
            n_pairs += 1
            ov = vol(objs[a] ^ objs[b])
            if (a, b) in gpairs or (b, a) in gpairs:
                continue
            if ov > worst[0]:
                worst = (ov, f"{a}/{b}")
            if ov > 1e-2:
                allok = False
                print(f"  OVERLAP {a} / {b}: {ov:.3f} mm3 -> FAIL")
    print(f"  {n_pairs} touching-bbox pairs checked, max unintended overlap "
          f"{worst[0]:.4f} mm3 {worst[1]} -> {ok(worst[0] <= 1e-2)}")
    for g, ps in GASKET_PARTNERS.items():
        gm = objs[g]
        area = gm.volume() / GASKET_T
        res = []
        for p in ps:
            c = vol(gm ^ objs[p]) / area
            res.append(f"{p} {c:.2f}")
        good = abs(vol(gm ^ objs[ps[0]]) / area - (GASKET_T - GASKET_GAP)) < 0.08
        allok &= good
        print(f"  {g:16s} {GASKET_T:.1f} free -> compressed by: {', '.join(res)} "
              f"({100 * (GASKET_T - GASKET_GAP) / GASKET_T:.0f} %) -> {ok(good)}")
    print("-- components vs enclosure")
    encl = {k: v for k, v in parts.items()}
    cok = True
    for c, cm in comps.items():
        hits = []
        for p, pm in encl.items():
            if (c, p) in gpairs or (p, c) in gpairs or not bbox_hit(bb[c], bb[p]):
                continue
            ov = vol(cm ^ pm)
            if ov > 1e-2:
                hits.append(f"{p} {ov:.2f}")
        cok &= not hits
        gap = min((cm.min_gap(pm, 3.0) for p, pm in encl.items() if bbox_hit(bb[c], bb[p], 3.0)
                   and not ((c, p) in gpairs or (p, c) in gpairs)), default=3.0)
        print(f"  {c:14s} clear (min gap {gap:4.2f})" + (f"  HITS {hits} -> FAIL" if hits else ""))
    print(f"  components placed without collisions -> {ok(cok)}")
    allok &= cok
    print("-- cable path (6 mm probe through every enclosure part)")
    pa = [(POD_X, YC, 40.0), (POD_X, YC, 8.5), (0.0, YC, 8.5), (0.0, YC, ZC - 50)]
    a, b = bore_axis()
    d = (b - a) / np.linalg.norm(b - a)
    pb = [(XB, YC, 8.5), tuple(a), tuple(b + 3 * d)]
    pok = True
    for label, path in (("R503 pod->ball", pa), ("4-core ball->wall", pb)):
        probe = union(m3d.Manifold.batch_hull([m3d.Manifold.sphere(2.9, 24).translate(p),
                                               m3d.Manifold.sphere(2.9, 24).translate(q)])
                      for p, q in zip(path, path[1:]))
        hit = sum(vol(probe ^ pm) for pm in encl.values())
        pok &= hit < 1e-2
        print(f"  {label:18s} probe overlap {hit:.3f} mm3 -> {ok(hit < 1e-2)}")
    secs = {"arm channel": channel_cs().area(), "arm floor/bracket bore": math.pi * BORE_R ** 2,
            "boss bore": math.pi * 11.0 ** 2, "neck bore": math.pi * 8.0 ** 2,
            "ball bottom hole": teardrop_cs(7.0).area()}
    mn = min(secs, key=secs.get)
    print("  sections mm2: " + ", ".join(f"{k} {v:.0f}" for k, v in secs.items()))
    print(f"  min cable cross-section {secs[mn]:.0f} mm2 ({mn}) -> {ok(pok)}")
    allok &= pok
    return allok


UP = {
    "ball_front": ((0, -1, 0), "face down"), "ball_rear": ((0, 1, 0), "rear opening down"),
    "rear_hatch": ((0, 1, 0), "back down"), "face_carrier": ((0, 1, 0), "back down"),
    "electronics_tray": ((0, 0, 1), "plate down"), "halo_ring": ((0, 1, 0), "shoulder down"),
    "face_disc": ((0, 1, 0), "back down"), "face_disc_blank": ((0, 1, 0), "back down"),
    "mickey_inlay": ((0, -1, 0), "front down"), "neck": ((0, 0, 1), "base down"),
    "arm_base": ((0, 0, 1), "base down"), "pod_cap": (tuple(-POD_N), "top face down"),
    "wall_bracket": ((0, 1, 0), "wall side down"), "controller_box": ((0, 0, 1), "floor down"),
    "controller_lid": ((0, 0, -1), "top down"),
    "face_gasket": ((0, 1, 0), "flat"), "seam_gasket": ((0, 1, 0), "flat"),
    "hatch_gasket": ((0, 1, 0), "flat"), "neck_gasket": ((0, 0, 1), "flat"),
    "neck_base_gasket": ((0, 0, 1), "flat"), "pod_gasket": (tuple(POD_N), "flat"),
    "r503_washer": (tuple(POD_N), "flat"), "bracket_gasket": ((0, 1, 0), "flat"),
}
MATERIAL = {
    "ball_front": "ASA", "ball_rear": "ASA", "rear_hatch": "ASA", "face_carrier": "ASA white",
    "electronics_tray": "ASA", "halo_ring": "transl. PETG/ASA", "face_disc": "ASA black",
    "face_disc_blank": "ASA black", "mickey_inlay": "transl. PETG/ASA", "neck": "ASA",
    "arm_base": "ASA", "pod_cap": "ASA", "wall_bracket": "ASA", "controller_box": "PETG",
    "controller_lid": "PETG",
}


def orient(m, up):
    r = rot_to_z(up)
    return m.transform(np.hstack([r, np.zeros((3, 1))]))


def meta(name):
    """colour, opacity, explode offset (mm at 100 %), group."""
    lift = (0, 0, 110)
    by = {
        "ball_front": ("#c3c8ce", 1.0, (0, 110, 0)), "seam_gasket": ("#222222", 1.0, (0, 70, 0)),
        "ball_rear": ("#b8bdc3", 1.0, (0, 0, 0)), "rear_hatch": ("#9fa5ab", 1.0, (0, -110, 0)),
        "hatch_gasket": ("#222222", 1.0, (0, -70, 0)), "face_carrier": ("#f4f4f2", 1.0, (0, 150, 0)),
        "electronics_tray": ("#e2e2dc", 1.0, (0, -60, -40)), "halo_ring": ("#e9f6ff", 0.8, (0, 220, 0)),
        "face_gasket": ("#222222", 1.0, (0, 190, 0)), "face_disc": ("#18191b", 1.0, (0, 260, 0)),
        "mickey_inlay": ("#f6f7f2", 0.92, (0, 300, 0)), "neck": ("#4a4f55", 1.0, (0, 0, 55)),
        "neck_gasket": ("#222222", 1.0, (0, 0, 80)), "neck_base_gasket": ("#222222", 1.0, (0, 0, 25)),
        "arm_base": ("#4a4f55", 1.0, (0, 0, 0)), "pod_cap": ("#5a6066", 1.0, tuple(POD_N * 90)),
        "pod_gasket": ("#222222", 1.0, tuple(POD_N * 45)), "r503_washer": ("#222222", 1.0, tuple(POD_N * 60)),
        "wall_bracket": ("#4a4f55", 1.0, (0, 0, -90)), "bracket_gasket": ("#222222", 1.0, (0, -20, -90)),
        "controller_box": ("#3d6fa8", 1.0, (0, 0, 0)), "controller_lid": ("#5b8bc4", 0.9, (0, -70, 0)),
        "pn532": ("#c0392b", 1.0, (0, 175, 0)), "speaker": ("#333333", 1.0, (0, 130, 0)),
        "led_strip": ("#f0f0f0", 1.0, (0, 165, 0)), "tamper_switch": ("#222222", 1.0, (0, -40, 0)),
        "r503": ("#202020", 1.0, tuple(POD_N * 130)),
        "wall": ("#d9d4c7", 0.55, (0, 0, 0)), "magicband": ("#2c7be5", 0.45, (0, 120, 0)),
    }
    for b in BOARDS:
        by[b] = ("#1f6f43", 1.0, (0, -60, -40))
    for b in CB_BOARDS:
        by[b] = ("#1f6f43", 1.0, (0, 0, 0))
    c, o, e = by[name]
    ball = name in ("ball_front", "seam_gasket", "ball_rear", "rear_hatch", "hatch_gasket", "face_carrier",
                    "electronics_tray", "halo_ring", "face_gasket", "face_disc", "mickey_inlay", "pn532",
                    "speaker", "led_strip", "tamper_switch", "neck_gasket") or name in BOARDS
    if ball:
        e = tuple(np.add(e, lift))
    group = "context" if name in ("wall", "magicband") else \
        "gasket" if "gasket" in name or name == "r503_washer" else \
        "component" if name in BOARDS or name in CB_BOARDS or name in (
            "pn532", "speaker", "led_strip", "tamper_switch", "r503") else "part"
    return c, o, [round(float(v), 1) for v in e], group


def export(parts, singles):
    import trimesh  # noqa: F401
    print("-- STL export (print orientation)")
    os.makedirs(os.path.join(OUT, "stl"), exist_ok=True)
    os.makedirs(os.path.join(OUT, "preview"), exist_ok=True)
    allok = True
    for name, m in singles.items():
        up, how = UP[name]
        bodies = len(m.decompose())
        tm = to_trimesh(orient(m, up))
        tm.apply_translation(-np.array([tm.bounds[0][0] + tm.extents[0] / 2,
                                        tm.bounds[0][1] + tm.extents[1] / 2, tm.bounds[0][2]]))
        tm.export(os.path.join(OUT, "stl", f"{name}.stl"))
        side, ang = bed_fit(tm)
        fits = side <= BED - 2 * BED_MARGIN and tm.extents[2] <= BED - BED_MARGIN
        oh = overhang_area(tm)
        good = fits and tm.is_watertight and bodies == 1 and oh < 1.0
        allok &= good
        mat = MATERIAL.get(name, "TPU 95A")
        print(f"  {name:17s} {mat:16s} {how:17s} size {np.round(tm.extents, 1)} fp {side:5.1f}@{ang:2d}  "
              f"{tm.volume / 1000:6.1f} cm3 bodies {bodies} watertight {tm.is_watertight} "
              f"overhang {oh:5.1f} mm2 -> {ok(good)}")
    entries = []
    objs = dict(parts)
    objs.update(components())
    objs.update(context())
    for name, m in objs.items():
        to_trimesh(m).export(os.path.join(OUT, "preview", f"{name}.stl"))
        c, o, e, g = meta(name)
        entries.append({"name": name, "file": f"preview/{name}.stl", "color": c, "opacity": o,
                        "explode": e, "group": g,
                        "glow": name in ("halo_ring", "mickey_inlay", "led_strip")})
    with open(os.path.join(OUT, "preview", "manifest.json"), "w") as fh:
        json.dump({"title": "MagicBand reader: 150 mm ball on neck + arm + fingerprint pod, wall mount",
                   "ball": [0, YC, ZC], "pod": [POD_X, YC, Z_POD], "face_y": YC + FACE_Y,
                   "parts": entries}, fh, indent=1)
    print(f"  all parts single body + watertight + fit + overhang ~0 -> {ok(allok)}")
    return allok


def main():
    parts, singles = build()
    a = report(parts)
    b = export(parts, singles)
    print(f"== ALL CHECKS {ok(a and b)}")


if __name__ == "__main__":
    main()
