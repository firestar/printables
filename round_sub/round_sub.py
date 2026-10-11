"""Round cone-flared folded-port enclosure for Gikfun 2" 4ohm 3W driver (EK1725).

The kerf-bent slot port of a classic box is revolved 360 deg around the
driver and folded several times from the centre out: air leaves the central
chamber under the chamber wall, then snakes up / over / down / under a set
of nested conical ring walls, and exits through an annular mouth around the
driver.  Every wall leans outward (LEAN), so the body fans out like a cone,
and each pass is wider than the last (FLARE), so the port flares toward the
mouth.

Walls alternate: "hanging" walls run floor-to-baffle with pointed-arch
windows at the bottom (air passes under them), "rising" walls stop short of
the baffle (air passes over them).  All walls, the floor and the skin are one
print; fins tie the walls together.  Below the floor is an electronics bay
(BASE cup) for the ESP32 + MAX98357 with a USB-C slot.  The base is the
back: keyhole slots let it hang on a wall, and a WS2812B ring on the
underside of the cone overhang, aimed 45 deg back, lights the wall behind
it as a halo.

Assembly is straight drop-in, no snapping through anything (checked in
main() by sweeping each part along its insertion path):
  1. BODY drops into the BASE socket (cone in cone, like stacking cups).
  2. BAFFLE drops onto the wall tops; inner wall tops locate in grooves.
     Seal with silicone / glue.

Parts (exported in print orientation):
  baffle.stl - flat baffle with speaker mount     (print face-down)
  body.stl   - floor + all ring walls + skin      (print floor-down)
  base.stl   - electronics bay cup                (print as-is)

Run: PYTHONPATH=../.pydeps python3 round_sub.py
"""
import math
import os

import numpy as np
import manifold3d as m3d

SEG = 192
OUT = os.path.dirname(os.path.abspath(__file__))

# ---- parameters (mm) -------------------------------------------------------
R_TOP = 110.0         # outer radius at the top rim (220 mm OD)
LEAN = 20.0           # cone half-angle of every wall, deg from vertical
T = 2.4               # outer skin / floor / baffle thickness
TW = 1.6              # ring wall thickness
N_RINGS = 5           # port passes (odd: last pass runs up to the mouth)
FLARE = 1.10          # each pass has this much more area than the previous
FB_TARGET = 178.0     # port tuning the solver aims for, Hz (driver Fs ~190)
TURN = 1.15           # turn gaps are this much wider than the pass gap
CLR = 0.4             # FDM sliding-fit clearance per side
HOLE_COMP = 0.2       # FDM holes print small: added to small hole diameters
EF = 0.6              # elephant-foot chamfer on mating edges at the bed
SEAT = 1.2            # hanging-wall tops sit this deep in baffle grooves
POST = 4.0            # width of the posts between the under-wall windows
FLOOR = 3.0           # MID floor thickness
BAFFLE = 4.0          # TOP baffle thickness
PORT_H = 40.0         # floor top to baffle underside (flat disk)
SPK_HOLE = 51.0       # cutout: clears the 50.8 mm surround (rear mounted)
SPK_FRAME = 52.6      # square frame per Gikfun drawing (pocket adds CLR per side)
SPK_POCKET = 2.0      # pocket depth under the baffle, locates the frame
SPK_SCREW = 42.0      # corner hole spacing per Gikfun drawing (square pattern)
SPK_SCREW_D = 3.0     # screw hole (M2.5 clearance / M3 self-tap), + HOLE_COMP
SPK_VOL = 25e3        # approx volume displaced by the driver, mm^3
WIRE_HOLE = 8.0       # speaker wire hole through the floor centre

