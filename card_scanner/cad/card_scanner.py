"""Automated bulk trading-card scanner + penny-sleever + 3-bin sorter.
PETG on a Bambu P1S (256 x 256 x 256), every printed part fits the bed.

Card path (face up, long edge along +x, cards slide on the track plane
z = Z_TRACK):

  HOPPER (250 cards, NEMA17 + T8 elevator, top feed; pick carriage with a
  20 mm suction cup slides the top card +x, air-puff nozzle in the front wall,
  stack-top IR + double-feed slot sensor)
    -> FEED nip (O-ring rollers, 8 mm shafts, 608 bearings, NEMA17 'feed'
       drives every lower roller shaft over one GT2 loop)
    -> SCAN station (card on 2 mm AR glass, 2nd glass 1 mm above, stub-axle
       O-ring nips beside the glass, scan_stop flag + microswitch, CM3 above
       and below at WD, LED frames with diffuser + polarizer slots, light-tight
       hood + lower shroud)
    -> XFER nip -> SLEEVE station (vacuum platen, sleeve magazine on the +y
       side with N20 pick wheels, MG90S lift cup, duck-bill tongues on a
       NEMA17/GT2 carriage, mouth air-jet, MG90S crank-slider pusher with a
       gravity flap that seats the card and ejects the sleeved card)
    -> EXIT nip -> DIVERTER (MG90S fan flap) -> 3 gravity BINS.

World frame: x = card travel, y = across (+y = magazine side), z up.
z = 0 is the top of the 2020 base frame; deck rails (2020 along x, y = +-60)
have their top at Z_DECK.  The sleeve station is modelled in its own frame
S (origin = sleeve mouth centre on the platen top) and moved by to_sleeve().
The SLEEVE station sits on its own SLEEVE_DECK so it also stands alone as the
PHASE-1 TEST RIG (deck on rig feet + manual push slot): stl/rig/.

Run: PYTHONPATH=../../.pydeps python3 card_scanner.py
Outputs stl/ (print orientation), stl/rig/ (phase-1 set), preview/
(assembled + hardware stand-ins + manifest.json).
"""
import json
import math
import os
import shutil

import numpy as np
import manifold3d as m3d

OUT = os.path.dirname(os.path.abspath(__file__))
SEG = 64

# ---- card size switch ------------------------------------------------------
CARD = "standard"      # "standard" (MTG / Pokemon) or "small" (Yu-Gi-Oh)
CARDS = {              # card w x l, penny sleeve w x l (open end = short side)
    "standard": dict(w=63.0, l=88.0, sw=66.7, sl=92.1),   # Ultra Pro penny: 2-5/8 x 3-5/8 in
    "small": dict(w=59.0, l=86.0, sw=62.0, sl=89.0),
}
CW, CL, SW, SL = (CARDS[CARD][k] for k in ("w", "l", "sw", "sl"))
W_MAX, L_MAX = 63.0, 88.0          # fixed geometry is sized for the larger card
W_MIN, L_MIN = 59.0, 86.0
SW_MAX, SL_MAX = 66.7, 92.1
CARD_T = 0.30
PLY = 0.045            # penny sleeve ply (Ultra Pro: 45 um front and back)
GUIDE_CLR = 0.75       # card -> side guide, per side

# ---- printer / checks ------------------------------------------------------
BED = 256.0
BED_MARGIN = 3.0
OVERHANG = 45.0

# ---- frame -----------------------------------------------------------------
EXT = 20.0             # 2020 extrusion
Z_DECK = 85.0          # deck rail top
RAIL_Y = 60.0          # deck rail centre |y|
Z_TRACK = 125.0        # card bottom on the transport track
FOOT_H = 40.0          # printed feet under the base frame
INSERT_R = 2.0         # M3 heat-set insert hole
M3 = 1.7               # M3 clearance radius
M5 = 2.75              # M5 clearance radius (2020 T-nut)

# ---- rollers ---------------------------------------------------------------
R_HUB = 13.0           # printed hub D26, 2 mm O-ring cord in a 1 mm groove
R_ROLL = 14.0          # effective roller radius
HUB_W = 8.0
B608 = (11.0, 7.0)     # 608 bearing r, width
SHAFT_R = 4.0
BLOCK_Y = (53.0, 67.0)  # roller block |y| (sits on the deck rail)
FLOAT = 1.5            # upper bearing float (spring loaded pinch)
WHEEL_Y = 22.0         # wheel centre |y| on cross shafts
STUB_Y = 26.0          # wheel centre |y| on stub axles (scan + sleeve entry)

# ---- stations along the card path (world x of nip lines) ---------------------
X_HOP = 0.0            # hopper stack centre
X_FEED = 66.0          # feed nip
X_SCAN_IN = 146.0      # scan entry nip (stub axles)
X_SCAN_OUT = 228.0     # scan exit nip (stub axles)
X_STOP = 244.0         # card leading edge at the scan_stop flag
X_SCAN = X_STOP - L_MAX / 2   # camera axis (card centre, standard card)
X_XFER = 308.0         # transfer nip
X_ENTRY = 388.0        # sleeve entry nip
ENTRY_S = -18.0        # entry nip in the sleeve frame (mouth = 0)
X_MOUTH = X_ENTRY - ENTRY_S
EXIT_S = 120.0         # exit nip in the sleeve frame
X_EXIT = X_MOUTH + EXIT_S
X_DIV = X_EXIT + 50.0  # diverter pivot

# ---- hopper ----------------------------------------------------------------
STACK_H = 80.0         # 250 cards
HOP_TOP = Z_TRACK - 1.0          # walls stop 1 mm under the track plane
STACK_TOP = Z_TRACK - 3.0        # stack top after the elevator drops 3 mm
PLAT_LO = STACK_TOP - STACK_H    # platform top with a full stack
WALL_T = 4.0
HOP_IN_X = L_MAX / 2 + 1.0       # back / front wall inner faces
ELEV_X = -70.0                   # elevator leadscrew + rods
ROD_Y = 27.0
PICK_Z = Z_TRACK + 44.0          # pick rods
PICK_X0 = -15.0                  # cup x at pick start
PICK_STROKE = 30.0

# ---- scan station -----------------------------------------------------------
CM3_HFOV, CM3_VFOV = 66.0, 41.0
CM3_MIN_FOCUS = 100.0  # CM3 standard: 10 cm .. inf
FIELD = (SL_MAX, SW_MAX)          # field to frame: 91 (along x) x 66 (along y)
WD_H = FIELD[0] / 2 / math.tan(math.radians(CM3_HFOV / 2))
WD_V = FIELD[1] / 2 / math.tan(math.radians(CM3_VFOV / 2))
WD = max(WD_H, WD_V, CM3_MIN_FOCUS)          # card -> lens front
GLASS_T = 2.0
GLASS_GAP = 1.0        # lower glass top -> upper glass bottom
GLASS_W = 44.0         # between the stub-axle wheels (y +-24 .. 28)
GLASS_LO = (X_SCAN_IN - 18.0, X_STOP + 2.0)  # lower glass x0, x1
GLASS_HI = (X_SCAN_IN - 20.0, X_STOP - 3.0)  # upper glass (bonded under the two arches)
LED_H = 45.0           # LED frame distance from the card
Z_LENS_TOP = Z_TRACK + CARD_T + WD
Z_LENS_BOT = Z_TRACK - WD
HOOD_X = (X_SCAN_IN - 31.0, X_SCAN_OUT + 33.0)
HOOD_Y = 75.0
SHROUD_X = 54.0        # lower shroud half x (inner), between the rails
SHROUD_Y = 44.0

# ---- sleeve station (frame S: mouth centre, platen top = 0) ------------------
TONGUE_T = 0.3         # stainless shim
TONGUE_CLR = 1.5       # card -> tongue, per side (vertical), and throat sides
Z_SHIM_LO = PLY        # lower shim bottom (lies on the bottom ply)
Z_CARD_S = Z_SHIM_LO + TONGUE_T + TONGUE_CLR       # card bottom in the throat
Z_SHIM_HI = Z_CARD_S + CARD_T + TONGUE_CLR          # upper shim bottom
Z_PLATEN = Z_TRACK - Z_CARD_S                       # platen top (world)
LIFT = 5.5             # top ply lift at the cup: mouth edge >= 4.4 after the 1.1 mm cantilever sag to x 0
SHIM_W = 40.0          # tongue width (between the entry wheels +-24)
SHIM_FORK = 8.0        # centre slot in the upper shim for the pusher post
SHIM_OUT = 30.0        # shim length protruding from the clamp
TIP_RET, TIP_IN = -3.0, 15.0     # tongue tip x: retracted / inserted
TONGUE_POS = TIP_IN    # pose shown in the assembly
CLAMP_L = 12.0
ROD_TY = 40.0          # tongue carriage rods |y|
ROD_TZ = 0.0
PLATEN_X = (-2.0, 84.0)
PLATEN_Y = SW_MAX / 2 + 2.0
DECK_X = (-58.0, 146.0)
DECK_Y = (-105.0, 115.0)
DECK_T = 5.0
Z_DECK_S = Z_DECK + DECK_T - Z_PLATEN               # sleeve deck top in S
MAG_Y0 = SW_MAX / 2 + 0.5        # gate plate inner face (+y)
MAG_Y1 = MAG_Y0 + 3.0 + SW_MAX + 4.0                # rear wall inner face
MAG_H = 25.0
GATE_GAP = 0.14        # 1.5 x one sleeve (0.09): one passes, two (0.18) do not; set with a feeler gauge
CUP_X = 22.0           # lift cup x (S): tongue tips +15 + cup R5 + 2 margin; on a finger off the arm plate (x 41..44)
LIFT_SERVO = (28.0, -60.0, 14.0)  # lift servo shaft (S): along x
PUSH_START = ENTRY_S - 2.0        # pusher flap start x (behind the trailing edge)
PUSH_STROKE = 56.0                # seat (to +1.5) + eject into the exit nip
PUSH_Z = 26.0                     # pusher guide bar centre (S)
FLAP_TIP = 1.55                   # pusher pawl tip at rest (on the lower keeper, under the card edge)
RIG_FOOT = 60.0                   # phase-1 rig feet (NEMA17 under the deck)

# ---- diverter + bins ----------------------------------------------------------
DIV_L = 70.0
DIV_ANG = (-30.0, 0.0, 30.0)
BIN_R = 165.0          # bin centre radius from the diverter pivot
BIN_IN = (97.0, 71.0, 60.0)   # inner l x w x depth (100 sleeved cards ~ 45 mm)
BIN_TOP = Z_PLATEN - 22.0

# ---- electronics bay (plates on the base frame, -y side) ----------------------
ELEC_Y = (-245.0, -95.0)
ELEC_A_X = (0.0, 240.0)
ELEC_B_X = (250.0, 490.0)
BOARDS_A = {           # x0, y0 (plate local), l, w, h  + mounting holes
    "pi5": (8.0, 8.0, 85.0, 56.0, 26.0, [(3.5, 3.5), (61.5, 3.5), (3.5, 52.5), (61.5, 52.5)]),
    "esp32s3": (110.0, 8.0, 69.0, 28.0, 14.0, []),
    "tmc_carrier": (8.0, 78.0, 100.0, 62.0, 22.0, [(4, 4), (96, 4), (4, 58), (96, 58)]),
    "buck_5v": (125.0, 60.0, 65.0, 40.0, 22.0, [(4, 4), (61, 36)]),
    "mcp23017_out": (194.0, 18.0, 38.0, 22.0, 12.0, []),    # 0x20: pneumatics MOSFET gates
    "mcp23017_in": (194.0, 47.0, 38.0, 22.0, 12.0, []),     # 0x21: endstops, lid, magazine, stack/exit IR
    "drv8833": (196.0, 76.0, 22.0, 18.0, 10.0, []),          # sleeve_pick N20
    "relay_k1": (112.0, 106.0, 26.0, 30.0, 28.0, []),        # 24 V safety relay (e-stop NC1 + lid NC in the coil)
}
BOARDS_B = {
    "psu_24v": (6.0, 6.0, 159.0, 97.0, 30.0, [(20, 20), (139, 20), (20, 77), (139, 77)]),   # LRS-150-24
    "vac_pump": (168.0, 4.0, 70.0, 40.0, 30.0, []),
    "air_pump": (168.0, 48.0, 55.0, 27.0, 27.0, []),
    "valve_pick_cup": (8.0, 112.0, 30.0, 22.0, 32.0, []),
    "valve_platen": (48.0, 112.0, 30.0, 22.0, 32.0, []),
    "valve_lift_cup": (88.0, 112.0, 30.0, 22.0, 32.0, []),
    "valve_stack_puff": (128.0, 112.0, 30.0, 22.0, 32.0, []),   # air pump -> hopper puff
    "valve_mouth_jet": (168.0, 112.0, 30.0, 22.0, 32.0, []),    # air pump -> sleeve mouth jet
    "vac_manifold": (225.0, 48.0, 14.0, 40.0, 12.0, [(7, 5), (7, 35)]),   # pump -> 3 cup valves + sensor
    "vac_sensor": (168.0, 80.0, 22.0, 18.0, 12.0, [(3, 3), (19, 15)]),    # XGZP6847A, teed into the manifold
}
ELEC_T = 4.0

