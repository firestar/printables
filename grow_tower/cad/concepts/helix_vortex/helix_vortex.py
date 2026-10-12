"""Helix Vortex: a twisted 6-lobe star grow tower with a spiral NFT gutter.

Concept tower for the rotating grow tower (see ../BRIEF.md).  Only the turning
stack and its water path differ from the classic design; the stand, tank, lid,
drive and rotor come unchanged from grow_tower.py.

  TIER x 6   6-lobe star (r 76..100, 24 mm deep V valleys) whose outline twists
             continuously, 25 deg per tier, so lobes and valleys run as
             unbroken helices up the whole stack.  Every tier is identical and
             is placed 25 deg further round than the one below.  A collar on
             each tier top carries the lobes up over the 45 deg neck of the
             tier above (1 mm seam), so the joints don't break the spiral.
             The six ports sit on the lobes (pot lip drops into a scoop cut in
             the lobe above the mouth).
             Inside each tier a V-gutter (wall + 45 deg flank) winds round at
             3 % slope, starting high and ending low.  In the valleys its outer
             side is the wall; where a lobe bulges further out, the corner
             rides the 45 deg bottom funnel instead.  Each port follows the
             gutter down and its pot base hangs 5-15 mm over the flow.
             At its end the gutter pours onto the tier's inner shoulder; the
             water runs down the spigot and drips 25 deg further on, which
             (because of the 25 deg twist) is exactly the start of the gutter
             in the tier below.  6 turns of NFT gutter, 6 small cascades.
  HEADER     port-less 7th ring with the same gutter.  The fixed spray head
             squirts at its wall; the gutter collects it and feeds tier 6.
  CAP        base cap with a star plate, bushing on the spray-head stub.
  keys       a tooth in every socket and a slot in every spigot fix the
             25 deg indexing (the rotor has no tooth, so tier 1 goes anywhere).

The gutter is printed with the tier (spigot down): its underside is a 45 deg
flank, the ports are 45 deg tubes, the twisted lobes lean < 15 deg and the
collar's inside is an upward-opening cone, so nothing needs support.  If a
gutter clogs, water spills over the lip (r <= 62 mm, inside every spigot) and
falls straight to the rotor funnel and the lid drain.

Run: env PYTHONPATH=/home/infra/printables/.pydeps python3 \\
     grow_tower/cad/concepts/helix_vortex/helix_vortex.py
"""
import math
import os
import sys

import numpy as np
import manifold3d as m3d

HERE = os.path.dirname(os.path.abspath(__file__))
CAD = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, CAD)
import grow_tower as gt  # noqa: E402
from grow_tower import CLR, EF, ok, revolve, union, vol  # noqa: E402

S2 = math.sqrt(2.0)
R_TI, R_TO, R_SO, R_SI = gt.R_TI, gt.R_TO, gt.R_SO, gt.R_SI
SPIG_L, SEAT_DROP, RIM_CH = gt.SPIG_L, gt.SEAT_DROP, gt.RIM_CH

# ---- parameters (mm, deg) ----------------------------------------------------
N_TIERS, N_PORT = 6, 6
PITCH = 116.0            # tier-to-tier spacing once seated
TWIST = 25.0             # outline twist and placement step per tier
TIER_H = PITCH + SEAT_DROP
LOBE_A = 12.0            # 6-lobe star: r = R + A lobe(theta), 24 mm deep valleys
LOBE_P = 0.6             # < 1: fat lobes, sharp V valleys (crisp helical grooves)
WALL = R_TO - R_TI       # 3.4 radial
SOCK_BAND = SPIG_L + SEAT_DROP + 2.0   # round socket bore at the top of a tier
SEG_PETAL = 360

SLOPE = 0.03             # gutter fall along the corner (NFT 2-5 %)
GUT_W = 26.0             # flank width (radial = height, 45 deg)
GUT_T = 2.4              # flank plate thickness
GUT_T45 = GUT_T * S2     # its vertical thickness
SHOULDER_CLR = 1.0       # gutter floor above the inner spigot shoulder (valleys)
PSI_LAND = 8.0           # drip from the tier above lands here
PSI_END = 360.0 + PSI_LAND - TWIST     # gutter end (338 deg after its start)
PORT_GAP = 24.5          # first port this far (deg) after the landing drip
DAM_T, DAM_H = 3.0, 8.0

BORE_R = gt.PORT_ID / 2
PORT_RO = BORE_R + gt.PORT_WALL
PORT_L = gt.PORT_L       # wall to mouth along the axis (mouth at r = 102)
WIN_GAP = 2.0            # port window bottom above the gutter floor
POT_R, POT_L = 25.0, 50.0  # 2" net pot body radius, length under the lip
SCOOP_R = 31.0           # lobe cut away above the mouth so the pot lip drops in
COLLAR_H, COLLAR_G = 24.0, 1.0   # lobes carried up over the next tier's 45 deg neck

TOOTH_HW = 3.0           # key tooth half width (tangential)
SLOT_HW = TOOTH_HW + 0.5
TOOTH_OFF = 15.0         # tooth sits on a lobe flank, clear of the pots

TIER_Z0 = gt.Z_RT - SEAT_DROP          # tier 1 seat (same socket as classic)
HEAD_Z = TIER_Z0 + N_TIERS * PITCH     # header seat