BAY_H = 28.0          # bay height (cup floor top to MID floor underside)
BASE_T = 8.0          # cup floor thickness (holds the LED groove)
BASE_WALL = 2.4
SOCKET = 6.0          # how far MID sits down inside the cup socket
HALO_W = 16.0         # LED band width incl. lips: 13 mm channel for 12 mm strip
HALO_LIP = 4.0        # retaining lip height either side of the strip
HALO_LIP_T = 1.5      # lip thickness
HALO_GAP = 4.0        # band starts this far above the base socket
HALO_WIRE_ANG = 200.0 # LED lead enters the bay through the wall here
HALO_SLOT = (12.0, 7.0)  # lead slot w x h: passes the strip's JST-SM 3-pin plug
CLIP_GAP = 5.0        # wire guide gap (fits ~6 x 26 AWG wires)
CLIP_H = 9.0          # wire guide post height
KEY_X = -20.0         # keyhole entry centre X (slots run toward -X = up)
KEY_SPACING = 100.0   # keyhole spacing (along Y = level on the wall)
KEY_HEAD = 9.5        # screw head clearance (up to ~8.5 mm heads)
KEY_SHANK = 5.0       # screw shank slot width (up to M4 / #8)
KEY_SLOT = 10.0       # slot travel
MIC_ANGS = (90.0, 270.0)  # INMP441 mics: left/right side walls when wall mounted
MIC_PCB_D = 14.0      # round INMP441 board (B0C1C64R8S), sound hole centred
MIC_POCKET = MIC_PCB_D + 2.4   # mount block size driver (pocket is round)
MIC_RELIEF = 1.5      # recess behind the board for solder joints
MIC_RING = 6.0        # raised seal ring around the sound hole (OD)
MIC_DEPTH = 5.0       # pocket depth (board + gasket, glue in place)
MIC_HOLE = 2.0        # sound hole through the wall
MIC_Z = 16.0          # mic centre height in the bay
# Hosyond ESP32 devkit: 30-pin, 51 x 28 mm, pins pre-soldered pointing down.
# Ledge 20 mm clears the pins plus female Dupont housings underneath.
ESP_L, ESP_W, ESP_LEDGE = 51.5, 28.4, 20.0
# MAX98357A breakout: 18.0 x 20.1 mm (listing), 7-pin header on one edge,
# screw terminal on top.  Sits on a 10 mm platform; header edge overhangs.
AMP_L, AMP_W = 20.1, 18.0
AMP_PLAT_H = 10.0     # clears header pins soldered pointing down
AMP_PLAT_D = 14.0     # platform depth: header row (outer 2.5 mm) hangs off the edge
AUX_ANG = 150.0

SLOPE = math.tan(math.radians(LEAN))        # dr/dz of every wall
COS = math.cos(math.radians(LEAN))
Z_FLOOR = BAY_H                             # MID floor bottom (cup floor top = 0)
Z_F = Z_FLOOR + FLOOR                       # floor top (wall reference height)
Z_B = Z_F + PORT_H                          # baffle underside
H = Z_B + BAFFLE                            # top of the enclosure
Z_MID = Z_F + PORT_H / 2


def skin_r(z):
    """Outer surface radius of the skin at height z."""
    return R_TOP - SLOPE * (H - z)


def at(r_ref, z):
    """Radius at height z of a cone surface that is r_ref at the floor top."""
    return r_ref + SLOPE * (z - Z_F)


def ring_layout(a0):
    """Passes [(r_in, r_out)] and walls [(r_in, r_out)] centre-out, as
    horizontal radii at the floor top.  Pass k has area a0 * FLARE**k
    (normal to the walls, at mid-height).  walls[0] is the chamber wall."""
    passes, walls = [], []
    r = skin_r(Z_MID) - T / COS                     # skin inner face at mid-height
    for k in reversed(range(N_RINGS)):
        area = a0 * FLARE ** k
        g = area / (2 * math.pi * r * COS)
        for _ in range(5):
            g = area / (2 * math.pi * (r - g / 2) * COS)
        passes.append((r - g, r))
        walls.append((r - g - TW / COS, r - g))
        r = r - g - TW / COS
    shift = SLOPE * PORT_H / 2                       # mid-height -> floor top
    pas = [(a - shift, b - shift) for a, b in passes[::-1]]
    wal = [(a - shift, b - shift) for a, b in walls[::-1]]
    return pas, wal