# ---- switches + sensors added for the firmware (config.h MCPI_*, PIN_ESTOP) --------
ESW_X = (-80.0, -60.0)            # elev_home / elev_limit KW11 bodies (20 x 6.4 x 10) on the switch post
ESW_Y = (43.6, 50.0)
ESW_HOME_Z = (27.0, 37.0)         # lever top 37.5: platform tab (z 38..42 at full stack) trips it 0.5 lower
ESW_LIMIT_Z = (123.5, 133.5)      # lever bottom 123: tab top 1 mm above the empty-stack position (122)
PLAT_TAB = (-74.0, -66.0, 48.0)   # platform trip tab x0, x1, y1
TSW = (-63.0, -56.6, 42.0, 54.8, 5.0, 10.8)   # tongue_home KW-mini (S) on tongue_rod_block_sw
SLEEVE_SENSOR = (30.0, -30.0)     # sleeve_present TCRT5000 under the platen (S): covered only near the fence
MAG_SENS_X = SL_MAX + 3.6         # magazine sensor plate inner face (S), 0.1 off the end wall
MAG_SENS = {"mag_empty": (81.0, 2.8), "mag_low": (95.0, 6.5)}   # TCRT5000 optic centre y, z (S)
LID_SW = (335.0, 365.0, 155.0, 171.0, 4.5, 54.5)   # lid interlock (D4NS class) body on the +y base rail
ESTOP = (-40.0, 38.0)             # 22 mm e-stop x, z on the -y panel

# ---- helpers ---------------------------------------------------------------
def box(x0, x1, y0, y1, z0, z1):
    return m3d.Manifold.cube((x1 - x0, y1 - y0, z1 - z0)).translate((x0, y0, z0))


def cbox(cx, cy, cz, lx, ly, lz):
    return box(cx - lx / 2, cx + lx / 2, cy - ly / 2, cy + ly / 2, cz - lz / 2, cz + lz / 2)


def union(parts):
    parts = [p for p in parts if not p.is_empty()]
    return m3d.Manifold.batch_boolean(parts, m3d.OpType.Add)


def clean(m):
    """Drop zero-volume sliver components left by coplanar booleans."""
    return m3d.Manifold.compose([c for c in m.decompose() if c.volume() > 1.0])


def xform(m, rows):
    return m.transform(np.array(rows, dtype=float))


def zcyl(r, z0, z1, x=0.0, y=0.0, seg=SEG):
    return m3d.Manifold.cylinder(z1 - z0, r, r, seg).translate((x, y, z0))


def ycyl(r, y0, y1, x=0.0, z=0.0, seg=SEG):
    m = m3d.Manifold.cylinder(y1 - y0, r, r, seg)
    return xform(m, [[1, 0, 0, x], [0, 0, 1, y0], [0, -1, 0, z]])


def xcyl(r, x0, x1, y=0.0, z=0.0, seg=SEG):
    m = m3d.Manifold.cylinder(x1 - x0, r, r, seg)
    return xform(m, [[0, 0, 1, x0], [0, 1, 0, y], [-1, 0, 0, z]])


def hull(ms):
    return m3d.Manifold.batch_hull(list(ms))


def zslot(x0, y0, x1, y1, r, z0, z1):
    """Stadium hole along z from (x0, y0) to (x1, y1)."""
    return hull([zcyl(r, z0, z1, x0, y0, 32), zcyl(r, z0, z1, x1, y1, 32)])


def tear_y(r, x, z, y0, y1):
    """Hole along y with a 45 deg roof toward +z (prints without support)."""
    c = ycyl(r, y0, y1, x, z, 32)
    t = r * math.sqrt(2.0)
    roof = xform(box(-r / math.sqrt(2), r / math.sqrt(2), y0, y1, -r / math.sqrt(2), r / math.sqrt(2)),
                 [[0.7071, 0, -0.7071, 0], [0, 1, 0, 0], [0.7071, 0, 0.7071, 0]])
    return c + roof.translate((x, 0, z)) - box(x - r - 1, x + r + 1, y0 - 1, y1 + 1, z + t, z + 2 * t)


def tear_x(r, y, z, x0, x1):
    c = xcyl(r, x0, x1, y, z, 32)
    roof = xform(box(x0, x1, -r / math.sqrt(2), r / math.sqrt(2), -r / math.sqrt(2), r / math.sqrt(2)),
                 [[1, 0, 0, 0], [0, 0.7071, -0.7071, 0], [0, 0.7071, 0.7071, 0]])
    return c + roof.translate((0, y, z)) - box(x0 - 1, x1 + 1, y - r - 1, y + r + 1, z + r * 1.4143, z + 3 * r)


def rot_to_z(u):
    u = np.asarray(u, float) / np.linalg.norm(u)
    z = np.array([0.0, 0.0, 1.0])
    c = float(u @ z)
    if c < -1 + 1e-9:
        return np.diag([1.0, -1.0, -1.0])
    v = np.cross(u, z)
    vx = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    return np.eye(3) + vx + vx @ vx / (1 + c)


def cyl_between(p0, p1, r, seg=32):
    p0, p1 = np.asarray(p0, float), np.asarray(p1, float)
    d = p1 - p0
    rot = rot_to_z(d).T
    m = m3d.Manifold.cylinder(float(np.linalg.norm(d)), r, r, seg)
    return m.transform(np.hstack([rot, p0[:, None]]))


def rotz(m, deg, cx=0.0, cy=0.0):
    return m.translate((-cx, -cy, 0)).rotate((0, 0, deg)).translate((cx, cy, 0))


def mirror_y(m):
    return m.mirror((0, 1, 0))


def to_sleeve(m):
    """Sleeve frame S -> world."""
    return m.translate((X_MOUTH, 0.0, Z_PLATEN))


def m3_insert(x, y, z0, z1):
    return zcyl(INSERT_R, z0, z1, x, y, 24)


def m3_hole(x, y, z0, z1):
    return zcyl(M3, z0, z1, x, y, 24)


def nema17_holes(cx, cy, z0, z1):
    """NEMA17 face pattern along z: 22 mm boss + 4 x M3 on 31 mm."""
    hs = [zcyl(11.5, z0, z1, cx, cy, 48)]
    hs += [m3_hole(cx + sx * 15.5, cy + sy * 15.5, z0, z1) for sx in (-1, 1) for sy in (-1, 1)]
    return union(hs)


# ---- 1. hopper ---------------------------------------------------------------
GUIDE_IN = CW / 2 + GUIDE_CLR                    # side guide inner face |y|
GUIDE_INSERT_Y = (W_MAX + W_MIN) / 4 + GUIDE_CLR + 12.0   # fixed insert |y| (both sizes)
HOP_BASE_X = (-112.0, 64.0)
HOP_BASE_Y = 70.0
HOP_M5 = [(-104.0, -62.0), (-104.0, 62.0), (42.0, -62.0), (42.0, 62.0)]
LEG_Y = (-66.0, -60.0)                           # pick bridge leg


def make_hopper_base():
    b = box(*HOP_BASE_X, -HOP_BASE_Y, HOP_BASE_Y, 0, 6)
    b += union(zcyl(7.0, 6, 14, ELEV_X, s * ROD_Y, 48) for s in (-1, 1))
    holes = [nema17_holes(ELEV_X, 0.0, -1, 7)]
    holes += [zcyl(4.05, 3, 15, ELEV_X, s * ROD_Y, 32) for s in (-1, 1)]          # 8 mm rods
    holes += [m3_insert(x, s * GUIDE_INSERT_Y, 1, 7) for x in (-30.0, 30.0) for s in (-1, 1)]
    holes += [m3_insert(-56.0, s * 30.0, 1, 7) for s in (-1, 1)]                  # back wall
    holes += [m3_insert(55.5, s * 30.0, 1, 7) for s in (-1, 1)]                   # front wall
    holes += [m3_insert(x, -63.0, 1, 7) for x in (-80.0, -30.0, 20.0)]            # pick bridge leg
    holes += [m3_insert(x, 61.0, 1, 7) for x in (-76.0, -64.0)]                   # elev switch post
    holes += [zcyl(M5, -1, 7, x, y, 24) for x, y in HOP_M5]
    return b - union(holes)


def make_hopper_guide(side=1):
    """Side guide, slotted foot -> adjustable for 59 / 63 mm cards."""
    g = GUIDE_IN
    w = box(-42, 42, g, g + WALL_T, 6, HOP_TOP)
    w += box(-42, 42, g, g + 20, 6, 10)
    w += union(box(x - 2, x + 2, g + WALL_T, g + 14, 10, 40) for x in (-15.0, 15.0))
    w -= union(zslot(x, g + 10, x, g + 14, M3, 5, 11) for x in (-30.0, 30.0))
    return w if side > 0 else mirror_y(w)


def make_hopper_back():
    x0, x1 = -HOP_IN_X - 6.0, -HOP_IN_X
    w = box(x0, x1, -40, 40, 6, HOP_TOP)
    w += box(-60, x0, -40, 40, 6, 10)                                            # foot
    w += box(-86, x1, -40, 40, HOP_TOP, HOP_TOP + 8)                             # rod yoke
    w -= box(x0 - 1, x1 + 1, -12, 12, 30, HOP_TOP + 0.01)                        # platform arm slot
    w -= union(zcyl(4.05, HOP_TOP - 1, HOP_TOP + 9, ELEV_X, s * ROD_Y, 32) for s in (-1, 1))
    w -= zcyl(6.0, HOP_TOP - 1, HOP_TOP + 9, ELEV_X, 0.0, 32)                    # T8 clearance
    w -= union(m3_hole(-56.0, s * 30.0, 5, 11) for s in (-1, 1))
    return w


PUFF_Z = STACK_TOP - 0.5


def make_hopper_front():
    x0, x1 = HOP_IN_X, HOP_IN_X + 6.0
    w = box(x0, x1, -40, 40, 6, HOP_TOP)
    w += box(x1, 60, -40, 40, 6, 10)
    w += xcyl(3.0, x1 - 0.5, x1 + 9, 0.0, PUFF_Z - 1.0, 32)                      # 4 mm hose barb
    w += xcyl(2.4, x1 + 3, x1 + 9, 0.0, PUFF_Z - 1.0, 32).scale((1, 1, 1))
    w += box(x1 - 0.5, x1 + 3, -5, 5, PUFF_Z - 6, PUFF_Z + 1)
    # double-feed sensor ear: slot interrupter (TCST2103-class) + thickness lever pivot
    ear = box(x1 - 0.5, x1 + 10, 34, 50, Z_TRACK - 13, Z_TRACK + 15)
    ear += box(x1 - 0.5, x1 + 2, 34, 50, Z_TRACK - 30, Z_TRACK - 13)
    ear -= box(x1 + 3, x1 + 9.5, 36, 47, Z_TRACK + 3, Z_TRACK + 16)              # sensor pocket 6.3 x 11
    ear -= tear_y(0.9, x1 + 6.2, Z_TRACK + 6.0, 33, 51)                          # lever pivot (D1.8 pin)
    w += ear
    w -= xcyl(0.75, x0 - 1, x1 + 10, 0.0, PUFF_Z, 24)                            # puff nozzle
    w -= cyl_between((x1 + 2, 0, PUFF_Z - 1), (x1 + 10, 0, PUFF_Z - 1), 1.25)
    w -= cyl_between((x1 - 1, 0, PUFF_Z), (x1 + 3, 0, PUFF_Z - 1), 0.75, 24)
    w -= union(m3_hole(55.5, s * 30.0, 5, 11) for s in (-1, 1))
    return w


def make_platform(top=PLAT_LO):
    p = box(-41, 41, -28, 28, top - 4, top)
    p += box(-56, -40, -10, 10, top - 8, top)
    p += box(-86, -55, -37, 37, top - 24, top)
    p -= union(zcyl(7.6, top - 25, top + 1, ELEV_X, s * ROD_Y, 48) for s in (-1, 1))   # LM8UU
    p -= zcyl(5.25, top - 25, top + 1, ELEV_X, 0.0, 32)                                 # T8 nut
    p -= union(m3_hole(ELEV_X + 8 * math.cos(a), 8 * math.sin(a), top - 25, top + 1)
               for a in np.radians([45, 135, 225, 315]))
    p += box(PLAT_TAB[0], PLAT_TAB[1], 36.99, PLAT_TAB[2], top - 4, top)              # elev_home / limit trip tab
    p -= union(zcyl(1.5, top - 5, top + 1, x, y, 16) for x in (-25, 0, 25) for y in (-15, 15))
    return p


def make_pick_bridge():
    zb = PICK_Z + 18.0
    b = box(-98, 50, LEG_Y[0], 24, zb, zb + 6)                                     # beam
    b += box(-98, 30, *LEG_Y, 6, zb + 6)                                           # leg
    b += box(-90, 30, -70, -56, 6, 10)                                             # leg foot
    b += union(box(x0, x1, -24, 24, PICK_Z - 7, zb + 0.5) for x0, x1 in ((-50, -38), (38, 50)))
    b += union(box(x - 2, x + 2, LEG_Y[0], LEG_Y[1], 10, 60) for x in (-60.0, 0.0))  # leg ribs
    # stack-top IR sensor (TCRT5000 head 10.2 x 5.8) hanging behind the pick carriage
    b += box(-41, -31, -30, -12, Z_TRACK + 8, zb + 0.5)
    b -= box(-39.1, -32.9, -26.1, -15.9, Z_TRACK + 7, Z_TRACK + 15)
    b -= box(-37, -35, -24, -18, Z_TRACK + 14, zb + 7)                              # wire hole
    b -= union(xcyl(3.05, -51, 51, s * 16.0, PICK_Z, 32) for s in (-1, 1))         # 6 mm rods
    b -= union(m3_hole(x, -63.0, 5, 11) for x in (-80.0, -30.0, 20.0))
    # pick NEMA17 on the leg outer face, shaft along +y
    b += box(-101, -59, LEG_Y[0], LEG_Y[1], PICK_Z - 21, PICK_Z + 21)
    b -= ycyl(11.5, LEG_Y[0] - 1, LEG_Y[1] + 1, -80.0, PICK_Z, 48)
    b -= union(ycyl(M3, LEG_Y[0] - 1, LEG_Y[1] + 1, -80.0 + sx * 15.5, PICK_Z + sz * 15.5, 24)
               for sx in (-1, 1) for sz in (-1, 1))
    b -= union(xcyl(1.0, -51, -37, d, PICK_Z, 16) for d in (-3.25, 3.25))         # pick_home KW-mini (M2)
    b -= zcyl(M3, zb - 1, zb + 7, 45.0, -44.0, 24)                                 # GT2 idler bolt
    return b