# ---- layout of the gutter and the ports ---------------------------------------
def tw(z):
    """Outline twist (deg) at tier-local height z."""
    return TWIST * np.asarray(z, dtype=float) / PITCH


def r_in(phi, z):
    """Inner wall radius at local angle phi (deg), local height z."""
    return R_TI + LOBE_A * lobe(np.asarray(phi) - tw(z))


def lobe(x):
    """Star profile 0..2 at angle x (deg), lobe tips at x = 0, 60, ..."""
    c = np.clip((1 + np.cos(np.radians(6 * np.asarray(x, dtype=float)))) / 2, 0.0, 1.0)
    return 2.0 * c ** LOBE_P


def r_corner(phi, z):
    """Gutter corner: on the wall in the valleys, on the 45 deg bottom funnel
    (r = R_SI + z) where a lobe reaches further out."""
    return np.minimum(r_in(phi, z), R_SI + np.asarray(z, dtype=float))


def schedule(z_cs, phi_s, n=1801):
    """Gutter corner along psi (deg from its start): floor z, wall r, arc."""
    psi = np.linspace(0.0, PSI_END, n)
    z = np.full(n, z_cs)
    for _ in range(3):
        r = r_corner(phi_s + psi, z)
        a = np.radians(phi_s + psi)
        seg = np.hypot(np.diff(r * np.cos(a)), np.diff(r * np.sin(a)))
        arc = np.concatenate([[0.0], np.cumsum(seg)])
        z = z_cs - SLOPE * arc
    return psi, z, r_corner(phi_s + psi, z), arc


def port_layout(phi_s, psi_t, zc_t):
    """(local angle, axis z at r = R_TI, gutter floor z, psi) per port, sorted
    along the gutter.  Ports sit on the lobes and follow the gutter down."""
    out = []
    for j in range(N_PORT):
        zp = float(zc_t[0]) + WIN_GAP + BORE_R * S2
        for _ in range(6):
            phi = 60.0 * j + float(tw(zp))
            psi = (phi - phi_s) % 360.0
            zc = float(np.interp(psi, psi_t, zc_t))
            zp = zc + WIN_GAP + BORE_R * S2
        out.append((phi, zp, zc, psi))
    return sorted(out, key=lambda q: q[3])


def solve_layout():
    """Lowest gutter start that keeps the floor above the spigot shoulder in
    the valleys; start angle so the first lobe port is PORT_GAP past the
    landing drip."""
    z_cs, phi_s = 20.0, 0.0
    for _ in range(8):
        psi, z, r, arc = schedule(z_cs, phi_s)
        z_cs = math.ceil((R_TI - R_SI + SHOULDER_CLR + SLOPE * arc[-1]) * 10) / 10
        ports = port_layout(phi_s, psi, z)
        phi_s += ports[0][3] - (PSI_LAND + PORT_GAP)
    return (z_cs, phi_s) + schedule(z_cs, phi_s)


Z_CS, PHI_S, PSI, ZC, RW, ARC = solve_layout()
LIP_MAX = Z_CS + GUT_W


def zc_at(psi):
    return float(np.interp(psi, PSI, ZC))


def rw_at(psi):
    return float(np.interp(psi, PSI, RW))


PORTS = port_layout(PHI_S, PSI, ZC)
WIN_TOP = max(zp + BORE_R * S2 for _, zp, _, _ in PORTS)

# top: the spray head jets hit the header wall above its gutter lip
JET_LOCAL = LIP_MAX + 5.0
SPRAY_Z = HEAD_Z + JET_LOCAL - 6.0        # pipe top (jets are 6 mm higher)
CAP_Z = SPRAY_Z + 31.0                    # same stub/bushing relation as classic
P_H = CAP_Z - HEAD_Z                      # header seat-to-cap-seat
TIER_H_H = P_H + SEAT_DROP
PIPE_LEN = SPRAY_Z - gt.PIPE_Z0


# ---- geometry helpers -------------------------------------------------------------
def at(r, t, z, ang):
    a = math.radians(ang)
    return (r * math.cos(a) - t * math.sin(a), r * math.sin(a) + t * math.cos(a), z)


def petal_cs(off, rot):
    th = np.radians(np.arange(SEG_PETAL) * 360.0 / SEG_PETAL)
    r = R_TI + off + LOBE_A * lobe(np.degrees(th))
    a = th + math.radians(rot)
    return m3d.CrossSection([list(zip(r * np.cos(a), r * np.sin(a)))])


def petal_prism(off, z0, z1):
    """Twisted soft-hex prism (inner wall offset by off) from z0 to z1."""
    n = max(1, int(round((z1 - z0) / 3.0)))
    m = petal_cs(off, float(tw(z0))).extrude(z1 - z0, n, TWIST * (z1 - z0) / PITCH)
    return m.translate((0, 0, z0))


def cone_up(r0, h):
    """Solid r <= r0 + z for 0 <= z <= h (45 deg)."""
    return revolve([(0, 0), (r0, 0), (r0 + h, h), (0, h)])