def acoustics_for(a0):
    passes, walls = ring_layout(a0)
    r1, r2 = walls[0][0], at(walls[0][0], Z_B)
    v = math.pi * PORT_H / 3 * (r1 * r1 + r1 * r2 + r2 * r2) - SPK_VOL
    v *= 1e-9
    mass = 0.0                                       # sum of L/A over passes
    length = 0.0
    for k in range(N_RINGS):
        lk = PORT_H / COS + (passes[k][1] - passes[k][0])
        ak = a0 * FLARE ** k
        mass += lk / ak
        length += lk
    mass += 1.7 * math.sqrt(a0 * FLARE ** (N_RINGS - 1) / math.pi) / (a0 * FLARE ** (N_RINGS - 1))
    fb = 343 / (2 * math.pi) * math.sqrt(1 / (v * mass * 1e3))
    return v * 1e6, length, fb


def solve_area():
    lo, hi = 100.0, 3000.0
    for _ in range(60):
        mid = (lo + hi) / 2
        if acoustics_for(mid)[2] < FB_TARGET:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


A0 = solve_area()
PASSES, WALLS = ring_layout(A0)
R_CH = WALLS[0][0]                          # chamber radius at the floor


def hangs(k):
    """Wall k hangs from the baffle (even) or rises from the floor (odd)."""
    return k % 2 == 0


def turn_gap(r):
    """Vertical turn clearance so the bend keeps the pass area."""
    return TURN * A0 * 1.3 / (2 * math.pi * r)


def revolve(poly, seg=SEG):
    return m3d.Manifold.revolve(m3d.CrossSection([poly]), seg)


def cone(r0, r1, z0, z1):
    """Conical wall between reference radii r0..r1 (at floor top), z0..z1."""
    return revolve([(at(r0, z0), z0), (at(r1, z0), z0),
                    (at(r1, z1), z1), (at(r0, z1), z1)])


def tube(r0, r1, z0, z1):
    return revolve([(r0, z0), (r1, z0), (r1, z1), (r0, z1)])


def cyl(h, r, z=0.0, x=0.0, y=0.0, seg=64):
    return m3d.Manifold.cylinder(h, r, r, seg).translate((x, y, z))


def box(x0, x1, y0, y1, z0, z1):
    return m3d.Manifold.cube((x1 - x0, y1 - y0, z1 - z0)).translate((x0, y0, z0))


def polar(r, ang):
    a = math.radians(ang)
    return r * math.cos(a), r * math.sin(a)


def vol(m):
    return m.volume() if hasattr(m, "volume") else m.get_properties().volume


def fin(r0, r1, z0, z1, ang, w):
    """Thin radial fin following the cone between reference radii r0..r1."""
    poly = [(at(r0, z0), z0), (at(r1, z0), z0), (at(r1, z1), z1), (at(r0, z1), z1)]
    m = m3d.CrossSection([poly]).extrude(w).translate((0, 0, -w / 2))
    return m.rotate((90, 0, 0)).rotate((0, 0, ang))


def window_cutter(r_lo, r_hi, z0, w, hr):
    """Pointed-arch window (45 deg top, printable) cut radially through a wall."""
    poly = [(-w / 2, z0 - 1), (w / 2, z0 - 1), (w / 2, z0 + hr),
            (0, z0 + hr + w / 2), (-w / 2, z0 + hr)]
    m = m3d.CrossSection([poly]).extrude(r_hi - r_lo)
    # (u, v, t) -> (t, u, v): extrusion axis becomes radial X
    return m.rotate((90, 0, 0)).rotate((0, 0, 90)).translate((r_lo, 0, 0))