def make_pick_carriage(x=PICK_X0):
    c = box(x - 12, x + 12, -24, 24, PICK_Z - 8, PICK_Z + 8)
    c += box(x - 6, x + 6, -48, -24, PICK_Z - 4, PICK_Z + 6)                       # belt arm
    c -= union(xcyl(6.1, x - 13, x + 13, s * 16.0, PICK_Z, 48) for s in (-1, 1))  # LM6UU
    c -= zcyl(2.1, PICK_Z - 9, PICK_Z + 9, x, 0.0, 24)                             # M5 cup stem (tap)
    c -= box(x - 7, x + 7, -45.5, -43.0, PICK_Z - 1, PICK_Z + 7)                   # belt slot
    return c


# ---- 2. rollers + track ------------------------------------------------------
def make_roller_block(nx, z_base, z_nip, foot=(-24.0, 24.0), body=15.0):
    """+y roller block at nip x nx: lower 608 fixed, upper 608 floats (spring pinch).
    z_nip = card bottom at the nip."""
    y0, y1 = BLOCK_Y
    z_lo, z_up = z_nip - R_ROLL, z_nip + CARD_T + R_ROLL
    top = z_up + B608[0] + 6.0
    b = box(nx - body, nx + body, y0, y1, z_base, top)
    b += box(nx + foot[0], nx + foot[1], RAIL_Y - 10, RAIL_Y + 10, z_base, z_base + 5)
    b -= ycyl(B608[0] + 0.1, y0 - 1, y0 + B608[1], nx, z_lo)
    b -= ycyl(5.0, y0, y1 + 1, nx, z_lo, 32)
    up = hull([ycyl(B608[0] + 0.1, y0 - 1, y0 + B608[1], nx, z_up + d) for d in (-FLOAT, FLOAT)])
    b -= up
    b -= hull([ycyl(5.0, y0, y1 + 1, nx, z_up + d, 32) for d in (-FLOAT, FLOAT)])
    b -= zcyl(2.6, z_up + FLOAT + B608[0] - 1, top + 1, nx, y0 + 3.5, 24)          # pinch spring
    fx = [nx + foot[0] + 5, nx + foot[1] - 5] if foot[1] - body > 9 else [nx + foot[0] + 5, nx + foot[0] + 15]
    b -= union(zcyl(M5, z_base - 1, z_base + 6, x, RAIL_Y, 24) for x in fx)
    return b


def make_hub():
    """O-ring roller hub: D26 x 8, two 2 mm cord grooves, 8 mm bore + M3 grub."""
    h = zcyl(R_HUB, 0, HUB_W, seg=96)
    for z in (2.0, 6.0):
        h -= zcyl(R_HUB + 1, z - 1.0, z + 1.0) - zcyl(R_HUB - 1.0, z - 1.5, z + 1.5)
    h -= zcyl(4.05, -1, HUB_W + 1, seg=32)
    h -= xcyl(1.3, 0, R_HUB + 1, 0, HUB_W / 2, 24)
    return h


TRACK_INSERT_Y = GUIDE_INSERT_Y


def rail_range(x0, x1, arch):
    """Guide rail x range on a track (kept clear of the glass arches)."""
    if arch and arch[2] == "in":
        return x0, arch[0] - 2.0
    if arch:
        return x1 - 40.0, x1
    return x0, x1


def make_track(x0, x1, legs, glass_in=None, arch=None):
    """Track plate top = Z_TRACK between two nips, legs down to the deck rails.
    glass_in: (gx0, gx1) ledge for the lower glass end.  arch: (ax0, ax1, kind)."""
    t = box(x0, x1, -46, 46, Z_TRACK - 4, Z_TRACK)
    lx0, lx1 = legs
    t += box(lx0, lx1, -RAIL_Y - 10, RAIL_Y + 10, Z_TRACK - 4, Z_TRACK)
    for s in (-1, 1):
        t += box(lx0, lx1, s * RAIL_Y - 10, s * RAIL_Y + 10, Z_DECK, Z_TRACK - 4).translate((0, 0, 0))
    t -= union(zcyl(M5, Z_DECK - 1, Z_DECK + 30, (lx0 + lx1) / 2, s * RAIL_Y, 24) for s in (-1, 1))
    t -= union(box((lx0 + lx1) / 2 - 5, (lx0 + lx1) / 2 + 5, s * RAIL_Y - 5, s * RAIL_Y + 5,
                   Z_DECK + 6, Z_TRACK - 8) for s in (-1, 1))                     # screw access
    rx0, rx1 = rail_range(x0, x1, arch)
    gx = [rx0 + 8, rx1 - 8] if rx1 - rx0 > 30 else [(rx0 + rx1) / 2]
    t -= union(m3_insert(x, s * TRACK_INSERT_Y, Z_TRACK - 4.5, Z_TRACK + 1) for x in gx for s in (-1, 1))
    if glass_in:
        t -= box(glass_in[0] - 0.2, glass_in[1] + 0.2, -GLASS_W / 2 - 0.3, GLASS_W / 2 + 0.3,
                 Z_TRACK - GLASS_T, Z_TRACK + 1)
    if arch:
        ax0, ax1, kind = arch
        zb, zt = Z_TRACK + GLASS_GAP + GLASS_T, Z_TRACK + GLASS_GAP + GLASS_T + 4
        if kind == "in":
            t += box(ax0, ax1, -40, 40, zb, zt)
            t += union(box(ax0, ax1, s * 36 - 2, s * 36 + 2, Z_TRACK - 0.01, zt) for s in (-1, 1))
        else:   # cantilever back over the upper glass end, centre slot for the stop flag
            t += box(x0, x0 + 6, -40, 40, zb, zt)
            t += box(ax0, x0 + 6, -GLASS_W / 2, GLASS_W / 2, zb, zt)
            t += union(box(x0, x0 + 6, s * 36 - 2, s * 36 + 2, Z_TRACK - 0.01, zt) for s in (-1, 1))
            t -= box(ax0 - 1, x0 + 7, -3, 3, zb - 1, zt + 1)
            t -= union(m3_insert(x0 + 3, s * 9.0, zt - 4, zt + 1) for s in (-1, 1))
    return t


def make_guide_rail(x0, x1, side=1):
    """Slotted side guide on a track plate (one print fits 59 + 63 mm)."""
    g = GUIDE_IN
    r = box(x0, x1, g, g + 3, Z_TRACK, Z_TRACK + 3)
    r += box(x0, x1, g, g + 16, Z_TRACK, Z_TRACK + 2)
    gx = [x0 + 8, x1 - 8] if x1 - x0 > 30 else [(x0 + x1) / 2]
    r -= union(zslot(x, g + 9.5, x, g + 13, M3, Z_TRACK - 1, Z_TRACK + 4) for x in gx)
    for xe, d in ((x0, 1), (x1, -1)):                                          # lead-in chamfer
        r -= xform(box(-3, 3, -3, 3, Z_TRACK - 1, Z_TRACK + 4),
                   [[0.7071, -0.7071, 0, xe], [0.7071, 0.7071, 0, g], [0, 0, 1, 0]])
    return r if side > 0 else mirror_y(r)


TRACKS = {   # name: x0, x1, legs, glass, arch
    "track_feed": (X_FEED + 16, X_SCAN_IN - 16, (X_FEED + 25, X_SCAN_IN - 34),
                   (GLASS_LO[0], X_SCAN_IN - 16), (X_SCAN_IN - 22, X_SCAN_IN - 15, "in")),
    "track_scan_out": (X_SCAN_OUT + 16, X_XFER - 16, (X_SCAN_OUT + 36, X_XFER - 25),
                       (X_SCAN_OUT + 16, GLASS_LO[1]), (GLASS_HI[1] - 5, X_SCAN_OUT + 22, "out")),
    "track_xfer": (X_XFER + 16, X_MOUTH - 64, (X_XFER + 25, X_MOUTH - 64), None, None),
}


# ---- 3. scan station ------------------------------------------------------------
HOOD_TOP = Z_LENS_TOP + 3.0      # hood top plate top (cam plate on it)
LED_Z_TOP = Z_TRACK + CARD_T + LED_H      # top LED frame underside
LED_Z_BOT = Z_TRACK - LED_H               # bottom LED frame top face
SHR_Z = (Z_LENS_BOT - 3.0, 95.0)          # lower shroud bottom plate .. flange top
LED_WIN = (42.0, 26.0)                    # LED frame window half x / y (> field at LED_H)
CAM_TUBE = 6.3


def make_hood():
    x0, x1 = HOOD_X
    h = box(x0, x1, -HOOD_Y, HOOD_Y, Z_DECK, HOOD_TOP)
    h -= box(x0 + 3, x1 - 3, -HOOD_Y + 3, HOOD_Y - 3, Z_DECK - 1, HOOD_TOP - 4)
    for xa, xb in ((x0 - 1, x0 + 4), (x1 - 4, x1 + 1)):                       # card / track slits
        h -= box(xa, xb, -50, 50, Z_TRACK - 6, Z_TRACK + 9)
        h -= union(box(xa, xb, s * RAIL_Y - 11, s * RAIL_Y + 11, Z_DECK - 1, Z_DECK + 6) for s in (-1, 1))
    h -= zcyl(13.0, HOOD_TOP - 5, HOOD_TOP + 1, X_SCAN, 0.0, 64)
    for x in (X_SCAN_IN, X_SCAN_OUT):                                          # lower shafts -> pulleys
        h -= union(ycyl(6.0, s * HOOD_Y - 4, s * HOOD_Y + 4, x, Z_TRACK - R_ROLL, 32) for s in (-1, 1))
    h -= union(m3_insert(X_SCAN + sx * 16, sy * 16, HOOD_TOP - 4.5, HOOD_TOP + 1)
               for sx in (-1, 1) for sy in (-1, 1))
    h += union(box(x0 + 2.9, x1 - 2.9, s * (HOOD_Y - 6.1), s * (HOOD_Y - 2.9), LED_Z_TOP - 3, LED_Z_TOP)
               if s > 0 else box(x0 + 2.9, x1 - 2.9, -HOOD_Y + 2.9, -HOOD_Y + 6.1, LED_Z_TOP - 3, LED_Z_TOP)
               for s in (-1, 1))                                               # LED frame ledges
    return h


def led_frame(x0, x1, y0, y1, z0, up):
    """Rect LED frame: window, LED strip channel, diffuser recess, side-loading
    linear-polarizer film slot.  up=False: LEDs face down (top frame)."""
    t = 8.0
    f = box(x0, x1, y0, y1, z0, z0 + t)
    wx, wy = LED_WIN
    f -= box(X_SCAN - wx, X_SCAN + wx, -wy, wy, z0 - 1, z0 + t + 1)

    def ring(a, b, za, zb, open_edge=False):
        r = box(X_SCAN - wx - b, X_SCAN + wx + b, -wy - b, wy + b, za, zb) - \
            box(X_SCAN - wx - a, X_SCAN + wx + a, -wy - a, wy + a, za - 1, zb + 1)
        if open_edge:
            r += box(X_SCAN - wx - b, X_SCAN + wx + b, wy + a, y1 + 1, za, zb)
        return r
    if up:      # face toward +z: film at the top, diffuser, then LED channel
        f -= ring(1.0, 13.0, z0 + t - 0.6, z0 + t + 1, open_edge=True)
        f -= ring(1.0, 13.0, z0 + t - 2.1, z0 + t - 0.6)
        f -= ring(3.0, 11.0, z0 + t - 5.1, z0 + t - 2.1)
        f -= box(X_SCAN + wx + 5, X_SCAN + wx + 9, -2, 2, z0 - 1, z0 + t - 5)     # wire hole
    else:
        f -= ring(1.0, 13.0, z0 - 1, z0 + 0.6, open_edge=True)
        f -= ring(1.0, 13.0, z0 + 0.6, z0 + 2.1)
        f -= ring(3.0, 11.0, z0 + 2.1, z0 + 5.1)
        f -= box(X_SCAN + wx + 5, X_SCAN + wx + 9, -2, 2, z0 + 5, z0 + t + 1)
    return f


def make_led_frame_top():
    x0, x1 = HOOD_X
    return led_frame(x0 + 3.3, x1 - 3.3, -HOOD_Y + 3.3, HOOD_Y - 3.3, LED_Z_TOP, up=False)


def make_led_frame_bot():
    return led_frame(X_SCAN - SHROUD_X + 0.3, X_SCAN + SHROUD_X - 0.3, -SHROUD_Y + 0.3, SHROUD_Y - 0.3,
                     LED_Z_BOT - 8.0, up=True)


def make_lower_shroud():
    z0, z1 = SHR_Z
    sx, sy = SHROUD_X, SHROUD_Y
    s = box(X_SCAN - sx - 3, X_SCAN + sx + 3, -sy - 3, sy + 3, z0, z1)
    s -= box(X_SCAN - sx, X_SCAN + sx, -sy, sy, z0 + 4, z1 + 1)
    s += box(HOOD_X[0] + 4, X_SCAN - sx, -sy - 3, sy + 3, z1 - 3, z1)           # light flange
    s += union(box(X_SCAN - sx, X_SCAN + sx, k * (sy - 2.5), k * sy, LED_Z_BOT - 11, LED_Z_BOT - 8) if k > 0 else
               box(X_SCAN - sx, X_SCAN + sx, -sy, -sy + 2.5, LED_Z_BOT - 11, LED_Z_BOT - 8)
               for k in (-1, 1))                                                # LED frame ledges
    for x in (X_SCAN - 30, X_SCAN + 30):                                       # tabs -> rail side slots
        for k in (-1, 1):
            ya, yb = sorted((k * (sy + 2.9), k * (RAIL_Y - 10)))
            s += box(x - 10, x + 10, ya, yb, Z_DECK - 20, Z_DECK - 1)
            s -= ycyl(M5, ya - 1, yb + 1, x, Z_DECK - 10, 24)
    s -= zcyl(13.0, z0 - 1, z0 + 5, X_SCAN, 0.0, 64)
    s -= union(m3_insert(X_SCAN + a * 16, b * 16, z0 - 1, z0 + 4.5) for a in (-1, 1) for b in (-1, 1))
    s -= box(X_SCAN + sx - 1, X_SCAN + sx + 4, -6, 6, z0 + 6, z0 + 14)           # ribbon slot
    return s