def shell(h_top):
    """Tier shell with seat at z = 0, rim at h_top: returns (solid, void)."""
    big = h_top + 40
    outer = petal_prism(WALL, 0.0, h_top) ^ cone_up(R_SO, big)
    spig = revolve([(0, -SPIG_L), (R_SO - EF, -SPIG_L), (R_SO, -SPIG_L + EF),
                    (R_SO, 0.01), (0, 0.01)])
    zb = h_top - SOCK_BAND
    soft = petal_prism(0.0, -1.0, h_top + 1) ^ revolve(
        [(0, -1), (R_TI + zb + 1, -1), (R_TI, zb), (0, zb)])    # 45 deg under the band
    rnd = gt.cyl(h_top + 2, R_TI, z=-1, seg=gt.SEG)
    void = (soft + rnd) ^ cone_up(R_SI, big)
    void = void + gt.cyl(SPIG_L + 1.02, R_SI, z=-SPIG_L - 1, seg=gt.SEG)
    void = void + revolve([(0, h_top - RIM_CH), (R_TI, h_top - RIM_CH),
                           (R_TI + RIM_CH, h_top), (R_TI + RIM_CH, h_top + 1),
                           (0, h_top + 1)])
    return outer + spig, void


def collar(z_seat):
    """Lobe skirt above the rim that wraps the 45 deg neck of the part seated at
    z_seat, so the lobes run on unbroken from tier to tier (COLLAR_G radial seam).
    Its inside is a 45 deg cone opening upward: no support."""
    top = z_seat + COLLAR_H
    band = petal_prism(WALL, z_seat, top)
    r0 = R_SO + COLLAR_G
    return band - revolve([(0, z_seat - 1), (r0 - 1, z_seat - 1), (r0 + COLLAR_H + 1, top + 1),
                           (0, top + 1)])


def port_cyl(r, s0, s1, zp, phi, seg=96):
    c = m3d.Manifold.cylinder(s1 - s0, r, r, seg).rotate((0, gt.PORT_TILT, 0))
    a = math.radians(gt.PORT_TILT)
    return c.translate((R_TI + s0 * math.sin(a), 0, zp + s0 * math.cos(a))).rotate((0, 0, phi))


def embed(r, z):
    """Outer end of the flank plate (bottom, top) for a corner at (r, z): up to
    2 mm into the wall, never past the middle of the bottom funnel."""
    e = min(2.0, (R_SI + WALL / 2 - (r - z)) / 2)
    return (r + e - GUT_T45 / 2, z - e - GUT_T45 / 2), (r + e, z - e)


def gutter():
    """Helical V-gutter (local frame): one 45 deg flank plate swept along the
    corner, floor falling at SLOPE from psi = 0 to PSI_END."""
    psi = np.arange(0.0, PSI_END + 1e-9, 1.0)
    zc = np.interp(psi, PSI, ZC)
    rw = r_corner(PHI_S + psi, zc)
    verts = []
    for p, z, r in zip(psi, zc, rw):
        a = math.radians(PHI_S + p)
        for qr, qz in embed(r, z) + ((r - GUT_W, z + GUT_W), (r - GUT_W, z + GUT_W - GUT_T45)):
            verts.append((qr * math.cos(a), qr * math.sin(a), qz))
    n = len(psi)
    tris = [(0, 2, 1), (0, 3, 2)]
    e = 4 * (n - 1)
    tris += [(e, e + 1, e + 2), (e, e + 2, e + 3)]
    for i in range(n - 1):
        for k in range(4):
            a, b = 4 * i + k, 4 * i + (k + 1) % 4
            c, d = b + 4, a + 4
            tris += [(a, b, c), (a, c, d)]
    v = np.array(verts, dtype=np.float64)
    t = np.array(tris, dtype=np.int64)
    sv = np.einsum("ij,ij->i", v[t[:, 0]], np.cross(v[t[:, 1]], v[t[:, 2]])).sum()
    if sv < 0:
        t = t[:, ::-1]
    mesh = m3d.Mesh(vert_properties=v.astype(np.float32), tri_verts=t.astype(np.uint32))
    return m3d.Manifold(mesh)


def dam():
    """Low end wall at the gutter start (keeps the landing drip from running
    back); DAM_H tall so it stays clear of the last port's net pot."""
    r, z = rw_at(0.0), zc_at(0.0)
    zt = z + DAM_H
    rt = min(float(r_in(PHI_S, zt)), R_SI + zt) + WALL / 2    # wall or funnel
    pts = []
    for t in (-DAM_T / 2, DAM_T / 2):
        for qr, qz in embed(r, z) + ((rt, zt), (r - DAM_H, zt), (r - DAM_H, zt - GUT_T45)):
            pts.append(at(qr, t, qz, PHI_S))
    return m3d.Manifold.hull_points(pts)


def tooth(zt):
    """Key tooth in a socket on a lobe flank; zt = where the next spigot bottom
    sits.  Underside 45 deg into the lobe roof."""
    ang = float(tw(zt)) + TOOTH_OFF
    pts = []
    for t in (-TOOTH_HW, TOOTH_HW):
        for r, z in ((70.0, zt + 7), (70.0, zt - 0.6), (81.5, zt - 12.1), (81.5, zt + 7)):
            pts.append(at(r, t, z, ang))
    return m3d.Manifold.hull_points(pts), ang