# ---- BAFFLE: flat disc, drops onto the hanging-wall tops --------------------
def make_baffle():
    last = max(k for k in range(len(WALLS)) if hangs(k))
    rb = at(WALLS[last][1], Z_B)
    baffle = revolve([(0, Z_B), (rb, Z_B), (rb, H - 0.8), (rb - 0.8, H), (0, H)])
    baffle = baffle - cyl(BAFFLE + 2, SPK_HOLE / 2, z=Z_B - 1, seg=96)
    # square frame pocket on the underside + 4 corner screw holes
    f = SPK_FRAME / 2 + CLR
    baffle = baffle - box(-f, f, -f, f, Z_B - 1, Z_B + SPK_POCKET)
    for sx in (-1, 1):
        for sy in (-1, 1):
            baffle = baffle - cyl(BAFFLE + 2, (SPK_SCREW_D + HOLE_COMP) / 2, z=Z_B - 1,
                                  x=sx * SPK_SCREW / 2, y=sy * SPK_SCREW / 2, seg=24)
    # locating grooves for the inner hanging-wall tops
    for k, (r0, r1) in enumerate(WALLS):
        if hangs(k) and k != last:
            gi, go = at(r0, Z_B) - CLR, at(r1, Z_B + SEAT) + CLR
            zt = Z_B + SEAT + 0.3
            baffle = baffle - revolve([(gi - EF, Z_B - 1), (go + EF, Z_B - 1),
                                       (go + EF, Z_B), (go, Z_B + EF), (go, zt),
                                       (gi, zt), (gi, Z_B + EF), (gi - EF, Z_B)])
    return baffle


# ---- BODY: floor + every ring wall + outer skin, one print -----------------
def make_body():
    rf = skin_r(Z_FLOOR)
    body = tube(0, rf, Z_FLOOR, Z_F)
    body = body - revolve([(rf - EF, Z_FLOOR - 1), (rf + 1, Z_FLOOR - 1),
                           (rf + 1, Z_FLOOR + EF + 1)])
    body = body + revolve([(rf - T / COS, Z_FLOOR), (rf - EF, Z_FLOOR), (rf, Z_FLOOR + EF),
                           (R_TOP, H), (R_TOP - T / COS + 1.2, H),   # mouth flare
                           (R_TOP - T / COS, H - 1.2)])
    last = max(k for k in range(len(WALLS)) if hangs(k))
    for k, (r0, r1) in enumerate(WALLS):
        if not hangs(k):                    # rising wall: open over the top
            body = body + cone(r0, r1, Z_F - 0.01, Z_B - turn_gap(at(r1, Z_B)))
            continue
        # "hanging" wall: floor to baffle, air passes under it through windows
        top = Z_B if k == last else Z_B + SEAT
        wall = cone(r0, r1, Z_F - 0.01, top)
        rb = at(r0, Z_F)
        n = max(6, int(2 * math.pi * rb / 18))
        w = 2 * math.pi * rb / n - POST
        area = TURN * A0 * FLARE ** k
        hr = area / (n * w)
        cutter = window_cutter(rb - 2, at(r1, Z_F + hr + w / 2) + 2, Z_F, w, hr)
        for j in range(n):
            wall = wall - cutter.rotate((0, 0, 360 * j / n))
        body = body + wall
    # tie fins across every pass (stiffen the thin walls while printing)
    for k, (p0, p1) in enumerate(PASSES):
        n = 4 if k == 0 else 6
        for j in range(n):
            body = body + fin(p0 - 0.3, p1 + 0.3, Z_F - 0.01, Z_B,
                              360 / n * j + 7 * k, 1.2)
    body = body + halo_collar()
    body = body - cyl(FLOOR + 2, (WIRE_HOLE + HOLE_COMP) / 2, z=Z_FLOOR - 1)
    return body


def halo_collar():
    """Ring band on the underside of the cone overhang that holds the LED
    strip facing 45 deg back/out, so a wall-mounted unit throws a halo on the
    wall.  Every face is <= 45 deg overhang, so it prints with the body."""
    u = np.array([1.0, 1.0]) / math.sqrt(2)        # along the band (out + up)
    n = np.array([1.0, -1.0]) / math.sqrt(2)       # LED facing (out + back)
    z0 = Z_FLOOR + SOCKET + HALO_GAP
    p = np.array([skin_r(z0), z0])
    q = p + HALO_W * u
    t = (q[0] - skin_r(q[1])) / (1 + SLOPE)         # top face back to the skin
    e = q + t * np.array([-1.0, 1.0])
    lt = HALO_LIP_T
    poly = [p - [1.0, 0], p, p + HALO_LIP * n, p + HALO_LIP * n + lt * u, p + lt * u,
            q - lt * u, q - lt * u + HALO_LIP * n, q + HALO_LIP * n, q, e, e - [1.0, 0]]
    return revolve([tuple(v) for v in poly])