def make_cam_mount():
    """CM3 mount, local frame: plate z 0..3 (board below z = 0), lens tube toward +z
    with a polarizer film pocket at the tube end (in front of the lens)."""
    m = box(-20, 20, -20, 20, 0, 3)
    m += zcyl(12.0, 0, 3 + CAM_TUBE, 0, 0, 64)
    m -= zcyl(6.0, -1, 4 + CAM_TUBE, 0, 0, 48)                                   # lens bore
    m -= zcyl(9.2, 3 + CAM_TUBE - 0.6, 4 + CAM_TUBE, 0, 0, 64)                  # film disc D18
    m -= box(-9.2, 9.2, 0, 13, 3 + CAM_TUBE - 0.6, 3 + CAM_TUBE - 0.0001 + 1)    # side slot
    m -= union(m3_hole(a * 16, b * 16, -1, 4) for a in (-1, 1) for b in (-1, 1))
    m -= union(zcyl(1.1, -1.0, 4.0, a * 10.5, b * 6.25 - 2.25, 16) for a in (-1, 1) for b in (-1, 1))  # M2 + 2 mm spacers
    m -= box(-9, 9, -20.5, -12, -1, 1.0)                                         # ribbon relief
    return m


def cam_top(m):
    return xform(m, [[1, 0, 0, X_SCAN], [0, -1, 0, 0], [0, 0, -1, HOOD_TOP + 3.0]])


def cam_bot(m):
    return m.translate((X_SCAN, 0.0, SHR_Z[0] - 3.0))


STOP_X = TRACKS["track_scan_out"][0]


def make_stop_mount():
    zt = Z_TRACK + GLASS_GAP + GLASS_T + 4
    m = box(STOP_X, STOP_X + 12, -14, 14, zt, zt + 4)
    m += union(box(STOP_X, STOP_X + 4, s * 3.2, s * 3.2 + s * 3.5, zt + 3.9, zt + 14) if s > 0 else
               box(STOP_X, STOP_X + 4, -6.7, -3.2, zt + 3.9, zt + 14) for s in (-1, 1))
    m -= tear_y(0.95, STOP_X + 2, zt + 10.0, -8, 8)
    m += box(STOP_X + 4, STOP_X + 12, -8, 8, zt + 3.9, zt + 21)                  # microswitch seat
    m -= box(STOP_X + 5, STOP_X + 11, -6.5, 6.5, zt + 13.5, zt + 22)            # KW mini 12.8 x 5.8, from the top
    m -= box(STOP_X + 1, STOP_X + 8, -3.2, 3.2, zt + 9.5, zt + 13.6)             # lever window
    m -= union(m3_hole(STOP_X + 3, s * 9.0, zt - 1, zt + 5) for s in (-1, 1))
    m -= box(STOP_X - 1, STOP_X + 4.5, -3.2, 3.2, zt - 1, zt + 15)                # flag swing
    return m


def make_stop_flag():
    zt = Z_TRACK + GLASS_GAP + GLASS_T + 4
    f = box(X_STOP + 0.2, X_STOP + 1.4, -2.5, 2.5, Z_TRACK + 0.1, zt + 12)
    f += ycyl(2.2, -3.0, 3.0, STOP_X + 2, zt + 10.0, 32)
    f += box(STOP_X + 2, STOP_X + 7, -2.5, 2.5, zt + 11, zt + 13)              # switch lever
    f -= ycyl(1.0, -4, 4, STOP_X + 2, zt + 10.0, 24)
    return f


# ---- 4. sleeve station (frame S) -------------------------------------------------
FENCE_Y = -(SW / 2 + 0.5)          # -y sleeve fence inner face (adjustable)
TONGUE_MOTOR = (-50.0, -28.0)      # NEMA17 under the deck, vertical shaft
IDLER = (-10.0, -28.0)
BELT_Z = (Z_DECK_S + 3.0, Z_DECK_S + 9.0)
ROD_BLOCKS = ((-62.0, -57.5), (-13.5, -9.0))
WHEEL_A = (50.0, 52.0)             # sleeve pick wheels (N20 + 2 mm O-ring link)
WHEEL_B = (50.0, 24.0)
WHEEL_R = 10.0
PUSH_SERVO = (79.0, -40.0)         # pusher servo shaft (vertical)
CRANK_R = 24.0
LINK_L = 80.0
CRANK_Z = 41.0
MOUTH_SENSOR = (6.0, -26.0)
RIG_FEET = ((-50.0, -97.0), (138.0, -97.0), (-50.0, 107.0), (138.0, 107.0))
DECK_M5 = [(ENTRY_S - 47.0, -RAIL_Y), (ENTRY_S - 37.0, -RAIL_Y), (ENTRY_S - 47.0, RAIL_Y),
           (ENTRY_S - 37.0, RAIL_Y), (EXIT_S - 19.0, -RAIL_Y), (EXIT_S + 19.0, -RAIL_Y),
           (EXIT_S - 19.0, RAIL_Y), (EXIT_S + 19.0, RAIL_Y), (60.0, -RAIL_Y)]


def make_sleeve_deck():
    z1 = Z_DECK_S
    d = box(*DECK_X, *DECK_Y, z1 - DECK_T, z1)
    d += box(-75.0, DECK_X[0] + 0.01, -48, 48, z1 - DECK_T, z1)                    # push-slot / motor tab
    d += zcyl(5.0, z1 - 0.01, BELT_Z[0], *IDLER, 32)                             # idler boss
    holes = [nema17_holes(*TONGUE_MOTOR, z1 - DECK_T - 1, z1 + 1)]
    holes += [m3_insert(*IDLER, z1 - 2, BELT_Z[0] + 1)]
    holes += [zcyl(M5, z1 - DECK_T - 1, z1 + 1, x, y, 24) for x, y in DECK_M5]
    holes += [m3_insert(x, y, z1 - DECK_T - 1, z1 - 1) for x, y in RIG_FEET]
    holes += [m3_insert(x, y, z1 - 4, z1 + 1) for x, y in (
        (-70, -30), (-70, 30), (-1.5, 60), (93.0, 60), (60, 100),                 # push slot, magazine
        (20, 0), (70, 0), (20, -30), (70, 20),                                    # platen
        (28.0, -70), (28.0, -50), (58, -54), (-2, -44),                           # lift, pusher, jet
        (106.0, 78.0), (106.0, 98.0),                                             # magazine sensor mount
    )]
    holes += [m3_insert((x0 + x1) / 2, s * ROD_TY, z1 - 4, z1 + 1) for x0, x1 in ROD_BLOCKS for s in (-1, 1)]
    holes += [zcyl(4.0, z1 - DECK_T - 1, z1 + 1, x, y, 24) for x, y in (MOUTH_SENSOR, SLEEVE_SENSOR, (50, 38))]
    return d - union(holes)


def make_platen():
    p = box(PLATEN_X[0], PLATEN_X[1], -PLATEN_Y, PLATEN_Y, Z_DECK_S, 0)
    p += box(PLATEN_X[1] - 0.01, EXIT_S - 16, -18, 18, -4, 0)                     # exit bridge
    p += union(box(x0, x1, -45, -PLATEN_Y + 0.01, Z_DECK_S, 0) for x0, x1 in ((6, 14), (70, 78)))
    p -= box(4, 78, -20, 10, -9, -3)                                              # plenum
    holes = [zcyl(0.6, -3.5, 1, x, y, 12) for x in np.arange(6, 79, 6.0) for y in np.arange(-18, 7, 6.0)
             if not (abs(y) < 4 and x < 42) and not (38 <= x <= 62 and y > 18)]
    p -= union(holes)
    p -= box(PLATEN_X[0] - 1, 40, -2.5, 2.5, -1.2, 1)                             # pusher flap groove
    p -= ycyl(1.2, -PLATEN_Y - 9, -19, 60, -6, 24)                               # vacuum port
    p += ycyl(3.0, -PLATEN_Y - 8, -PLATEN_Y + 0.01, 60, -6, 32) - ycyl(1.2, -PLATEN_Y - 9, -PLATEN_Y, 60, -6, 24)
    p -= box(WHEEL_B[0] - 5, WHEEL_B[0] + 5, WHEEL_B[1] - 12, WHEEL_B[1] + 12, Z_DECK_S - 1, -1.5)
    p -= box(WHEEL_B[0] - 4.5, WHEEL_B[0] + 4.5, WHEEL_B[1] - 10.5, WHEEL_B[1] + 10.5, -2, 1)
    p -= box(WHEEL_B[0] - 3, WHEEL_B[0] + 3, WHEEL_B[1], PLATEN_Y + 1, -20, -5)  # O-ring link
    for sx, sy in (MOUTH_SENSOR, SLEEVE_SENSOR):                                 # sleeve_mouth / sleeve_present TCRT5000
        p -= zcyl(2.5, -8, 1, sx, sy, 24)
        p -= box(sx - 5.5, sx + 5.5, sy - 3.5, sy + 3.5, Z_DECK_S - 1, -7.5)
    p -= union(m3_insert(x, -40.0, -4.5, 1) for x in (10.0, 74.0))
    p -= union(m3_insert(x, y, Z_DECK_S - 1, Z_DECK_S + 5) for x, y in ((20, 0), (70, 0), (20, -30), (70, 20)))
    return p


def make_fence():
    f = FENCE_Y
    s = box(6, 80, f - 3, f, 0, 1.5)
    s += union(box(x0, x1, -45, f, 0, 2) for x0, x1 in ((6, 14), (70, 78)))
    s -= union(zslot(x, f - 10, x, f - 5, M3, -1, 3) for x in (10.0, 74.0))
    return s


def make_magazine():
    y0, y1 = PLATEN_Y, MAG_Y1 + 3.0
    m = box(-3, SL_MAX + 3.5, y0, y1, Z_DECK_S, 0)
    m -= box(1, SL_MAX - 0.5, y0 + 4, y1 - 4, Z_DECK_S - 1, -3)                  # hollow under the floor
    m += box(-3, 0, MAG_Y0 + 3, y1, -0.01, MAG_H)                                 # mouth-side wall
    m += box(SL_MAX + 0.5, SL_MAX + 3.5, MAG_Y0 + 3, y1, -0.01, MAG_H)            # end wall
    m += box(-3, SL_MAX + 3.5, MAG_Y1, y1, -0.01, MAG_H)                          # rear wall
    for x0, x1 in ((-9.0, -2.99), (SL_MAX + 3.49, SL_MAX + 9.5)):                 # gate lugs
        m += box(x0, x1, MAG_Y0 + 3, MAG_Y0 + 12, 6, MAG_H)
        m -= ycyl(INSERT_R, MAG_Y0 + 2, MAG_Y0 + 9, (x0 + x1) / 2, 16.0, 24)
    m -= box(WHEEL_A[0] - 4.5, WHEEL_A[0] + 4.5, WHEEL_A[1] - 10.5, WHEEL_A[1] + 10.5, -4, 1)   # pick wheel A
    m -= box(WHEEL_B[0] - 3, WHEEL_B[0] + 3, y0 - 1, y0 + 5, -20, -5)            # O-ring link
    m -= union(m3_insert(x, y, Z_DECK_S - 1, Z_DECK_S + 5) for x, y in ((-1.5, 60), (93.0, 60), (60, 100)))
    m -= box(30, 70, y1 - 4, y1 + 1, 8, MAG_H + 1)                                # rear load window
    for y, z in MAG_SENS.values():                                                # mag_low / mag_empty windows
        m -= box(SL_MAX + 0.4, SL_MAX + 3.6, y - 5.2, y + 5.2, max(z - 3.0, 0.2), z + 3.0)
    return m


def make_gate():
    g = box(-9.0, SL_MAX + 9.5, MAG_Y0, MAG_Y0 + 3, GATE_GAP, MAG_H)
    for x in (-6.0, SL_MAX + 6.5):
        g -= hull([ycyl(M3, MAG_Y0 - 1, MAG_Y0 + 4, x, z, 24) for z in (13.0, 19.0)])
    g -= box(-10, 0.5, MAG_Y0 - 1, MAG_Y0 + 4, GATE_GAP - 1, 4.0)                 # clear the shims
    return g