def slot(ang, z_seat):
    """Spigot slot that takes the tooth of the part below (pointed roof)."""
    pts = []
    for r in (67.0, 73.5):
        for t, z in ((-SLOT_HW, -SPIG_L - 1), (SLOT_HW, -SPIG_L - 1), (-SLOT_HW, -SPIG_L + 7.6),
                     (SLOT_HW, -SPIG_L + 7.6), (0.0, -SPIG_L + 7.6 + SLOT_HW)):
            pts.append(at(r, t, z + z_seat, ang))
    return m3d.Manifold.hull_points(pts)
TOOTH_ANG = float(tw(PITCH - SPIG_L)) + TOOTH_OFF


TOOTH_ANG = float(tw(PITCH - SPIG_L)) + TOOTH_OFF


# ---- parts -------------------------------------------------------------------------
def make_tier():
    solid, void = shell(TIER_H)
    tubes = [port_cyl(PORT_RO, -30, PORT_L, zp, phi) for phi, zp, _, _ in PORTS]
    bores = [port_cyl(BORE_R, -30, PORT_L + 1, zp, phi) for phi, zp, _, _ in PORTS]
    scoops = [port_cyl(SCOOP_R, PORT_L, PORT_L + 90, zp, phi) for phi, zp, _, _ in PORTS]
    t = union([solid, collar(PITCH)] + tubes) - union([void] + bores + scoops)
    t = union([t, gutter(), dam(), tooth(PITCH - SPIG_L)[0]])
    return t - slot(TOOTH_ANG - TWIST, 0.0)


def make_header():
    solid, void = shell(TIER_H_H)
    h = union([solid - void, gutter(), dam(), tooth(P_H - SPIG_L)[0]])
    return h - slot(TOOTH_ANG - TWIST, 0.0)


def make_cap_local():
    """Cap in header-local coordinates (classic cap + petal plate + key slot)."""
    c = gt.make_cap().translate((0, 0, P_H - gt.CAP_Z))
    c = c + petal_prism(WALL + 2.0, P_H + (R_TO - R_SO), P_H + 7.8)
    return c - slot(tooth(P_H - SPIG_L)[1], P_H)


def place(m, k):
    return m.rotate((0, 0, TWIST * k)).translate((0, 0, TIER_Z0 + k * PITCH))


def pipe():
    return gt.tube(gt.PIPE_ID / 2, gt.PIPE_OD / 2, gt.PIPE_Z0, SPRAY_Z, 64)


def build():
    parts, leg = gt.build_base()
    tier, header, cap = make_tier(), make_header(), make_cap_local()
    for k in range(N_TIERS):
        parts[f"tier_{k + 1}"] = place(tier, k)
    parts["header"] = place(header, N_TIERS)
    parts["cap"] = place(cap, N_TIERS)
    parts["spray_head"] = gt.make_spray_head().translate((0, 0, SPRAY_Z - gt.SPRAY_Z))
    return parts, tier, header, cap


# ---- checks ------------------------------------------------------------------------
def clip(m, z0, z1):
    return m ^ gt.box(-300, 300, -300, 300, z0, z1)


def report():
    print("-- helix vortex")
    print(f"  {N_TIERS} tiers x {N_PORT} ports = {N_TIERS * N_PORT} plants, pitch {PITCH:.0f}, "
          f"twist {TWIST:.0f} deg/tier, 6-lobe star r {R_TO:.0f}..{R_TO + 2 * LOBE_A:.0f}")
    print(f"  height      {CAP_Z + 7.8 + gt.HUB_T:.0f} mm on the stand (cap top z={CAP_Z + 7.8:.0f})")
    print(f"  pipe        1/2in PVC cut to {PIPE_LEN:.0f} mm, jets at z={SPRAY_Z + 6:.0f}")
    print(f"  gutter      floor z {ZC[0]:.1f} -> {ZC[-1]:.1f} over {ARC[-1]:.0f} mm "
          f"({100 * (ZC[0] - ZC[-1]) / ARC[-1]:.1f} %), {PSI_END:.0f} deg, lip r <= "
          f"{np.max(RW) - GUT_W:.1f}")
    print(f"  NFT path    {(N_TIERS + 1) * ARC[-1] / 1000:.2f} m of gutter in "
          f"{N_TIERS + 1} turns, {N_TIERS + 1} cascades")
    print(f"  ports       window top z={WIN_TOP:.1f} (socket band from z={TIER_H - SOCK_BAND:.1f})")