def mic_mount(rb_in, rb_out):
    """Block on the inside of the bay wall (at +X) holding a mic pocket.
    45 deg underside so it prints without supports."""
    h = MIC_POCKET / 2 + 1.6
    d = MIC_DEPTH + 0.5
    poly = [(rb_in + 0.5, MIC_Z + h), (rb_in - d, MIC_Z + h),
            (rb_in - d, MIC_Z - h), (rb_in + 0.5, MIC_Z - h - d - 0.5)]
    m = m3d.CrossSection([poly]).extrude(2 * h).translate((0, 0, -h))
    return m.rotate((90, 0, 0))


def mic_cut(rb_in, rb_out):
    """Round pocket for the board.  The board's labelled face (sound hole)
    faces the wall and rests on a raised ring around the hole; a shallow
    relief around the ring clears the solder joints on that face."""
    seat = rb_in - 0.4
    axis = lambda m, x: m.rotate((0, 90, 0)).translate((x, 0, MIC_Z))
    r_p = MIC_PCB_D / 2 + CLR
    cut = axis(m3d.Manifold.cylinder(MIC_DEPTH + 1, r_p, r_p, 64), seat - MIC_DEPTH - 1)
    relief = (m3d.Manifold.cylinder(MIC_RELIEF + 0.01, r_p - 0.5, r_p - 0.5, 64)
              - m3d.Manifold.cylinder(MIC_RELIEF + 0.01, MIC_RING / 2, MIC_RING / 2, 48))
    cut = cut + axis(relief, seat - 0.005)
    hole = m3d.Manifold.cylinder(rb_out - seat + 2, (MIC_HOLE + HOLE_COMP) / 2,
                                 (MIC_HOLE + HOLE_COMP) / 2, 24)
    cut = cut + axis(hole, seat - 0.5)
    cham = m3d.Manifold.cylinder(1.2, MIC_HOLE / 2, MIC_HOLE / 2 + 1.2, 24)
    return cut + axis(cham, rb_out - 1.0)