def tongue_parts(tip):
    """Carriage (frame + both clamp bodies), keepers and steel shims at tongue tip x."""
    F = tip - SHIM_OUT
    yt = W_MAX / 2 + TONGUE_CLR                                                     # throat side guides
    c = box(F - 17, F, -21, 21, -6, Z_SHIM_LO)                                       # lower clamp body
    c += box(F - 23, F - 16.99, -yt, yt, -6, 0)                                      # lower bar
    c += union(box(F - 23, F, s * yt, s * 46, -7, 10) if s > 0 else box(F - 23, F, -46, -yt, -7, 10)
               for s in (1, -1))                                                     # side frames
    zu = Z_SHIM_HI + TONGUE_T
    c += union(box(F - 17, F, a, b, zu, 10) for a, b in ((SHIM_FORK / 2, 21), (-21, -SHIM_FORK / 2)))
    c += box(F - 23, F - 16.99, -46, 46, 6, 10)                                      # rear bridge
    c += box(F - 16, F - 10, -40, -yt + 0.01, -30, -6.99)                            # belt clamp arm
    c -= box(F - 17, F - 9, -35.4, -33.4, BELT_Z[0] + 0.5, BELT_Z[1] - 0.5)          # GT2 slot
    c -= ycyl(M3, -41, -33.5, F - 13, BELT_Z[1] + 2.5, 16)                           # clamp screw
    c -= union(xcyl(6.1, F - 24, F + 1, s * ROD_TY, ROD_TZ, 48) for s in (-1, 1))   # LM6UU
    c -= union(zcyl(0.9, -5, 1, F - 7, s * 12.0, 16) for s in (-1, 1))
    c -= union(zcyl(0.9, zu - 1, 9, F - 7, s * 12.0, 16) for s in (-1, 1))
    lo = box(F - 12, F - 2, -21, 21, Z_SHIM_LO + TONGUE_T, 1.5)
    lo -= union(zcyl(1.1, 0, 2, F - 7, s * 12.0, 16) for s in (-1, 1))
    hi = box(F - 12, F - 2, SHIM_FORK / 2, 21, 2.5, Z_SHIM_HI) - zcyl(1.1, 2, 4, F - 7, 12.0, 16)
    shim_lo = box(F - 12, tip, -SHIM_W / 2, SHIM_W / 2, Z_SHIM_LO, Z_SHIM_LO + TONGUE_T)
    shim_hi = box(F - 12, tip, -SHIM_W / 2, SHIM_W / 2, Z_SHIM_HI, zu) - \
        box(F - 5, tip + 1, -SHIM_FORK / 2, SHIM_FORK / 2, Z_SHIM_HI - 1, zu + 1)
    return c, lo, hi, mirror_y(hi), shim_lo, shim_hi


def make_rod_block(x0, x1, side=1):
    b = box(x0, x1, ROD_TY - 5.5, ROD_TY + 5.5, Z_DECK_S, ROD_TZ + 5)
    b -= xcyl(3.05, x0 - 1, x1 + 1, ROD_TY, ROD_TZ, 32)
    b -= m3_hole((x0 + x1) / 2, ROD_TY, Z_DECK_S - 1, Z_DECK_S + 8)
    return b if side > 0 else mirror_y(b)


def make_rod_block_sw():
    """-x / +y rod block stretched to y 55: KW-mini tongue_home on top (2 x M2), lever on the carriage
    side frame's rear face when the tongues are retracted."""
    x0, x1 = ROD_BLOCKS[0]
    b = make_rod_block(x0, x1, 1) + box(x0, x1, ROD_TY + 5.49, 55.0, Z_DECK_S, ROD_TZ + 5)
    b -= union(zcyl(1.0, 0.0, ROD_TZ + 6, (x0 + x1) / 2, y, 16) for y in (45.15, 51.65))
    return b


def make_air_jet():
    j = box(-6, 2, -48, -36, Z_DECK_S, 4)
    j += ycyl(2.6, -56, -47.99, 0, -6, 32)
    j -= ycyl(1.2, -57, -40, 0, -6, 24)
    j -= cyl_between((0, -40, -7), (0, -40, 2.5), 1.0, 24)
    j -= cyl_between((0, -40, 2.5), (1.5, -33.0, 2.5), 0.6, 24)                    # aims into the mouth
    j -= m3_hole(-2, -44, Z_DECK_S - 1, -20)
    return j


def make_lift_mount():
    sx, sy, sz = LIFT_SERVO
    m = box(15, 40, -75, -45, Z_DECK_S, 0)
    m += union(box(15, 40, a, b, -0.01, 27) for a, b in ((-75, -67), (-53, -45)))
    m += box(34, 37, -75, -45, Z_DECK_S, 30)                                        # ear plate
    m -= box(33, 38, -66.2, -53.8, 2.6, 25.4)                                       # MG90S body 22.8 x 12.2
    m -= union(xcyl(1.0, 32, 38, sy, sz + d, 16) for d in (-13.9, 13.9))           # ear screws
    m -= union(m3_hole(28.0, y, Z_DECK_S - 1, -28) for y in (-70.0, -50.0))
    return m


def make_lift_arm(lift=0.0):
    """Arm on the MG90S horn (shaft along x); a 9 x 6 finger runs -x along y -12 to the cup stem at CUP_X."""
    sx, sy, sz = LIFT_SERVO
    a = xcyl(6.0, 41, 44, sy, sz, 48)
    a += box(41, 44, sy, -12, sz - 3, sz + 3)
    a += xcyl(4.5, 41, 44, -12.0, sz, 32)
    a += box(CUP_X - 4.5, 41.01, -16.5, -7.5, sz - 3, sz + 3)                       # finger to the cup
    a -= xcyl(1.2, 40, 45, sy, sz, 16)
    a -= zcyl(1.6, sz - 4, sz + 4, CUP_X, -12.0, 24)                                # M4 cup stem
    ang = math.degrees(math.atan2(lift, sy - (-12.0)))
    return a.translate((0, -sy, -sz)).rotate((ang, 0, 0)).translate((0, sy, sz)) if lift else a


def push_pose(p):
    """Crank angle for the slider pin at x = p + 4 (offset slider-crank)."""
    px, py = PUSH_SERVO
    sxp = p + 4.0
    best = None
    for k in range(3600):
        t = 2 * math.pi * k / 3600
        cx, cy = px + CRANK_R * math.cos(t), py + CRANK_R * math.sin(t)
        err = abs(math.hypot(sxp - cx, 0.0 - cy) - LINK_L)
        if cx > sxp and (best is None or err < best[0]):
            best = (err, cx, cy)
    return best[1], best[2]


def pusher_parts(p=PUSH_START):
    """Guide bar + bracket (fixed), slider + post, flap, crank, link at flap x p."""
    br = box(50, 66, -60, -48, Z_DECK_S, 34)
    br += box(50, 66, -48.01, 3, PUSH_Z - 3, PUSH_Z + 3)
    br += box(-26, 66, -3, 3, PUSH_Z - 3, PUSH_Z + 3)                                # guide bar 6 x 6
    br += box(50, 102, -48.01, -32, 29.5, 33.5)                                      # servo arm
    br -= box(72.8, 96.0, -46.2, -33.8, 29, 34)                                      # MG90S cut-out
    br -= union(zcyl(1.0, 28, 35, x, -40, 16) for x in (70.4, 98.4))                # servo ear screws
    br -= union(m3_hole(58, -54, Z_DECK_S - 1, Z_DECK_S + 8) for _ in (0,))
    sl = box(p - 4, p + 12, -6, 6, PUSH_Z - 6, PUSH_Z + 6)
    sl -= box(p - 5, p + 13, -3.25, 3.25, PUSH_Z - 3.25, PUSH_Z + 3.25)
    sl += zcyl(3.0, PUSH_Z + 6 - 0.01, PUSH_Z + 12, p + 4, 0, 32)
    sl -= zcyl(1.5, PUSH_Z + 2, PUSH_Z + 13, p + 4, 0, 16)
    sl += box(p - 2, p, -2, 2, 6, PUSH_Z - 5.99)                                     # post
    sl -= ycyl(0.8, -3, 3, p - 1, 8.0, 16)
    fl = box(p, p + 1.2, -3.5, 3.5, FLAP_TIP, 9.5)                                  # gravity pawl, rests on the keeper
    fl += union(box(p - 2, p + 1.2, a, b, 6, 10) for a, b in ((2.1, 3.5), (-3.5, -2.1)))
    fl -= ycyl(0.85, -4, 4, p - 1, 8.0, 16)
    cx, cy = push_pose(p)
    px, py = PUSH_SERVO
    ang = math.atan2(cy - py, cx - px)
    cr = hull([zcyl(5.0, CRANK_Z, CRANK_Z + 3, px, py, 32), zcyl(3.5, CRANK_Z, CRANK_Z + 3, cx, cy, 32)])
    cr -= zcyl(2.45, CRANK_Z - 1, CRANK_Z + 4, px, py, 24)                          # on the MG90S horn spline
    cr -= zcyl(1.5, CRANK_Z - 1, CRANK_Z + 4, cx, cy, 16)
    sxp = p + 4.0
    lk = hull([zcyl(3.5, PUSH_Z + 12, PUSH_Z + 15, sxp, 0, 32), zcyl(3.5, PUSH_Z + 12, PUSH_Z + 15, cx, cy, 32)])
    lk -= zcyl(1.5, PUSH_Z + 11, PUSH_Z + 16, sxp, 0, 16)
    lk -= zcyl(1.5, PUSH_Z + 11, PUSH_Z + 16, cx, cy, 16)
    return br, sl, fl, cr, lk, (cx, cy, ang)


def make_rig_push_slot():
    yt = W_MAX / 2 + 1.0
    s = box(-75, -63, -40, 40, Z_DECK_S, Z_CARD_S)
    s += union(box(-75, -63, a, b, Z_CARD_S - 0.01, Z_CARD_S + 5) for a, b in ((yt, 40), (-40, -yt)))
    s -= box(-76, -62, -8, 8, Z_CARD_S - 1.5, Z_CARD_S + 1)                          # finger groove
    s -= union(m3_hole(-70, y, Z_DECK_S - 1, Z_CARD_S + 6) for y in (-30.0, 30.0))
    return s


def make_rig_foot():
    f = box(-10, 10, -10, 10, 0, RIG_FOOT)
    f -= zcyl(M3, RIG_FOOT - 12, RIG_FOOT + 1, 0, 0, 24)
    f -= zcyl(3.2, -1, RIG_FOOT - 14, 0, 0, 24)
    return f


def make_push_stick():
    s = box(0, 110, -20, 20, 0, 1.6)
    s -= box(90, 111, -12, 12, -1, 3)
    return s + box(0, 30, -20, 20, 0, 6)


# ---- 5. diverter + bins ----------------------------------------------------------
DIV_TILT = 25.0        # tray slope (sleeved PP slides on PETG above ~17 deg)
DIV_Z = Z_PLATEN - 2.0  # tray top at the pivot
DIV_LEN = 120.0
DIV_ANGS = (-42.0, 0.0, 42.0)
BIN_FLOOR = 3.0        # bins stand on a 3 mm board on the base frame
DIV_END_Z = DIV_Z - DIV_LEN * math.sin(math.radians(DIV_TILT))
BIN_R0 = DIV_LEN * math.cos(math.radians(DIV_TILT)) + 2.0


def make_diverter_base():
    x0 = X_EXIT + 26.0
    b = box(x0, X_DIV + 44, -RAIL_Y - 10, RAIL_Y + 10, Z_DECK, Z_DECK + 5)
    b += box(X_EXIT + 15, X_DIV - 12, -38, 38, Z_PLATEN - 4, Z_PLATEN - 1)         # lead-in
    b += union(box(x0, x0 + 7, a, b_, Z_DECK + 4.99, Z_PLATEN - 3.99) for a, b_ in ((-38, -28), (28, 38)))
    sx0 = X_DIV - 16.8                                                              # shaft 6 mm from the +x end
    top = DIV_Z - 13.14
    b += box(sx0 - 3, sx0 + 25.8, -9.1, 9.1, Z_DECK + 4.99, top)                    # servo tower
    b -= box(sx0, sx0 + 22.8, -6.1, 6.1, Z_DECK + 7, top + 1)                       # MG90S pocket
    b -= union(zcyl(1.0, top - 7, top + 1, x, 0, 16) for x in (sx0 - 2.35, sx0 + 25.15))
    b -= box(sx0 + 5, sx0 + 18, -10, -5, Z_DECK + 7, Z_DECK + 14)                   # cable
    b -= zcyl(2.5, Z_PLATEN - 5, Z_PLATEN, X_EXIT + 26.0, 12.0, 24)                # exit TCRT5000
    b -= box(X_EXIT + 20.5, X_EXIT + 31.5, 8.5, 15.5, Z_PLATEN - 5, Z_PLATEN - 3.5)
    b -= union(zcyl(M5, Z_DECK - 1, Z_DECK + 6, x, s * RAIL_Y, 24) for x in (x0 + 15, X_DIV + 34) for s in (-1, 1))
    return b


def div_place(m, ang):
    return m.rotate((0, 0, ang)).translate((X_DIV, 0, DIV_Z))


def make_diverter_tray():
    """Local: pivot at origin, tray top surface through the origin, sloping down along +x."""
    w = SW_MAX / 2 + 4.0
    t = hull([box(-2, 2, -10, 10, -2.5, 0), box(40, DIV_LEN, -w, w, -2.5, 0)])
    t += union(box(40, DIV_LEN, a, b, -0.01, 4) for a, b in ((w - 3, w), (-w, -w + 3)))
    t = t.rotate((0, DIV_TILT, 0))
    t += zcyl(8.0, -6, -1.0, 0, 0, 48)
    t -= zcyl(1.1, -11, 0.5, 0, 0, 16)
    t -= zcyl(2.5, -7, -2.5, 0, 0, 24)                                             # horn / spline
    t -= union(zcyl(0.8, -11, -4, 0, d, 12) for d in (-5.5, 5.5))
    return t


def bin_place(m, ang):
    return m.rotate((0, 0, ang)).translate((X_DIV, 0, 0))


def make_bin():
    """Local: radial x from the pivot.  Inner 97 x 71 x 60 (100 sleeved cards ~ 45 mm)."""
    l, w, d = BIN_IN
    x0 = BIN_R0
    top = BIN_FLOOR + d + 3.0
    b = box(x0 - 2.5, x0 + l + 2.5, -w / 2 - 2.5, w / 2 + 2.5, BIN_FLOOR, top)
    b -= box(x0, x0 + l, -w / 2, w / 2, BIN_FLOOR + 3, top + 1)
    b -= box(x0 - 3, x0 + 0.01, -w / 2 + 8, w / 2 - 8, top - 18, top + 1)           # landing notch
    b -= box(x0 + l / 2 - 15, x0 + l / 2 + 15, -w / 2 - 3, -w / 2 + 0.01, top - 25, top + 1)   # grip
    return b


# ---- 6. frame + electronics ---------------------------------------------------------
FRAME_X = (-125.0, 800.0)
FRAME_Y = (-255.0, 175.0)
CROSS_X = (-104.0, 42.0, 90.0, 300.0, 600.0, 790.0)
POSTS_X = (90.0, 300.0, 600.0)
DECK_RAIL_X = (36.0, 612.0)
ELEC_RAILS_Y = (-235.0, -105.0)