def checks(p, tier, header, cap):
    allok = True

    def line(txt, flag):
        nonlocal allok
        allok &= bool(flag)
        print(f"  {txt} -> {ok(flag)}")

    print("-- 1. stack drop-in (path, seated, wiggle in mm^3)")
    cone = 1.5 * CLR + 0.1
    names = ["rotor"] + [f"tier_{k + 1}" for k in range(N_TIERS)] + ["header", "cap"]
    for i in range(1, len(names)):
        mv, fx = p[names[i]], p[names[i - 1]]
        zs = TIER_Z0 + (i - 1) * PITCH if names[i] != "cap" else CAP_Z
        mv = clip(mv, zs - SPIG_L - 2, zs + 45)
        fx = clip(fx, zs - 70, zs + 45)
        path, seat, w = gt.drop_check(mv, fx, 30.0, CLR, cone)
        line(f"{names[i]:8s} -> {names[i - 1]:8s} path {path:.4f} seated {seat:6.1f} "
             f"wiggle {w:.4f}", path < 1e-3 and seat > 1e-3 and w < 1e-3)
    # the key really indexes: a tier turned 6 deg off cannot seat
    off = clip(p["tier_2"].rotate((0, 0, 6)), TIER_Z0 + PITCH - 14, TIER_Z0 + PITCH + 45)
    jam = vol(off.translate((0, 0, 0.5)) ^ clip(p["tier_1"], TIER_Z0 + 40, TIER_Z0 + 160))
    line(f"key: tier_2 turned 6 deg collides {jam:.1f} mm^3 0.5 mm above its seat", jam > 1)

    print("-- 2. turning vs fixed (min gap, mm, swept over 360 deg)")
    pod = p["pod_base"] + p["pod_roof"]
    pp = pipe()
    fixed = {"lid": p["lid"], "pod": pod, "pinion": p["pinion"], "pipe": pp}
    low = clip(p["tier_1"], 0, gt.Z_RT + 60)
    worst = {}
    for ang in range(0, 360, 10):
        mv = low.rotate((0, 0, ang))
        for sn, sm in fixed.items():
            worst[("tier_1", sn)] = min(worst.get(("tier_1", sn), 99), mv.min_gap(sm, 10.0))
    for ang in np.linspace(0, 360 / gt.N_GEAR, 4):
        mv = p["rotor"].rotate((0, 0, ang))
        for sn in ("lid", "pod", "pipe"):
            worst[("rotor", sn)] = min(worst.get(("rotor", sn), 99), mv.min_gap(fixed[sn], 10.0))
    head = p["spray_head"]
    for ang in range(0, 360, 30):
        for tn in ("header", "tier_6"):
            mv = p[tn].rotate((0, 0, ang))
            for sn, sm in (("spray_head", head), ("pipe", pp)):
                worst[(tn, sn)] = min(worst.get((tn, sn), 99), mv.min_gap(sm, 10.0))
    for (tn, sn), g in sorted(worst.items()):
        line(f"{tn:7s} vs {sn:10s} {g:6.2f}", g >= 0.8)
    g = min(p["cap"].rotate((0, 0, a)).min_gap(head, 10.0) for a in range(0, 360, 60))
    line(f"cap     vs spray_head {g:6.2f} (bushing fit)", g >= 0.25)
    rmax = max(np.max(np.hypot(*np.asarray(p[n].to_mesh().vert_properties)[:, :2].T))
               for n in names[1:])
    line(f"stack max radius {rmax:.1f} <= tank collar {gt.RC:.1f}", rmax <= gt.RC + 0.5)

    print("-- 3. water path")
    allok &= water_checks(p)

    print("-- print: overhangs > 45 deg, net-pot fit")
    for name, m, rot in (("tier", tier, None), ("header", header, None),
                         ("cap", place(cap, 0), gt.FLIP)):
        a = overhang_area(rot(m) if rot else m)
        line(f"{name:7s} overhang area {a:6.1f} mm^2 (bed excluded)", a < 50)
    pots = union([port_cyl(POT_R, -(POT_L - PORT_L), PORT_L + 40, zp, phi)
                  for phi, zp, _, _ in PORTS])
    v = vol(pots ^ tier)
    line(f"2in net pots slide in along the port axis: overlap {v:.3f} mm^3", v < 1e-3)
    line(f"port windows end {TIER_H - SOCK_BAND - WIN_TOP:.1f} mm under the socket band",
         WIN_TOP <= TIER_H - SOCK_BAND - 2.0)
    return allok


def stack_parts(p):
    return {k: p[f"tier_{k + 1}"] for k in range(N_TIERS)} | {N_TIERS: p["header"]}


def to_local(k, pos):
    x, y, z = pos
    psi = (math.degrees(math.atan2(y, x)) - TWIST * k - PHI_S) % 360.0
    return math.hypot(x, y), psi, z - (TIER_Z0 + k * PITCH)


def on_gutter(k, pos):
    r, psi, zl = to_local(k, pos)
    if psi > 359.0 or psi < 1.5:                  # start dam / start of the flank
        rw0, zc0 = rw_at(0.0), zc_at(0.0)
        tops = (zc0 + max(DAM_H, rw0 - r), zc0 + rw0 - r)
        return rw0 - GUT_W - 0.8 <= r and min(abs(zl - t) for t in tops) < 1.5
    if psi > PSI_END + 0.3:
        return False
    rw, zc = rw_at(psi), zc_at(psi)
    if rw - GUT_W - 0.8 <= r <= rw + 0.5:
        return abs(zl - (zc + rw - r)) < 1.5
    # past a corner that rides the funnel: the funnel drains straight into it
    return r <= float(r_in(PHI_S + psi, zl)) + 0.5 and abs(zl - (r - R_SI)) < 1.5