# ---- BASE: electronics bay cup ---------------------------------------------
def make_base():
    rs = skin_r(Z_FLOOR)                     # MID skin radius where it sits
    rb_in = rs - T / COS                     # bay inner radius
    rb_out = rs + CLR + BASE_WALL
    z0 = -BASE_T
    base = tube(0, rb_out, z0, 0)
    base = base + tube(rb_in, rb_out, -0.01, Z_FLOOR)              # bay wall, MID seat
    zs = Z_FLOOR + SOCKET                    # socket flares with the skin
    base = base + revolve([(rs + CLR, Z_FLOOR - 0.01), (rb_out, Z_FLOOR - 0.01),
                           (skin_r(zs) + CLR + BASE_WALL, zs), (skin_r(zs) + CLR, zs)])
    # wall-mount keyholes in the back (bottom) face; slots run toward -X (up
    # on the wall), so the USB-C slot at +X ends up facing down
    for ky in (-KEY_SPACING / 2, KEY_SPACING / 2):
        kx = KEY_X
        base = base - cyl(BASE_T - 1, KEY_HEAD / 2, z=z0 - 1, x=kx, y=ky)
        base = base - box(kx - KEY_SLOT, kx, ky - KEY_SHANK / 2, ky + KEY_SHANK / 2,
                          z0 - 1, z0 + 3.01)
        base = base - box(kx - KEY_SLOT, kx, ky - KEY_HEAD / 2, ky + KEY_HEAD / 2,
                          z0 + 3, -1.0)
        base = base - cyl(-1.0 - (z0 + 3), KEY_HEAD / 2, z=z0 + 3, x=kx - KEY_SLOT, y=ky)
    # halo LED wire hole through the bay wall, just under the cone overhang
    x, y = polar(rb_out, HALO_WIRE_ANG)
    sw, sh = HALO_SLOT
    hw = m3d.Manifold.cube((16, sw, sh), True)
    base = base - hw.rotate((0, 0, HALO_WIRE_ANG)).translate((x, y, Z_FLOOR - sh / 2 - 1.5))
    # ESP32 cradle: ledges under the two short (pin-free) edges, USB to +X
    xu = rb_in - 3.0
    xa = xu - ESP_L
    base = base + box(xu - 3, xu, -9, 9, -0.01, ESP_LEDGE)
    base = base + box(xa, xa + 3, -9, 9, -0.01, ESP_LEDGE)
    base = base + box(xa - CLR - 1.6, xa - CLR, -9, 9, -0.01, ESP_LEDGE + 3)  # end stop
    # USB-C access slot facing the ESP32 USB end
    usb_z = ESP_LEDGE + 1.6 + 1.6
    base = base - box(rb_in - 2, rb_out + 2, -7, 7, usb_z - 5, usb_z + 5)
    # aux cable hole (external 5 V / extra wiring)
    x, y = polar(rb_out, AUX_ANG)
    aux = m3d.Manifold.cylinder(14, 4.0, 4.0, 48, True).rotate((0, 90, 0))
    base = base - aux.rotate((0, 0, AUX_ANG)).translate((x, y, 12))
    # INMP441 mic pockets: flat seat against a sound hole in each side wall
    for ang in MIC_ANGS:
        base = base + mic_mount(rb_in, rb_out).rotate((0, 0, ang))
        base = base - mic_cut(rb_in, rb_out).rotate((0, 0, ang))
    # MAX98357 pocket
    cx = xa - 22.0
    # board edge with the header faces +X and overhangs the platform
    aw = max(AMP_L, AMP_W) / 2 + CLR          # fits either board orientation
    x0 = cx - AMP_PLAT_D / 2
    pocket = box(x0, x0 + AMP_PLAT_D, -aw, aw, -0.01, AMP_PLAT_H)
    pocket = pocket + box(x0 - 1.6, x0, -aw - 1.6, aw + 1.6, -0.01, AMP_PLAT_H + 2.5)
    for sy in (-1, 1):
        pocket = pocket + box(x0 - 1.6, x0 + AMP_PLAT_D, sy * aw - (1.6 if sy < 0 else 0),
                              sy * aw + (1.6 if sy > 0 else 0), -0.01, AMP_PLAT_H + 2.5)
    base = base + pocket
    # wire guides along each cable run
    for (x, y, ang) in wire_routes(rb_in):
        base = base + wire_clip().rotate((0, 0, ang)).translate((x, y, 0))
    return base


def wire_routes(rb_in):
    """(x, y, direction) of each wire clip on the bay floor."""
    lx, ly = polar(rb_in - 12, HALO_WIRE_ANG)      # LED lead slot
    px, py = polar(rb_in - 12, AUX_ANG)            # 5 V input hole
    return [
        (0, 68, -90), (22, 34, -55),               # left mic  -> ESP32
        (0, -68, 90), (22, -34, 55),               # right mic -> ESP32
        (lx, ly, 15), (-30, -26, 0), (4, -26, 10), # LED lead  -> GPIO27 / 5 V
        (px, py, -15), (-30, 30, -10), (4, 26, -10),  # 5 V in -> ESP32 VIN / amp
    ]


def wire_clip():
    """Two posts with 45 deg retaining nubs: press wires into the gap.
    Local frame: wires run along +X."""
    g, t, L, h = CLIP_GAP, 2.4, 4.0, CLIP_H
    clip = None
    for s in (1, -1):
        post = box(-L / 2, L / 2, s * g / 2 - (t if s < 0 else 0),
                   s * g / 2 + (t if s > 0 else 0), -0.01, h)
        nub = [(s * (g / 2 + 0.5), h - 2.5), (s * (g / 2 - 1.0), h - 1.0),
               (s * (g / 2 + 0.5), h)]
        if s > 0:                           # keep the triangle counter-clockwise
            nub = nub[::-1]
        n = m3d.CrossSection([nub]).extrude(L)
        n = n.rotate((90, 0, 0)).rotate((0, 0, 90)).translate((-L / 2, 0, 0))
        part = post + n
        clip = part if clip is None else clip + part
    return clip