def frame():
    f = {}
    for i, y in enumerate((FRAME_Y[0] + 10, FRAME_Y[1] - 10)):
        f[f"ext_base_x{i}"] = box(*FRAME_X, y - 10, y + 10, -20, 0)
    for i, x in enumerate(CROSS_X):
        f[f"ext_cross_{i}"] = box(x - 10, x + 10, FRAME_Y[0] + 20, FRAME_Y[1] - 20, -20, 0)
    for i, y in enumerate(ELEC_RAILS_Y):
        f[f"ext_elec_{i}"] = box(-10, 500, y - 10, y + 10, -40, -20)
    for s, n in ((-1, "m"), (1, "p")):
        f[f"ext_deck_{n}"] = box(*DECK_RAIL_X, s * RAIL_Y - 10, s * RAIL_Y + 10, Z_DECK - 20, Z_DECK)
        for i, x in enumerate(POSTS_X):
            f[f"ext_post_{n}{i}"] = box(x - 10, x + 10, s * RAIL_Y - 10, s * RAIL_Y + 10, 0, Z_DECK - 20)
    f["bin_board"] = box(620, 800, -170, 170, 0, BIN_FLOOR)
    return f


def make_corner_bracket():
    """2020 L bracket, 2 x M5 per leg."""
    b = box(0, 20, 0, 20, 0, 4) + box(0, 20, 0, 4, 0, 20)
    b += xform(box(-1.5, 1.5, 0, 16, 0, 16), [[1, 0, 0, 10], [0, 0.7071, -0.7071, 4], [0, 0.7071, 0.7071, 4]]) \
        .trim_by_plane((0, 1, 0), 3.9).trim_by_plane((0, 0, 1), 3.9).trim_by_plane((0, -1, 0), -20) \
        .trim_by_plane((0, 0, -1), -20)
    b -= zcyl(M5, -1, 5, 10, 13, 24)
    b -= ycyl(M5, -1, 5, 10, 13, 24)
    return b


def make_frame_foot():
    f = zcyl(16.0, 0, FOOT_H, 0, 0, 64) + box(-10, 10, -10, 10, FOOT_H - 0.01, FOOT_H + 3)
    f -= zcyl(M5, -1, FOOT_H + 4, 0, 0, 24)
    f -= zcyl(5.0, -1, FOOT_H - 8, 0, 0, 32)
    return f


def make_feed_motor_mount():
    """L bracket on the -y deck rail outer face; NEMA17 shaft along +y."""
    x0, x1, zc = 300.0, 345.0, 55.0
    y_r = -RAIL_Y - 10
    m = box(x0, x1, y_r - 4, y_r, Z_DECK - 20, Z_DECK - 1)                           # rail flange
    m += box(x0, x1, y_r - 22, y_r - 18, zc - 22, Z_DECK - 1)                         # motor plate
    m += box(x0, x1, y_r - 22, y_r, Z_DECK - 5, Z_DECK - 1)                           # web
    m += union(box(x, x + 4, y_r - 22, y_r, zc + 2, Z_DECK - 1) for x in (x0, x1 - 4))
    m -= union(ycyl(M5, y_r - 5, y_r + 1, x, Z_DECK - 10, 24) for x in (x0 + 8, x1 - 8))
    m -= ycyl(11.5, y_r - 23, y_r - 17, (x0 + x1) / 2, zc, 48)
    m -= union(ycyl(M3, y_r - 23, y_r - 17, (x0 + x1) / 2 + a * 15.5, zc + b * 15.5, 24)
               for a in (-1, 1) for b in (-1, 1))
    return m


def make_elec_plate(xr, boards):
    x0, x1 = xr
    y0, y1 = ELEC_Y
    p = box(x0, x1, y0, y1, 0, ELEC_T)
    holes, extra = [], []
    for name, (bx, by, l, w, h, mh) in boards.items():
        ox, oy = x0 + bx, y0 + by
        if mh:
            for hx, hy in mh:
                extra.append(zcyl(3.2, ELEC_T - 0.01, ELEC_T + 6, ox + hx, oy + hy, 24))
                holes.append(zcyl(1.8, 1.0, ELEC_T + 7, ox + hx, oy + hy, 16))
        else:            # cable-tie slots
            for sx in (ox + 5, ox + l - 8):
                holes.append(box(sx, sx + 3, oy - 3, oy + w + 3, -1, ELEC_T + 1) -
                             box(sx - 1, sx + 4, oy + 0.01, oy + w - 0.01, -2, ELEC_T + 2))
    p += union(extra)
    p -= union(holes)
    p -= union(zcyl(M5, -1, ELEC_T + 1, x, y, 24) for x in (x0 + 12, x1 - 12) for y in ELEC_RAILS_Y)
    p -= union(box(x, x + 40, y0 + 120, y0 + 130, -1, ELEC_T + 1) for x in (x0 + 140, x0 + 190)) \
        if x0 == ELEC_A_X[0] else box(x0 + 195, x0 + 235, y0 + 100, y0 + 107, -1, ELEC_T + 1)
    return p


# ---- 7. endstops, magazine sensors, lid + e-stop -----------------------------------
def make_elev_switch_post():
    """Post on hopper_base (+y of the platform arm): KW11 elev_home low, elev_limit high, both tripped by
    the platform tab.  Foot slotted along y to set the lever overtravel."""
    x0, x1, yf = ESW_X[0] - 2, ESW_X[1] + 2, ESW_Y[1]
    p = box(x0, x1, yf, yf + 6, 6, ESW_LIMIT_Z[1] + 2)
    p += box(x0, x1, yf, 68, 6, 10)
    p += box(-72, -68, yf + 5.99, 68, 9.99, 40)                                     # rib
    p -= union(zslot(x, 58, x, 64, M3, 5, 11) for x in (-76.0, -64.0))
    xc = sum(ESW_X) / 2
    p -= union(ycyl(1.0, yf - 1, yf + 7, xc + d, (z0 + z1) / 2, 16)
               for d in (-4.75, 4.75) for z0, z1 in (ESW_HOME_Z, ESW_LIMIT_Z))      # M2 switch screws
    return p


def make_mag_sensor_mount():
    """(S) Plate outside the magazine end wall: TCRT5000 mag_empty (bottom) + mag_low look through the wall
    windows at the closed ends of the sleeve stack.  2 x M3 to the sleeve deck."""
    x0 = MAG_SENS_X
    m = box(x0, x0 + 4.4, 72, 104, Z_DECK_S, 12) + box(x0, 112, 72, 104, Z_DECK_S, Z_DECK_S + 5)
    m += union(box(x0 + 4.39, 112, y, y + 4, Z_DECK_S + 4.99, -6) for y in (72.0, 100.0))   # gussets
    m -= union(cbox(x0 + 2.2, y, z, 4.6, 10.4, 6.0) for y, z in MAG_SENS.values())   # TCRT5000 heads
    m -= union(m3_hole(106.0, y, Z_DECK_S - 1, Z_DECK_S + 6) for y in (78.0, 98.0))
    return m


def make_lid_switch_mount():
    """L bracket on the +y base rail for the lid interlock (D4NS class, actuator key on the lid)."""
    x0, x1, y0, y1, z0, z1 = LID_SW
    b = box(320, 380, y0, y1 + 4, 0, 4) + box(320, 380, y1, y1 + 4, 3.99, 60)
    b -= union(zcyl(M5, -1, 5, x, (y0 + y1 + 4) / 2, 24) for x in (326.0, 374.0))
    b -= union(ycyl(2.2, y1 - 1, y1 + 5, x, z, 24) for x in (340.0, 360.0) for z in (20.0, 45.0))
    return b


def make_estop_panel():
    """Panel on the -y base rail at the electronics bay: 22.3 mm hole + anti-rotation notch."""
    y0 = FRAME_Y[0]
    ex, ez = ESTOP
    p = box(ex - 22, ex + 22, y0, y0 + 20, 0, 5) + box(ex - 22, ex + 22, y0, y0 + 4, 4.99, ez + 24)
    p += union(box(x, x + 4, y0 + 3.99, y0 + 20, 4.99, 30) for x in (ex - 22, ex + 18))   # gussets
    p -= ycyl(11.15, y0 - 1, y0 + 5, ex, ez, 64)
    p -= box(ex - 1.6, ex + 1.6, y0 - 1, y0 + 5, ez + 11, ez + 13.5)
    p -= union(zcyl(M5, -1, 6, x, y0 + 10, 24) for x in (ex - 10, ex + 10))
    return p

# ---- hardware stand-ins (preview only) --------------------------------------------
def roller_set(nx, z_nip, lower_cross, upper_cross, wy):
    """Shafts + hubs (with O-ring) + 608 bearings at one nip (world)."""
    z_lo, z_up = z_nip - R_ROLL, z_nip + CARD_T + R_ROLL
    out = {}
    for tag, zc, cross in (("lo", z_lo, lower_cross), ("up", z_up, upper_cross)):
        if cross:
            sh = ycyl(SHAFT_R, -BLOCK_Y[1] - (14 if tag == "lo" else 0), BLOCK_Y[1], nx, zc, 24)
        else:
            sh = union(ycyl(SHAFT_R, s * BLOCK_Y[1], s * (wy - HUB_W / 2), nx, zc, 24) if s < 0 else
                       ycyl(SHAFT_R, wy - HUB_W / 2, BLOCK_Y[1], nx, zc, 24) for s in (-1, 1))
            if tag == "lo":
                sh += ycyl(SHAFT_R, -BLOCK_Y[1] - 14, -BLOCK_Y[1], nx, zc, 24)
        out[f"shaft_{tag}"] = sh
        out[f"wheels_{tag}"] = union(ycyl(R_ROLL, s * wy - HUB_W / 2, s * wy + HUB_W / 2, nx, zc, 48)
                                     for s in (-1, 1))
        out[f"b608_{tag}"] = union(ycyl(B608[0], s * BLOCK_Y[0], s * (BLOCK_Y[0] + B608[1]), nx, zc, 32)
                                   if s > 0 else ycyl(B608[0], -BLOCK_Y[0] - B608[1], -BLOCK_Y[0], nx, zc, 32)
                                   for s in (-1, 1))
    return out


def mg90s(x0, y0, z0, axis="z"):
    """MG90S body 22.8 x 12.2 x 22.5 + ears, shaft up (+z) at 6 mm from the -x end."""
    b = box(x0, x0 + 22.8, y0 - 6.1, y0 + 6.1, z0, z0 + 22.5)
    b += box(x0 - 4.7, x0 + 27.5, y0 - 6.1, y0 + 6.1, z0 + 15.5, z0 + 18.0)
    b += zcyl(2.4, z0 + 22.5, z0 + 26.5, x0 + 6.0, y0, 24)
    return b


def nema17(cx, cy, cz, axis):
    """NEMA17 42.3 sq x 40, face centre (cx, cy, cz), shaft toward the face side along axis."""
    b = cbox(0, 0, -20, 42.3, 42.3, 40) + zcyl(2.5, 0, 24, 0, 0, 24) + zcyl(11, 0, 2, 0, 0, 32)
    r = {"+z": np.eye(3), "-z": np.diag([1.0, -1.0, -1.0]),
         "+y": np.array([[1, 0, 0], [0, 0, 1], [0, -1, 0]], float),
         "-y": np.array([[1, 0, 0], [0, 0, -1], [0, 1, 0]], float)}[axis]
    return b.transform(np.hstack([r, np.array([[cx], [cy], [cz]])]))