def fall(p, origin, ks):
    """Drop a ray from origin; first thing it hits among stack parts ks + rotor."""
    x, y, z = origin
    best = None
    cands = [(k, stack_parts(p)[k]) for k in ks] + [("rotor", p["rotor"])]
    for k, m in cands:
        hits = m.ray_cast((x, y, z), (x, y, gt.Z_L))
        if hits and (best is None or hits[0].position[2] > best[1][2]):
            best = (k, list(hits[0].position))
    return best


def rotor_tip():
    zt = gt.Z_RB - gt.ROTOR_GAP_DRIP
    return R_TI - (gt.Z_RT - gt.SOCK_D - zt)


def water_checks(p):
    allok = True

    def line(txt, flag):
        nonlocal allok
        allok &= bool(flag)
        print(f"  {txt} -> {ok(flag)}")

    tip = rotor_tip()
    slope = 100 * (ZC[0] - ZC[-1]) / ARC[-1]
    line(f"gutter slope {slope:.2f} % (NFT 2-5 %)", 2.0 <= slope <= 5.0)
    jets = SPRAY_Z + 6
    line(f"jets z={jets:.0f} clear the header lip z={HEAD_Z + LIP_MAX:.0f}",
         jets > HEAD_Z + LIP_MAX + 3)
    # spray -> header wall -> header gutter
    good = tot = 0
    for a in range(0, 360, 30):
        for j in range(8):
            th = math.radians(22.5 + 45 * j + a)
            o = (16 * math.cos(th), 16 * math.sin(th), jets)
            e = (130 * math.cos(th), 130 * math.sin(th), jets)
            hits = p["header"].ray_cast(o, e)
            tot += 1
            if not hits:
                continue
            hx, hy, _ = hits[0].position
            # the sheet runs down the twisted wall: where the lobe flank leans in
            # below the hit it follows it, so drop from the innermost wall point
            phl = math.degrees(th) - TWIST * N_TIERS
            zs = np.arange(0.0, JET_LOCAL, 1.0)
            rh = min(math.hypot(hx, hy), float(np.min(r_in(phl, zs)))) - 1.5
            res = fall(p, (rh * math.cos(th), rh * math.sin(th), jets), range(N_TIERS, -1, -1))
            r, psi, zl = to_local(N_TIERS, res[1]) if res and res[0] == N_TIERS else (0, 0, 0)
            gap = (res and res[0] == N_TIERS and psi > PSI_END
                   and (zl < zc_at(PSI_END) or abs(zl - (r - R_SI)) < 1.5))   # funnel
            good += bool(res and res[0] == N_TIERS and (on_gutter(N_TIERS, res[1]) or gap))
    line(f"spray: {good}/{tot} jet hits run down the header wall into its gutter "
         f"(or the {360 - PSI_END:.0f} deg end gap -> shoulder -> spill path)", good == tot)
    # gutter end -> own shoulder -> spigot drip -> next gutter down
    for k in range(N_TIERS, -1, -1):
        name = "header" if k == N_TIERS else f"tier_{k + 1}"
        ang = PHI_S + PSI_END + 0.5 + TWIST * k      # just past the gutter end
        z0 = TIER_Z0 + k * PITCH
        r0 = rw_at(PSI_END) - 1.0
        o = (r0 * math.cos(math.radians(ang)), r0 * math.sin(math.radians(ang)),
             z0 + zc_at(PSI_END) + 0.5)
        h = stack_parts(p)[k].ray_cast(o, (o[0], o[1], z0 - 30))
        dz = (o[2] - h[0].position[2]) if h else 99
        rd = R_SI + 0.6
        d = (rd * math.cos(math.radians(ang)), rd * math.sin(math.radians(ang)),
             z0 - SPIG_L - 0.2)
        res = fall(p, d, range(k - 1, -1, -1))
        if k > 0:
            hit = res and res[0] == k - 1 and on_gutter(k - 1, res[1])
            _, psi, _ = to_local(k - 1, res[1]) if res else (0, -1, 0)
            pg = min(abs(psi - q[3]) for q in PORTS)
            arc = math.radians(pg) * rd
            line(f"{name:7s} spill: falls {dz:.1f} onto its shoulder, drips onto tier_{k} "
                 f"gutter at psi={psi:.1f} (pot {arc:.0f} mm away)",
                 dz < 3 and hit and arc > POT_R + 3 and psi < PORTS[0][3])
        else:
            hit = res and res[0] == "rotor"
            rr = math.hypot(*res[1][:2]) if res else 0
            line(f"{name:7s} spill: falls {dz:.1f} onto its shoulder, drips on the rotor "
                 f"funnel r={rr:.1f} -> tip r={tip:.1f} < drain {gt.R_DRAIN:.0f}",
                 dz < 3 and hit and tip < gt.R_DRAIN)
    # roots: every pot base hangs right over its own gutter, fed from upstream
    good = 0
    drops = []
    s = -(POT_L - PORT_L)
    for k in range(N_TIERS):
        for phi, zp, zc, psi in PORTS:
            z0 = TIER_Z0 + k * PITCH
            a = math.radians(phi + TWIST * k)
            rb = R_TI + (s + POT_R) / S2           # lowest rim point of the pot base
            zb = zp + (s - POT_R) / S2
            o = (rb * math.cos(a), rb * math.sin(a), z0 + zb - 0.05)
            h = stack_parts(p)[k].ray_cast(o, (o[0], o[1], z0 - 20))
            fed = PSI_LAND < psi < PSI_END
            if h and on_gutter(k, list(h[0].position)) and fed:
                drops.append(o[2] - h[0].position[2])
                good += drops[-1] < 20.0
    lo, hi = (min(drops), max(drops)) if drops else (0, 0)
    line(f"root zones: {good}/{N_TIERS * N_PORT} pot bases hang {lo:.1f}..{hi:.1f} mm over a "
         f"fed gutter", good == N_TIERS * N_PORT)
    # overflow when a gutter clogs: over the lip, straight down to the drain
    good = tot = 0
    worst = 0.0
    for k in range(N_TIERS, -1, -1):
        for psi in np.arange(2.0, PSI_END, 6.0):
            rl = rw_at(psi) - GUT_W - 0.4
            zl = zc_at(psi) + GUT_W - GUT_T45 - 0.2
            a = math.radians(PHI_S + psi + TWIST * k)
            o = (rl * math.cos(a), rl * math.sin(a), TIER_Z0 + k * PITCH + zl)
            res = fall(p, o, range(k, -1, -1))
            tot += 1
            if res is None:
                good += rl < gt.R_DRAIN
            elif res[0] == "rotor":
                good += 1
            elif on_gutter(res[0], res[1]) and res[0] < k:
                good += 1
            worst = max(worst, rl)
    line(f"overflow: {good}/{tot} lip drips (r <= {worst:.1f} < spigot bore {R_SI:.1f}) land in "
         f"a lower gutter or the rotor funnel -> drain", good == tot)
    return allok