def acoustics():
    return acoustics_for(A0)


def to_trimesh(m):
    import trimesh
    mesh = m.to_mesh()
    verts = np.asarray(mesh.vert_properties)[:, :3]
    return trimesh.Trimesh(verts, np.asarray(mesh.tri_verts), process=False)


def assembly_check(moving, fixed, travel, step=0.5):
    """Lower `moving` straight down onto `fixed` from `travel` mm above.
    Returns (max overlap along the path, overlap when pushed 0.3 mm past seat).
    First must be ~0 (it slides in freely); second > 0 proves it seats."""
    worst = 0.0
    for d in np.arange(travel, -1e-9, -step):
        worst = max(worst, vol(moving.translate((0, 0, d)) ^ fixed))
    wiggle = 0.0                              # seated, nudged sideways
    for a in range(0, 360, 45):
        dx, dy = polar(0.9 * CLR, a)
        wiggle = max(wiggle, vol(moving.translate((dx, dy, 0.05)) ^ fixed))
    return worst, vol(moving.translate((0, 0, -0.3)) ^ fixed), wiggle


def main():
    baffle, body, base = make_baffle(), make_body(), make_base()
    v_cm3, length, fb = acoustics()
    print(f"chamber r={R_CH:.1f} (floor) -> {at(R_CH, Z_B):.1f} (baffle)")
    for k, p in enumerate(PASSES):
        print(f"  pass {k + 1}: r {p[0]:.1f}-{p[1]:.1f} at floor, "
              f"gap {(p[1] - p[0]) * COS:.2f} normal, area {A0 * FLARE ** k:.0f} mm^2")
    print(f"net volume  {v_cm3:6.0f} cm^3")
    print(f"port length {length:.0f} mm ({N_RINGS} passes), flare x{FLARE ** (N_RINGS - 1):.2f}")
    print(f"tuning Fb   {fb:6.0f} Hz")
    r_halo = skin_r(Z_FLOOR + SOCKET + HALO_GAP) + HALO_W / 2 / math.sqrt(2)
    print(f"halo strip  {2 * math.pi * r_halo:.0f} mm (~{2 * math.pi * r_halo * 0.06:.0f} LEDs @60/m)")
    for name, mv, fx, travel in [("body -> base", body, base, 60.0),
                                 ("baffle -> body", baffle, body + base, 30.0)]:
        path, seat, wig = assembly_check(mv, fx, travel)
        ok = path < 1e-3 and seat > 1e-3 and wig < 1e-3
        print(f"assembly {name:15s} path overlap {path:.4f} mm^3, "
              f"seated {seat:.1f} mm^3, {0.9 * CLR:.2f} mm wiggle {wig:.4f} mm^3 "
              f"-> {'OK' if ok else 'FAIL'}")

    flip = lambda m: m.rotate((180, 0, 0))
    parts = {"baffle": flip(baffle), "body": body, "base": base}
    os.makedirs(os.path.join(OUT, "preview"), exist_ok=True)
    for name, m in parts.items():
        tm = to_trimesh(m)
        tm.apply_translation(-np.array([0, 0, tm.bounds[0][2]]))   # sit on bed
        tm.export(os.path.join(OUT, f"{name}.stl"))
        print(f"{name:6s} watertight={tm.is_watertight} tris={len(tm.faces)} "
              f"size={np.round(tm.extents, 1)}")
    # assembled-position copies for the viewer
    for name, m in {"baffle": baffle, "body": body, "base": base}.items():
        to_trimesh(m).export(os.path.join(OUT, "preview", f"{name}.stl"))
    return baffle, body, base

if __name__ == "__main__":
    main()