def components(pose):
    c = {}
    # hopper
    c["nema_elevator"] = nema17(ELEV_X, 0, 0.0, "+z") + zcyl(4.0, 0, 150, ELEV_X, 0, 24)
    c["rods_elevator"] = union(zcyl(4.0, 8, HOP_TOP + 8, ELEV_X, s * ROD_Y, 24) for s in (-1, 1))
    c["lm8uu"] = union(zcyl(7.5, PLAT_LO - 24, PLAT_LO, ELEV_X, s * ROD_Y, 32) for s in (-1, 1))
    c["card_stack"] = box(-CL / 2, CL / 2, -CW / 2, CW / 2, PLAT_LO, STACK_TOP)
    cx = pose["pick"]
    c["cup_pick"] = zcone(10.0, 6.0, Z_TRACK + CARD_T, Z_TRACK + 12, cx) + zcyl(2.5, Z_TRACK + 12, PICK_Z - 8, cx)
    c["rods_pick"] = union(xcyl(3.0, -50, 50, s * 16.0, PICK_Z, 24) for s in (-1, 1))
    c["nema_pick"] = nema17(-80.0, LEG_Y[0], PICK_Z, "+y")
    c["ir_stack_top"] = box(-39, -33, -26, -16, Z_TRACK + 8, Z_TRACK + 15)
    c["slot_double_feed"] = box(HOP_IN_X + 9, HOP_IN_X + 15.5, 36.5, 46.5, Z_TRACK + 3.5, Z_TRACK + 15)
    xs, ys = ESW_X, ESW_Y                                                          # KW11 + roller lever stubs
    c["sw_elev_home"] = box(*xs, *ys, *ESW_HOME_Z) + box(-76, -62, 44.5, 49, ESW_HOME_Z[1], ESW_HOME_Z[1] + 0.5)
    c["sw_elev_limit"] = box(*xs, *ys, *ESW_LIMIT_Z) + box(-76, -62, 44.5, 49, ESW_LIMIT_Z[0] - 0.5, ESW_LIMIT_Z[0])
    c["sw_pick_home"] = box(-37.9, -32.1, -6.4, 6.4, PICK_Z - 3.25, PICK_Z + 3.25) + \
        box(-32.1, -27.5, -4, 4, PICK_Z + 1, PICK_Z + 2)                           # lever 0.5 off the carriage at home
    # rollers (world)
    nips = {"feed": (X_FEED, Z_TRACK, True, True, WHEEL_Y), "scan_in": (X_SCAN_IN, Z_TRACK, True, False, STUB_Y),
            "scan_out": (X_SCAN_OUT, Z_TRACK, False, False, STUB_Y), "xfer": (X_XFER, Z_TRACK, True, True, WHEEL_Y),
            "entry": (X_ENTRY, Z_TRACK, True, False, STUB_Y), "exit": (X_EXIT, Z_PLATEN, True, True, WHEEL_Y)}
    for n, (x, z, lc, uc, wy) in nips.items():
        for k, v in roller_set(x, z, lc, uc, wy).items():
            c[f"{n}_{k}"] = v
    c["nema_feed"] = nema17(322.5, -RAIL_Y - 32, 55.0, "+y")
    # scan
    c["glass_lower"] = box(*GLASS_LO, -GLASS_W / 2, GLASS_W / 2, Z_TRACK - GLASS_T, Z_TRACK)
    c["glass_upper"] = box(*GLASS_HI, -GLASS_W / 2, GLASS_W / 2, Z_TRACK + GLASS_GAP, Z_TRACK + GLASS_GAP + GLASS_T)
    c["card_scan"] = box(X_STOP - CL, X_STOP, -CW / 2, CW / 2, Z_TRACK, Z_TRACK + CARD_T)
    cam = box(-12.5, 12.5, -14.5, 9.5, -3.0, -2.0) + zcyl(4.25, -2.0, 6.0, 0, 0, 32)   # CM3 in mount frame
    c["cm3_top"] = cam_top(cam)
    c["cm3_bot"] = cam_bot(cam)
    zt = Z_TRACK + GLASS_GAP + GLASS_T + 4
    c["microswitch_stop"] = box(STOP_X + 5.1, STOP_X + 10.9, -6.4, 6.4, zt + 13.6, zt + 20.1)
    # sleeve station (S)
    s = {}
    tip = pose["tongue"]
    _, _, _, _, shim_lo, shim_hi = tongue_parts(tip)
    s["shim_lower"], s["shim_upper"] = shim_lo, shim_hi
    s["rods_tongue"] = union(xcyl(3.0, -62, -9.5, k * ROD_TY, ROD_TZ, 24) for k in (-1, 1))
    s["lm6uu_tongue"] = union(xcyl(6.0, tip - SHIM_OUT - 22, tip - SHIM_OUT - 3, k * ROD_TY, ROD_TZ, 32)
                              for k in (-1, 1))
    s["nema_tongue"] = nema17(*TONGUE_MOTOR, Z_DECK_S - DECK_T, "+z")
    s["gt2_pulley"] = zcyl(6.4, BELT_Z[0], BELT_Z[1], *TONGUE_MOTOR, 32) + zcyl(6.4, BELT_Z[0] + 0.3, BELT_Z[1], *IDLER, 32)
    s["sleeve"] = box(0, SL, -SW / 2, SW / 2, 0, 2 * PLY) + box(0, SL * 0.6, -SW / 2 + 6, SW / 2 - 6, LIFT - 0.1, LIFT)
    s["sleeve_stack"] = box(0, SL, MAG_Y0 + 3.5, MAG_Y0 + 3.5 + SW, 0, 12.0)
    s["cup_lift"] = zcone(5.0, 3.5, LIFT, LIFT + 5.0, CUP_X, -12.0) + zcyl(1.5, LIFT + 5.0, LIFT_SERVO[2], CUP_X, -12.0)
    s["servo_lift"] = box(16.0, 38.8, -66.1, -53.9, 2.6, 25.4) + \
        xcyl(2.4, 38.8, 41, LIFT_SERVO[1], LIFT_SERVO[2], 24)
    s["servo_pusher"] = mg90s(PUSH_SERVO[0] - 6.0, PUSH_SERVO[1], CRANK_Z - 23.0)
    s["n20_pick"] = xcyl(6.0, WHEEL_A[0] + 6, WHEEL_A[0] + 34, WHEEL_A[1], -WHEEL_R + 0.3 - 0.0, 24)
    s["pick_wheels"] = union(xcyl(WHEEL_R, w[0] - 4, w[0] + 4, w[1], -WHEEL_R + 0.3, 48) for w in (WHEEL_A, WHEEL_B))
    s["tcrt_mouth"] = box(MOUTH_SENSOR[0] - 5, MOUTH_SENSOR[0] + 5, MOUTH_SENSOR[1] - 3, MOUTH_SENSOR[1] + 3,
                          Z_DECK_S, -8)
    s["tcrt_present"] = box(SLEEVE_SENSOR[0] - 5, SLEEVE_SENSOR[0] + 5, SLEEVE_SENSOR[1] - 3, SLEEVE_SENSOR[1] + 3,
                            Z_DECK_S, -8)
    s["sw_tongue_home"] = box(*TSW) + box(TSW[1], TSW[1] + 0.35, 42.5, 45.5, 6, 10)   # lever 0.25 off the retracted carriage
    for n, (y, z) in MAG_SENS.items():
        x0 = MAG_SENS_X
        s[f"tcrt_{n}"] = box(x0 + 0.3, x0 + 4.4, y - 5, y + 5, z - 2.8, z + 2.8) + \
            box(x0 + 4.6, x0 + 6.2, y - 7, y + 7, z - 5, z + 20)                     # head + module PCB
    for k, v in s.items():
        c[k] = to_sleeve(v)
    c["servo_diverter"] = mg90s(X_DIV - 6.0, 0, DIV_Z - 13.14 - 15.5).mirror((1, 0, 0)).translate((2 * X_DIV, 0, 0))
    c["sleeved_card"] = div_place(box(0, SL, -SW / 2, SW / 2, 0.0, 0.42).rotate((0, DIV_TILT, 0))
                                  .translate((10, 0, -10 * math.tan(math.radians(DIV_TILT)) + 0.0)), pose["diverter"])
    # electronics + safety
    ex, ez = ESTOP
    y0 = FRAME_Y[0]
    c["estop"] = ycyl(20.0, y0 - 14, y0 - 4, ex, ez, 48) + ycyl(14.0, y0 - 4, y0, ex, ez, 48) + \
        ycyl(11.0, y0, y0 + 4, ex, ez, 48) + box(ex - 14, ex + 14, y0 + 4.1, y0 + 44, ez - 14, ez + 14)
    c["lid_switch"] = box(*LID_SW) + box(LID_SW[0] + 5, LID_SW[1] - 5, LID_SW[2] + 3, LID_SW[3] - 3,
                                          LID_SW[5], LID_SW[5] + 10)                 # body + key head
    for xr, boards in ((ELEC_A_X, BOARDS_A), (ELEC_B_X, BOARDS_B)):
        for name, (bx, by, l, w, h, mh) in boards.items():
            z0 = ELEC_T + (6 if mh else 0)
            c[name] = box(xr[0] + bx, xr[0] + bx + l, ELEC_Y[0] + by, ELEC_Y[0] + by + w, z0, z0 + h)
    return c


def zcone(r0, r1, z0, z1, x=0.0, y=0.0, seg=48):
    return m3d.Manifold.cylinder(z1 - z0, r0, r1, seg).translate((x, y, z0))


# ---- build -------------------------------------------------------------------------
POSE = {"pick": PICK_X0, "tongue": TONGUE_POS, "pusher": PUSH_START, "diverter": 0.0}

# name: (up vector for printing, qty, sets)   sets: m = machine, r = phase-1 rig
PRINT = {
    "hopper_base": ((0, 0, 1), 1, "m"), "hopper_guide": ((0, 1, 0), 2, "m"),
    "hopper_back": ((-1, 0, 0), 1, "m"), "hopper_front": ((1, 0, 0), 1, "m"),
    "elevator_platform": ((0, 0, -1), 1, "m"), "pick_bridge": ((0, 0, -1), 1, "m"),
    "pick_carriage": ((0, 0, 1), 1, "m"),
    "roller_block": ((0, 0, 1), 10, "m"), "roller_block_s": ((0, 0, 1), 2, "m"),
    "roller_hub": ((0, 0, 1), 24, "m"),
    "track_feed": ((0, 0, -1), 1, "m"), "track_scan_out": ((0, 0, -1), 1, "m"),
    "track_xfer": ((0, 0, -1), 1, "m"), "guide_rail_40": ((0, 0, 1), 4, "m"),
    "guide_rail_18": ((0, 0, 1), 2, "m"),
    "hood": ((0, 0, -1), 1, "m"), "lower_shroud": ((0, 0, 1), 1, "m"),
    "led_frame_top": ((0, 0, -1), 1, "m"), "led_frame_bot": ((0, 0, 1), 1, "m"),
    "cam_mount": ((0, 0, 1), 2, "m"), "stop_mount": ((0, 0, 1), 1, "m"), "stop_flag": ((0, 1, 0), 1, "m"),
    "sleeve_deck": ((0, 0, 1), 1, "mr"), "platen": ((0, 0, -1), 1, "mr"), "sleeve_fence": ((0, 0, 1), 1, "mr"),
    "sleeve_magazine": ((0, 0, 1), 1, "mr"), "sleeve_gate": ((0, 1, 0), 1, "mr"),
    "tongue_carriage": ((0, 0, 1), 1, "mr"), "tongue_keeper_lo": ((0, 0, 1), 1, "mr"),
    "tongue_keeper_hi": ((0, 0, 1), 2, "mr"), "tongue_rod_block": ((0, 0, 1), 3, "mr"),
    "tongue_rod_block_sw": ((0, 0, 1), 1, "mr"), "mag_sensor_mount": ((0, 0, 1), 1, "mr"),
    "air_jet": ((0, 0, 1), 1, "mr"), "lift_mount": ((0, 0, 1), 1, "mr"), "lift_arm": ((-1, 0, 0), 1, "mr"),
    "pusher_bracket": ((0, 0, 1), 1, "mr"), "pusher_slider": ((1, 0, 0), 1, "mr"),
    "pusher_flap": ((0, 1, 0), 1, "mr"), "pusher_crank": ((0, 0, 1), 1, "mr"),
    "pusher_link": ((0, 0, 1), 1, "mr"),
    "rig_foot": ((0, 0, 1), 4, "r"), "rig_push_slot": ((0, 0, 1), 1, "r"), "rig_push_stick": ((0, 0, 1), 1, "r"),
    "diverter_base": ((0, 0, 1), 1, "m"), "bin": ((0, 0, 1), 3, "m"),
    "diverter_tray": ((math.sin(math.radians(DIV_TILT)), 0, math.cos(math.radians(DIV_TILT))), 1, "m"),
    "corner_bracket": ((0, 0, 1), 12, "m"), "frame_foot": ((0, 0, 1), 6, "m"),
    "feed_motor_mount": ((0, -1, 0), 1, "m"),
    "elec_plate_a": ((0, 0, 1), 1, "m"), "elec_plate_b": ((0, 0, 1), 1, "m"),
    "elev_switch_post": ((0, 1, 0), 1, "m"), "lid_switch_mount": ((0, 0, 1), 1, "m"),
    "estop_panel": ((0, 1, 0), 1, "m"),
}