def overhang_area(m):
    tm = gt.to_trimesh(m)
    z0 = tm.bounds[0][2]
    n = tm.face_normals
    c = tm.triangles_center
    bad = (n[:, 2] < -0.72) & (c[:, 2] > z0 + 0.4)
    return float(tm.area_faces[bad].sum())


def budget(p, tier, header, cap):
    """Rotating mass, water and friction torque on the ball race + bushing."""
    print("-- 5. mass / torque budget")
    fill = 0.85                                  # thin walls print near solid
    g_tier = vol(tier) / 1000 * 1.07 * fill
    g_head = vol(header) / 1000 * 1.07 * fill
    g_cap = vol(cap) / 1000 * 1.07 * fill
    g_rot = vol(p["rotor"]) / 1000 * 1.07 * fill
    stack = N_TIERS * g_tier + g_head + g_cap + g_rot
    film = (N_TIERS + 1) * ARC[-1] * 8.0 / 1000   # 4 mm deep V film = 8 mm^2
    plants = N_TIERS * N_PORT * 150.0             # pot + wet media + mature plant
    w = (stack + film + plants) / 1000 * 9.81
    t_lo, t_hi = 0.005 * w * gt.RACE_R / 1000, 0.01 * w * gt.RACE_R / 1000
    f_wind = 0.5 * 1.2 * 8.3 ** 2 * 1.2 * 0.24     # 30 km/h on stack + foliage, N
    f_bush = f_wind * 0.5 + 2.0                    # share at the top + imbalance
    t_bush = 0.35 * f_bush * (gt.STUB_D / 2) / 1000
    total = t_hi + t_bush
    tm = gt.to_trimesh(union([p[f"tier_{k + 1}"] for k in range(N_TIERS)] + [p["header"]]))
    e = float(np.hypot(*tm.center_mass[:2]))
    print(f"  ASA (fill {fill:.0%}): tier {g_tier:.0f} g x {N_TIERS}, header {g_head:.0f} g, "
          f"cap {g_cap:.0f} g, rotor {g_rot:.0f} g -> {stack / 1000:.2f} kg turning")
    print(f"  water film {film:.0f} g, plants+media {plants / 1000:.1f} kg (36 x 150 g) "
          f"-> {w:.0f} N on the race")
    print(f"  race {t_lo:.3f}..{t_hi:.3f} N m (c 0.005..0.01 at r {gt.RACE_R:.0f}), "
          f"bushing {t_bush:.3f} N m ({f_bush:.0f} N radial, mu 0.35)")
    print(f"  stack CoM offset {e:.2f} mm (empty); wind {f_wind:.0f} N at 30 km/h")
    print(f"  total {total:.3f} N m of 0.2 available ({100 * total / 0.2:.0f} %) "
          f"-> {ok(total < 0.1)}")
    return total < 0.1, dict(tier=g_tier, header=g_head, cap=g_cap)


# ---- section + export --------------------------------------------------------------
def section_png(p):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Polygon
    from section import cut, color

    k_cut = 3
    ang = PORTS[0][0] + TWIST * k_cut
    fig, ax = plt.subplots(figsize=(9, 16), dpi=110)
    seen = set()
    cols = {"tier": "#e8e2d0", "header": "#cfc6aa", "cap": "#cfc6aa", "spray_head": "#4a90c2"}
    for name, m in dict(p, pipe=pipe()).items():
        key = name.rstrip("0123456789").rstrip("_")
        fc = cols.get(key, color(name))
        for poly in cut(m, ang):
            ax.add_patch(Polygon(poly, closed=True, fc=fc, ec="k", lw=0.4,
                                 label=key if key not in seen else None))
            seen.add(key)
    blue = "#1f77b4"
    jz = SPRAY_Z + 6
    ax.annotate("", (0, jz), (0, gt.TANK_FLOOR + 60),
                arrowprops=dict(arrowstyle="->", color=blue, lw=2.5))
    for s in (1, -1):
        ax.annotate("", (s * (R_TI - 2), jz - 3), (s * 16, jz),
                    arrowprops=dict(arrowstyle="->", color=blue, lw=2))
    # cascade: gutter end -> shoulder -> spigot drip -> next gutter (schematic)
    for k in range(N_TIERS, 0, -1):
        z0 = TIER_Z0 + k * PITCH
        ax.annotate("", (R_SI - 1, TIER_Z0 + (k - 1) * PITCH + Z_CS + 12),
                    (R_SI + 2, z0 + ZC[-1]),
                    arrowprops=dict(arrowstyle="->", color=blue, lw=1.4,
                                    connectionstyle="arc3,rad=0.25"))
    zo = TIER_Z0 + 4 * PITCH + LIP_MAX - 3
    ax.annotate("", (52, gt.Z_RT - 20), (R_TI - GUT_W - 1, zo),
                arrowprops=dict(arrowstyle="->", color="#d62728", lw=1.2, ls="--"))
    ax.annotate("", (-40, gt.Z_L - 60), (-50, gt.Z_L + 5),
                arrowprops=dict(arrowstyle="->", color=blue, lw=2))
    ax.annotate("spray head (fixed) squirts\nat the header wall", (20, jz),
                (130, jz + 60), arrowprops=dict(arrowstyle="->"), fontsize=9)
    ax.annotate(f"spiral V-gutter, {100 * SLOPE:.0f} % fall,\n1 turn per tier "
                f"(45 deg flank, no support)", (R_TI - 6, TIER_Z0 + 5 * PITCH + Z_CS),
                (130, TIER_Z0 + 5 * PITCH + 40), arrowprops=dict(arrowstyle="->"), fontsize=9)
    ax.annotate(f"gutter end pours on the shoulder,\nspigot drips {TWIST:.0f} deg on = start\n"
                "of the gutter below (blue)", (R_SI, TIER_Z0 + 3 * PITCH),
                ((130, TIER_Z0 + 2 * PITCH)), arrowprops=dict(arrowstyle="->"), fontsize=9)
    ax.annotate("2\" net pot on a lobe,\nbase 5-15 mm over the gutter",
                (150, TIER_Z0 + k_cut * PITCH + 20), arrowprops=dict(arrowstyle="->"),
                fontsize=9)
    ax.annotate("overflow (clog): over the lip,\nstraight to the rotor funnel\n"
                "and the lid drain (red)", (52, gt.Z_RT - 20), (130, gt.Z_L - 120),
                arrowprops=dict(arrowstyle="->"), fontsize=9)
    ax.set_xlim(-gt.LEG_R_END - 10, gt.LEG_R_END + 10)
    ax.set_ylim(-gt.HUB_T - 20, CAP_Z + 60)
    ax.set_aspect("equal")
    ax.set_xlabel("mm")
    ax.set_title(f"Helix Vortex: {N_TIERS} twisted tiers x {N_PORT} ports, spiral NFT gutter, "
                 f"{CAP_Z + 7.8 + gt.HUB_T:.0f} mm tall\n(cut through tier {k_cut + 1} port 1)")
    ax.legend(loc="upper left", fontsize=7)
    ax.grid(alpha=0.25)
    out = os.path.join(HERE, "preview", "section_2d.png")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)


def export(p, tier, header, cap):
    singles = {"tier": tier, "header": header, "cap": place(cap, 0)}
    orient = {"tier": (None, "spigot down"), "header": (None, "spigot down"),
              "cap": (gt.FLIP, "top face down")}
    qty = {"tier": N_TIERS}
    base = [n for n in p if not n.startswith(("tier", "header", "cap", "spray"))]
    preview = {n: f"preview/{n}.stl" for n in base}
    meta = {n: gt.base_meta(n) for n in base}
    for k in range(N_TIERS):
        preview[f"tier_{k + 1}"] = p[f"tier_{k + 1}"]
        meta[f"tier_{k + 1}"] = ("#e8e2d0" if k % 2 == 0 else "#d9d2bd", 4 + k, True)
    preview.update(header=p["header"], spray_head=p["spray_head"], cap=p["cap"], pipe=pipe())
    meta.update(header=("#cfc6aa", 10, True), spray_head=("#4a90c2", 10.6),
                cap=("#bfb595", 11.4, True), pipe=gt.base_meta("pipe"))
    return gt.export_set(HERE, singles, orient, qty, preview, meta,
                         f"Helix Vortex: {N_TIERS} twisted tiers x {N_PORT} ports, spiral NFT",
                         target_z=760.0)


def main():
    p, tier, header, cap = build()
    report()
    good = checks(p, tier, header, cap)
    print("-- 4. bed fit + watertight")
    good &= export(p, tier, header, cap)
    ok_t, _ = budget(p, tier, header, cap)
    good &= ok_t
    section_png(p)
    print(f"== all checks -> {ok(good)}")


if __name__ == "__main__":
    main()