def build(pose=POSE):
    """Returns (assembled printed parts {preview name: (part name, manifold)}, singles {part: manifold})."""
    A = {}

    def put(pname, m, key=None):
        A[key or pname] = (pname, clean(m))

    put("hopper_base", make_hopper_base())
    put("hopper_guide", make_hopper_guide(1), "hopper_guide_p")
    put("hopper_guide", make_hopper_guide(-1), "hopper_guide_m")
    put("hopper_back", make_hopper_back())
    put("hopper_front", make_hopper_front())
    put("elevator_platform", make_platform())
    put("elev_switch_post", make_elev_switch_post())
    put("pick_bridge", make_pick_bridge())
    put("pick_carriage", make_pick_carriage(pose["pick"]))
    for n, x in (("feed", X_FEED), ("scan_in", X_SCAN_IN), ("scan_out", X_SCAN_OUT), ("xfer", X_XFER)):
        b = make_roller_block(x, Z_DECK, Z_TRACK)
        put("roller_block", b, f"roller_block_{n}_p")
        put("roller_block", mirror_y(b), f"roller_block_{n}_m")
    b = make_roller_block(X_EXIT, Z_DECK + DECK_T, Z_PLATEN)
    put("roller_block", b, "roller_block_exit_p")
    put("roller_block", mirror_y(b), "roller_block_exit_m")
    b = make_roller_block(X_ENTRY, Z_DECK + DECK_T, Z_TRACK, foot=(-34.0, 14.0), body=14.0)
    put("roller_block_s", b, "roller_block_entry_p")
    put("roller_block_s", mirror_y(b), "roller_block_entry_m")
    for name, (x0, x1, legs, glass, arch) in TRACKS.items():
        put(name, make_track(x0, x1, legs, glass, arch))
        rx0, rx1 = rail_range(x0, x1, arch)
        rail = "guide_rail_40" if rx1 - rx0 > 30 else "guide_rail_18"
        put(rail, make_guide_rail(rx0, rx1, 1), f"{rail}_{name}_p")
        put(rail, make_guide_rail(rx0, rx1, -1), f"{rail}_{name}_m")
    put("hood", make_hood())
    put("lower_shroud", make_lower_shroud())
    put("led_frame_top", make_led_frame_top())
    put("led_frame_bot", make_led_frame_bot())
    cm = make_cam_mount()
    put("cam_mount", cam_top(cm), "cam_mount_top")
    put("cam_mount", cam_bot(cm), "cam_mount_bot")
    put("stop_mount", make_stop_mount())
    put("stop_flag", make_stop_flag())
    S = {}
    S["sleeve_deck"] = make_sleeve_deck()
    S["platen"] = make_platen()
    S["sleeve_fence"] = make_fence()
    S["sleeve_magazine"] = make_magazine()
    S["sleeve_gate"] = make_gate()
    car, klo, khi, khi2, _, _ = tongue_parts(pose["tongue"])
    S["tongue_carriage"], S["tongue_keeper_lo"] = car, klo
    S["tongue_keeper_hi"], S["tongue_keeper_hi_m"] = khi, khi2
    for i, (x0, x1) in enumerate(ROD_BLOCKS):
        if i == 0:
            S["tongue_rod_block_sw_0p"] = make_rod_block_sw()                 # carries tongue_home
        else:
            S[f"tongue_rod_block_{i}p"] = make_rod_block(x0, x1, 1)
        S[f"tongue_rod_block_{i}m"] = make_rod_block(x0, x1, -1)
    S["air_jet"] = make_air_jet()
    S["lift_mount"] = make_lift_mount()
    S["lift_arm"] = make_lift_arm()
    br, sl, fl, cr, lk, _ = pusher_parts(pose["pusher"])
    S["pusher_bracket"], S["pusher_slider"], S["pusher_flap"] = br, sl, fl
    S["pusher_crank"], S["pusher_link"] = cr, lk
    S["mag_sensor_mount"] = make_mag_sensor_mount()
    for k, v in S.items():
        pname = k.rsplit("_", 1)[0] if k.startswith("tongue_rod_block") or k == "tongue_keeper_hi_m" else k
        put(pname, to_sleeve(v), k)
    put("diverter_base", make_diverter_base())
    put("diverter_tray", div_place(make_diverter_tray(), pose["diverter"]))
    for i, a in enumerate(DIV_ANGS):
        put("bin", bin_place(make_bin(), a), f"bin_{'abc'[i]}")
    ext = frame()
    for i, x in enumerate(POSTS_X):
        for s in (-1, 1):
            cb = make_corner_bracket()
            m = cb
            put("corner_bracket", m.translate((x + 10, s * RAIL_Y - 10, 0)), f"corner_bracket_{i}{'mp'[s > 0]}")
    for i, (x, y) in enumerate(((FRAME_X[0] + 15, FRAME_Y[0] + 10), (FRAME_X[0] + 15, FRAME_Y[1] - 10),
                                (FRAME_X[1] - 15, FRAME_Y[0] + 10), (FRAME_X[1] - 15, FRAME_Y[1] - 10),
                                (350.0, FRAME_Y[0] + 10), (350.0, FRAME_Y[1] - 10))):
        put("frame_foot", make_frame_foot().mirror((0, 0, 1)).translate((x, y, -20.0)), f"frame_foot_{i}")
    put("feed_motor_mount", make_feed_motor_mount())
    put("elec_plate_a", make_elec_plate(ELEC_A_X, BOARDS_A))
    put("elec_plate_b", make_elec_plate(ELEC_B_X, BOARDS_B))
    put("lid_switch_mount", make_lid_switch_mount())
    put("estop_panel", make_estop_panel())
    # rig-only parts (shown in the rig preview pose, not in the machine)
    R = {"rig_push_slot": make_rig_push_slot(), "rig_push_stick": make_push_stick(), "rig_foot": make_rig_foot()}
    singles = {}
    for key, (pname, m) in A.items():
        singles.setdefault(pname, m)
    for k, v in R.items():
        singles[k] = clean(v)
    singles["roller_hub"] = clean(make_hub())
    return A, singles, ext


# ---- checks ------------------------------------------------------------------------
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


# intended contacts / press fits that the overlap check skips
FIT_OK = {("lm8uu", "elevator_platform"), ("rods_elevator", "hopper_back"), ("rods_elevator", "hopper_base"),
          ("rods_elevator", "lm8uu"), ("nema_elevator", "hopper_base"), ("nema_elevator", "elevator_platform"),
          ("nema_elevator", "hopper_back"),
          ("servo_diverter", "diverter_tray"),     # MG90S spline in the tray hub
          ("cup_lift", "lift_arm")}                # M4 cup stem threaded into the arm


def report(A, comps, ext):
    allok = True
    print("-- layout (world x of the card path, z = 0 base frame top)")
    print(f"  card {CARD}: {CW:.0f} x {CL:.0f}, sleeve {SW:.0f} x {SL:.0f}; track z {Z_TRACK:.1f}, deck rails z {Z_DECK:.0f}")
    print(f"  hopper stack x {X_HOP:.0f} (250 cards {STACK_H:.0f} mm, platform z {PLAT_LO:.0f}..{STACK_TOP:.0f}), "
          f"pick cup x {PICK_X0:.0f} -> {PICK_X0 + PICK_STROKE:.0f}")
    print(f"  nips: feed {X_FEED:.0f}, scan_in {X_SCAN_IN:.0f}, scan_out {X_SCAN_OUT:.0f}, xfer {X_XFER:.0f}, "
          f"sleeve entry {X_ENTRY:.0f}, exit {X_EXIT:.0f}")
    gaps = [X_SCAN_IN - X_FEED, X_SCAN_OUT - X_SCAN_IN, X_XFER - X_SCAN_OUT, X_ENTRY - X_XFER]
    gok = max(gaps) < L_MIN
    print(f"  nip spacing {gaps} < shortest card {L_MIN:.0f} -> {ok(gok)}")
    allok &= gok
    print(f"  scan: card stop (leading edge) x {X_STOP:.0f}, camera axis x {X_SCAN:.0f}; CM3 {CM3_HFOV:.0f} x "
          f"{CM3_VFOV:.0f} deg -> WD for 91 mm (H) {WD_H:.1f}, for 66 mm (V) {WD_V:.1f}, min focus "
          f"{CM3_MIN_FOCUS:.0f} -> WD {WD:.1f} mm")
    fh = 2 * WD * math.tan(math.radians(CM3_HFOV / 2))
    fv = 2 * WD * math.tan(math.radians(CM3_VFOV / 2))
    fok = fh >= FIELD[0] and fv >= FIELD[1]
    print(f"  field at WD {fh:.1f} x {fv:.1f} >= {FIELD[0]:.0f} x {FIELD[1]:.0f} -> {ok(fok)}; lens fronts z "
          f"{Z_LENS_TOP:.1f} (top) / {Z_LENS_BOT:.1f} (bottom); LED frames {LED_H:.0f} mm from the card")
    allok &= fok
    hw = (WD - LED_H) * math.tan(math.radians(CM3_HFOV / 2)), (WD - LED_H) * math.tan(math.radians(CM3_VFOV / 2))
    wok = LED_WIN[0] > hw[0] and LED_WIN[1] > hw[1]
    print(f"  LED frame window +-{LED_WIN[0]:.0f} x +-{LED_WIN[1]:.0f} vs field there +-{hw[0]:.1f} x +-{hw[1]:.1f} "
          f"-> {ok(wok)}")
    allok &= wok
    print(f"  sleeve: mouth x {X_MOUTH:.0f}, platen top z {Z_PLATEN:.2f}; shims {Z_SHIM_LO:.2f}/{Z_SHIM_HI:.2f}, "
          f"card in throat z {Z_CARD_S:.2f}..{Z_CARD_S + CARD_T:.2f} -> clearance "
          f"{Z_CARD_S - Z_SHIM_LO - TONGUE_T:.2f} / {Z_SHIM_HI - Z_CARD_S - CARD_T:.2f} mm; throat "
          f"{W_MAX + 2 * TONGUE_CLR:.0f} wide; tongues {TIP_RET:.0f} -> {TIP_IN:.0f} (insert "
          f"{TIP_IN:.0f} mm), top ply lift {LIFT:.1f}")
    print(f"  pusher flap {PUSH_START:.0f} -> {PUSH_START + PUSH_STROKE:.0f} (seats the card at +1.5, sleeved card "
          f"closed end -> {PUSH_START + PUSH_STROKE + 1.2 - 1.5 + SL:.0f}); exit nip "
          f"S {EXIT_S:.0f}")
    print(f"  diverter pivot x {X_DIV:.0f}, tray {DIV_LEN:.0f} @ {DIV_TILT:.0f} deg, bins at {DIV_ANGS} deg")
    print("-- fit (printed parts pairwise, components vs parts; overlap mm3)")
    objs = {k: m for k, (_, m) in A.items()}
    names = list(objs)
    bb = {k: bbox(v) for k, v in objs.items()}
    n_pairs, bad = 0, []
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            if not bbox_hit(bb[a], bb[b]):
                continue
            n_pairs += 1
            ov = (objs[a] ^ objs[b]).volume()
            if ov > 0.5:
                bad.append((ov, a, b))
    cb = {k: bbox(v) for k, v in comps.items()}
    for c, cm in comps.items():
        for p in names:
            if (c, p) in FIT_OK or not bbox_hit(cb[c], bb[p]):
                continue
            n_pairs += 1
            ov = (cm ^ objs[p]).volume()
            if ov > 0.5:
                bad.append((ov, c, p))
    for ov, a, b in sorted(bad, reverse=True):
        print(f"  OVERLAP {a} / {b}: {ov:.1f} mm3")
    print(f"  {n_pairs} pairs checked, {len(bad)} overlaps -> {ok(not bad)}")
    allok &= not bad
    return allok


def orient(m, up):
    r = rot_to_z(up)
    return m.transform(np.hstack([r, np.zeros((3, 1))]))


COLORS = {"hopper": "#3d6fa8", "elevator": "#5b8bc4", "pick": "#2a9d8f", "roller": "#555b61", "track": "#8d99a6",
          "guide": "#e9c46a", "hood": "#1d1f22", "lower": "#1d1f22", "led": "#f4f4f2", "cam": "#c0392b",
          "stop": "#e76f51", "sleeve_deck": "#6c757d", "platen": "#264653", "sleeve": "#f4a261",
          "tongue": "#8338ec", "air": "#00b4d8", "lift": "#2a9d8f", "pusher": "#ef476f", "rig": "#adb5bd",
          "diverter": "#06d6a0", "bin": "#ffd166", "corner": "#777777", "frame": "#777777", "feed": "#777777",
          "elec": "#3a5a40", "elev_switch": "#e76f51", "mag_sensor": "#f4a261", "lid": "#d62828",
          "estop": "#d62828"}


def colour(name):
    for k, v in COLORS.items():
        if name.startswith(k):
            return v
    return "#9aa0a6"


def export(A, singles, comps, ext):
    import trimesh  # noqa: F401
    print("-- STL export (print orientation)")
    stl = os.path.join(OUT, "stl")
    rig = os.path.join(stl, "rig")
    for d in (stl, rig, os.path.join(OUT, "preview")):
        os.makedirs(d, exist_ok=True)
        for f in os.listdir(d):                                  # drop stale exports
            if f.endswith(".stl"):
                os.remove(os.path.join(d, f))
    allok = True
    rows = []
    for name, m in singles.items():
        up, qty, sets = PRINT[name]
        bodies = len(m.decompose())
        tm = to_trimesh(orient(m, up))
        tm.apply_translation(-np.array([tm.bounds[0][0] + tm.extents[0] / 2,
                                        tm.bounds[0][1] + tm.extents[1] / 2, tm.bounds[0][2]]))
        path = os.path.join(stl, f"{name}.stl")
        if "m" in sets:
            tm.export(path)
        if "r" in sets:
            tm.export(os.path.join(rig, f"{name}.stl"))
        side, ang = bed_fit(tm)
        fits = side <= BED - 2 * BED_MARGIN and tm.extents[2] <= BED - BED_MARGIN
        oh = overhang_area(tm)
        good = fits and tm.is_watertight and bodies == 1
        allok &= good
        rows.append((name, qty, sets, tm.extents, tm.volume, oh))
        print(f"  {name:18s} x{qty:<2d} {sets:2s} size {np.round(tm.extents, 1)} fp {side:5.1f}@{ang:2d} "
              f"{tm.volume / 1000:6.1f} cm3 bodies {bodies} watertight {tm.is_watertight} "
              f"overhang {oh:6.0f} mm2 -> {ok(good)}")
    entries = []
    objs = {k: m for k, (_, m) in A.items()}
    groups = {k: "part" for k in objs}
    for k, v in comps.items():
        objs[k], groups[k] = v, "component"
    for k, v in ext.items():
        objs[k], groups[k] = v, "frame"
    for name, m in objs.items():
        to_trimesh(m).export(os.path.join(OUT, "preview", f"{name}.stl"))
        g = groups[name]
        col = colour(name) if g == "part" else "#b0b4b8" if g == "frame" else \
            "#bfe3ff" if name.startswith("glass") else "#f6f1e7" if "card" in name or "sleeve" in name \
            else "#c8ccd0" if "shim" in name else "#202020" if name.startswith("nema") else "#1f6f43"
        op = 0.35 if name.startswith("glass") else 0.6 if name in ("hood",) else 1.0
        entries.append({"name": name, "file": f"preview/{name}.stl", "color": col, "opacity": op,
                        "group": g, "station": station(name, m)})
    with open(os.path.join(OUT, "preview", "manifest.json"), "w") as fh:
        json.dump({"title": f"Card scanner + penny sleever + 3-bin sorter ({CARD} {CW:.0f}x{CL:.0f})",
                   "stations": {"hopper": X_HOP, "feed": X_FEED, "scan": X_SCAN, "xfer": X_XFER,
                                "sleeve": X_MOUTH, "exit": X_EXIT, "diverter": X_DIV},
                   "z_track": Z_TRACK, "parts": entries}, fh, indent=1)
    print(f"  all parts single body + watertight + fit {BED:.0f} bed -> {ok(allok)}")
    return allok, rows


def station(name, m):
    x = (m.bounding_box()[0] + m.bounding_box()[3]) / 2
    for s, x1 in (("hopper", 64), ("feed", 118), ("scan", 262), ("xfer", 348), ("sleeve", 552), ("diverter", 2000)):
        if x < x1:
            return s
    return "diverter"


def main():
    A, singles, ext = build()
    comps = components(POSE)
    a = report(A, comps, ext)
    b, _ = export(A, singles, comps, ext)
    print(f"== ALL CHECKS {ok(a and b)}")


if __name__ == "__main__":
    main()
