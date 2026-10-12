"""Lotus Cascade: a pagoda of flared, petal-edged bowls on the rotating base.

Water goes up the fixed 1/2" pipe to a bell-shaped DISTRIBUTOR (lotus seed
pod) on top.  Its jets hit the inside of the bell and rain off the bell rim
into the top bowl.  Every bowl holds a 15 mm pool; it is set by 3 SCUPPER
standpipes in the floor.  Their overflow falls straight down as thin water
threads into the bowl below, and from the bottom bowl into the ADAPTER funnel,
the rotor bore and the lid drain.  A 1.8 mm weep hole at the foot of every
standpipe empties the pool in a few minutes once the pump stops (ebb and
flow), so the stack is light again between cycles.

Why scuppers and not open petal-lip spill: a sheet over a lip leaves with
~0.3 m/s and lands 40+ mm further out, plus 40 mm of drift in light wind over
a 130 mm fall.  The next bowl would have to be ~85 mm wider, and the bed caps
a bowl at 250 mm.  A vertical drop near the stem only drifts, and the bowl
below catches it with > 15 mm to spare.  The petal rim stays dry: its notches
sit 17 mm above the scupper crest, more than the head at full pump flow with
one scupper blocked.

  ROTOR (base) - ADAPTER (tier spigot, drain funnel, stem, spokes)
  BOWL_1..BOWL_6 (7,7,7,6,5,4 pots = 36): floor, 40 deg flared core with a
     notched petal rim, 2" net-pot sleeves tilted 20 deg out (they bulge out
     of the core as petals), 3 scupper standpipes, central stem with a spigot
     for the next bowl, socket below.  Bowl 6's stem bore is the top bushing.
  DISTRIBUTOR on the pipe top (fixed): sleeve = bushing stub, jets, bell.

Run: env PYTHONPATH=/home/infra/printables/.pydeps python3 lotus_cascade.py
"""
import math
import os
import sys

import numpy as np
import manifold3d as m3d

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))
import grow_tower as gt  # noqa: E402

SEG = 144
G = 9.81

# ---- parameters (mm) -------------------------------------------------------
N_POTS = (7, 7, 7, 6, 5, 4)          # bottom -> top, 36 plants
R_POT = (74.0, 71.0, 68.0, 63.0, 58.0, 55.0)   # sleeve axis at the floor top
PITCH = 130.0         # bowl-to-bowl spacing
Z_A = 530.0           # adapter top = bowl_1 floor underside
FT = 3.0              # floor
H_W = 40.0            # core wall height above the floor underside
FLARE = 40.0          # core wall flare from vertical (<= 45 for printing)
WALL = 2.4            # core wall, sleeve wall (normal thickness)
CORE_OUT = (5.0, 5.0, 5.0, 9.0, 12.0, 8.0)   # core floor r = sleeve axis r + this
POOL = 15.0           # pool depth = scupper crest above the floor top
NOTCH = 5.0           # petal notch depth in the core rim
TILT = 20.0           # net-pot sleeve tilt outward from vertical
MOUTH_H = 56.0        # sleeve mouth above the floor top (vertical)
SLV_RO = gt.PORT_ID / 2 + WALL        # 28.4
POT_LEN, POT_BOT_R = 50.0, 20.0       # 2" net pot: lip to bottom, bottom radius
WIN = 12.0            # diamond window (diagonal) at the sleeve foot

STEM_RI, STEM_RO = 17.5, 24.0         # bowl stem (column) around the pipe
SPIG_RO = 21.0        # stem spigot outer (into the next bowl's socket)
SOCK_RI = SPIG_RO + gt.CLR            # socket bore
SOCK_D = 12.0
SPIG_H = SOCK_D - 0.5

N_SCUP = 3
R_SCUP = 34.0         # scupper standpipe axis radius
SCUP_RI, SCUP_RO = 5.0, 7.4           # 10 mm bore
WEEP_D = 1.8          # weep hole (prints ~1.6)

FUNNEL_R = 46.0       # adapter funnel lip (drips land inside gt.R_DRAIN)
FUNNEL_T = 3.5        # horizontal thickness of the 45 deg funnel shell

BUSH_R = 15.0         # distributor sleeve OD/2 = bushing stub
BUSH_CLR = 0.3
BUSH_L = 16.0
BELL_RI, BELL_RO = 31.0, 33.4
BELL_DROP = 24.0      # bell rim below the pipe top
JETS, JET_D = 8, 2.4
PIN_D = 3.4           # M3 cross pin / screw through bell, sleeve and pipe

# derived heights
Z_SEAT = gt.Z_RT - gt.SEAT_DROP
Z_BOWL = [Z_A + k * PITCH for k in range(len(N_POTS))]
Z_P = Z_BOWL[-1] + 74.0              # pipe top
Z_STEM_TOP = Z_P - 14.0              # top bowl stem top (under the jets)
Z_TOP = Z_P + 14.0
TANF = math.tan(math.radians(FLARE))

# physics / budget
RHO_ASA = 1.07
FILL = 0.8            # thin walls are mostly perimeters
PLANT_KG = 0.10       # mature herb / lettuce
POT_MEDIA_KG = 0.06   # net pot + wet clay pebbles
WIND = 3.0            # light wind, m/s
Q_MAX = 800.0         # L/h, pump at zero head
H_MAX = 1.45          # m, pump max head
C_ROLL = (0.005, 0.01)
MU_BUSH = 0.3
T_MOTOR = 0.2


def rev(pts, seg=SEG):
    a = sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1]))
    return gt.revolve(pts if a > 0 else pts[::-1], seg)


def tube(r0, r1, z0, z1, seg=SEG):
    return rev([(r0, z0), (r1, z0), (r1, z1), (r0, z1)], seg)


def zbox(z0, z1, r=400.0):
    return gt.box(-r, r, -r, r, z0, z1)


def diamond(length, diag, x0, z, ang, xy=(0.0, 0.0)):
    """Prism with a 45 deg diamond section, axis horizontal along `ang`."""
    s = diag / math.sqrt(2)
    p = m3d.Manifold.cube((length, s, s), True).rotate((45, 0, 0))
    p = p.translate((x0 + length / 2, 0, z)).rotate((0, 0, ang))
    return p.translate((xy[0], xy[1], 0))


def axis_pt(k, j, s):
    """Point at distance s along sleeve (k, j) axis from its foot (floor top)."""
    a = math.radians(TILT)
    r = R_POT[k] + s * math.sin(a)
    z = Z_BOWL[k] + FT + s * math.cos(a)
    t = math.radians(pot_ang(k, j))
    return r * math.cos(t), r * math.sin(t), z


def pot_ang(k, j):
    return (k % 2) * 180.0 / N_POTS[k] + 360.0 * j / N_POTS[k]


def scup_angs(k):
    n = N_POTS[k]
    gaps = [pot_ang(k, j) + 180.0 / n for j in range(n)]
    return [gaps[round(i * n / N_SCUP) % n] for i in range(N_SCUP)]


def sleeve_cyl(k, j, r, s0, s1, seg=96):
    c = m3d.Manifold.cylinder(s1 - s0, r, r, seg).translate((0, 0, s0))
    c = c.rotate((0, TILT, 0)).translate((R_POT[k], 0, Z_BOWL[k] + FT))
    return c.rotate((0, 0, pot_ang(k, j)))


MOUTH_S = MOUTH_H / math.cos(math.radians(TILT))


def core_r(k):
    """(floor radius, rim radius) of the core outer surface."""
    rf = R_POT[k] + CORE_OUT[k]
    return rf, rf + H_W * TANF


def stem_spigot(z):
    return rev([(STEM_RI, z - 0.01), (SPIG_RO, z - 0.01), (SPIG_RO, z + SPIG_H - gt.EF),
                (SPIG_RO - gt.EF, z + SPIG_H), (STEM_RI, z + SPIG_H)], 96)


# ---- parts -------------------------------------------------------------------
def make_adapter():
    """Rotor socket spigot (as gt.make_tier), 45 deg drain funnel, spokes,
    stem with the bowl spigot.  Prints spigot down."""
    zs = Z_SEAT
    zb = zs - gt.SPIG_L
    ring = rev([(gt.R_SI, zb), (gt.R_SO - gt.EF, zb), (gt.R_SO, zb + gt.EF), (gt.R_SO, zs),
                (gt.R_TO, zs + gt.R_TO - gt.R_SO), (gt.R_TO, Z_A), (gt.R_SI, Z_A)])
    ri = gt.R_SI + 0.5
    funnel = rev([(FUNNEL_R, zb), (FUNNEL_R + FUNNEL_T, zb),
                  (ri, zb + ri - FUNNEL_R - FUNNEL_T), (ri, zb + ri - FUNNEL_R)])
    stem = tube(STEM_RI, STEM_RO, zb, Z_A, 96) + stem_spigot(Z_A)
    spokes = [gt.box(STEM_RO - 1, FUNNEL_R + 2.5, -2.5, 2.5, zb, zs).rotate((0, 0, 60 + 120 * i))
              for i in range(3)]
    a = gt.union([ring, funnel, stem] + spokes)
    return a - gt.cyl(80, STEM_RI, z=zb - 1, seg=96)


def make_bowl(k):
    z0 = Z_BOWL[k]
    top = k == len(N_POTS) - 1
    rf, rr = core_r(k)
    n = N_POTS[k]
    core = rev([(0, z0), (rf, z0), (rr, z0 + H_W), (0, z0 + H_W)])
    sl_out = gt.union([sleeve_cyl(k, j, SLV_RO, -15, MOUTH_S) for j in range(n)])
    sl_bore = gt.union([sleeve_cyl(k, j, gt.PORT_ID / 2, -15, MOUTH_S + 5) for j in range(n)])
    z_stem = Z_STEM_TOP if top else Z_BOWL[k + 1]
    stem = tube(0, STEM_RO, z0, z_stem, 96)
    scups = [gt.polar(R_SCUP, a) for a in scup_angs(k)]
    scup_out = gt.union([gt.cyl(FT + POOL, SCUP_RO, z=z0, x=x, y=y, seg=48) for x, y in scups])
    env = (core + sl_out + stem) ^ zbox(z0, z_stem + 1)
    env = env + scup_out
    if not top:
        env = env + stem_spigot(z_stem)
    # pool void: core inside minus the solids standing in it, plus sleeve bores
    th = WALL / math.cos(math.radians(FLARE))
    inner = rev([(0, z0 + FT), (rf - th + FT * TANF, z0 + FT), (rr - th, z0 + H_W + 0.01),
                 (0, z0 + H_W + 0.01)])
    void = inner - sl_out - gt.cyl(H_W + 1, STEM_RO, z=z0 - 0.5, seg=96) - scup_out
    void = void + (sl_bore ^ zbox(z0 + FT, z0 + 200))
    wins = []
    for j in range(n):
        x, y, _ = axis_pt(k, j, 0)
        for d in (-45.0, 45.0):
            wins.append(diamond(SLV_RO + 1.2, WIN, 0, z0 + FT + WIN / 2 + 0.5,
                                pot_ang(k, j) + 180 + d, (x, y)))
    void = void + (gt.union(wins) - scup_out)
    # petal notches in the core rim, in every gap between sleeves
    notches = [diamond(rr - rf + 20, 2 * NOTCH, rf - 15, z0 + H_W, pot_ang(k, j) + 180.0 / n)
               for j in range(n)]
    void = void + (gt.union(notches) - sl_out)
    b = env - void
    # stem bore, socket below (45 deg step up to the bore), bushing in bowl 6
    bore = [(0, z0 - 1), (SOCK_RI, z0 - 1), (SOCK_RI, z0 + SOCK_D),
            (STEM_RI, z0 + SOCK_D + SOCK_RI - STEM_RI)]
    if top:
        zb = Z_STEM_TOP - BUSH_L
        rb = BUSH_R + BUSH_CLR
        bore += [(STEM_RI, zb - (STEM_RI - rb)), (rb, zb), (rb, Z_STEM_TOP + 1)]
    else:
        bore += [(STEM_RI, z_stem + SPIG_H + 1)]
    bore += [(0, bore[-1][1])]
    b = b - rev(bore, 96)
    # scupper bores, weep holes, drip-break grooves on the underside
    for (x, y), a in zip(scups, scup_angs(k)):
        b = b - gt.cyl(FT + POOL + 2, SCUP_RI, z=z0 - 1, x=x, y=y, seg=48)
        w = m3d.Manifold.cylinder(6, (WEEP_D + gt.HOLE_COMP) / 2, (WEEP_D + gt.HOLE_COMP) / 2, 16)
        w = w.rotate((0, 90, 0)).translate((SCUP_RI - 1, 0, z0 + FT + 1.0))
        b = b - w.rotate((0, 0, 180)).translate((x, y, 0))
        b = b - tube(SCUP_RO - 1.2, SCUP_RO - 0.2, z0 - 0.01, z0 + 1.0, 48).translate((x, y, 0))
    return b


def make_distributor():
    """Fixed, local z = 0 at the pipe top: pipe sleeve (= bushing stub),
    jet chamber, bell.  Prints upside down."""
    p = rev([(gt.PIPE_OD / 2 + 0.2, -45), (BUSH_R, -45), (BUSH_R, 10), (BELL_RI, 10),
             (BELL_RI, -BELL_DROP + 1.2), (BELL_RI + 1.2, -BELL_DROP), (BELL_RO, -BELL_DROP),
             (BELL_RO, 12.8), (BELL_RO - 1.2, 14), (0, 14), (0, 10), (8, 10), (8, 0),
             (gt.PIPE_OD / 2 + 0.2, 0)])
    for i in range(JETS):
        h = m3d.Manifold.cylinder(20, (JET_D + gt.HOLE_COMP) / 2, (JET_D + gt.HOLE_COMP) / 2, 24)
        p = p - h.rotate((0, 90, 0)).translate((0, 0, 5)).rotate((0, 0, 360 / JETS * i + 22.5))
    pin = m3d.Manifold.cylinder(80, (PIN_D + gt.HOLE_COMP) / 2, (PIN_D + gt.HOLE_COMP) / 2, 24)
    p = p - pin.rotate((90, 0, 0)).translate((0, 40, -7))
    return p.translate((0, 0, Z_P))


def pipe():
    return tube(gt.PIPE_ID / 2, gt.PIPE_OD / 2, gt.PIPE_Z0, Z_P, 64)


def build():
    base, leg = gt.build_base()
    own = {"adapter": make_adapter()}
    for k in range(len(N_POTS)):
        own[f"bowl_{k + 1}"] = make_bowl(k)
    own["distributor"] = make_distributor()
    return base, leg, own


# ---- physics -----------------------------------------------------------------
def drift(h_mm, d_mm=4.0):
    """Sideways drift (mm) of a falling drop in WIND over a fall h (linear drag)."""
    vt = 8.8 * min(1.0, d_mm / 4.0) ** 0.5
    tau = vt / G
    t = math.sqrt(2 * h_mm / 1000 / G)
    return 1000 * WIND * (t - tau * (1 - math.exp(-t / tau)))


def weir_head(q_lh, n_open):
    """Head (mm) over n_open circular standpipe crests for flow q (L/h)."""
    q = q_lh / 3.6e6
    return 1000 * (q / (1.84 * n_open * math.pi * 2 * SCUP_RI / 1000)) ** (2 / 3)


def pool_region(k):
    """Everything inside the bowl's wet outline (core inner + sleeve bores)."""
    z0 = Z_BOWL[k]
    rf, rr = core_r(k)
    th = WALL / math.cos(math.radians(FLARE))
    inner = rev([(STEM_RO, z0 + FT), (rf - th + FT * TANF, z0 + FT), (rr - th, z0 + H_W),
                 (STEM_RO, z0 + H_W)])
    bores = gt.union([sleeve_cyl(k, j, gt.PORT_ID / 2, -15, MOUTH_S + 5)
                      for j in range(N_POTS[k])])
    return inner + (bores ^ zbox(z0 + FT, z0 + 200))


# ---- checks --------------------------------------------------------------------
def checks(base, own):
    allok = True

    def line(txt, flag):
        nonlocal allok
        allok &= bool(flag)
        print(f"  {txt} -> {gt.ok(flag)}")

    cone = 1.5 * gt.CLR + 0.1
    print("-- 1. stack drop-in (path, seated, wiggle; mm^3)")
    seq = [("adapter -> rotor", own["adapter"], base["rotor"], gt.CLR, cone),
           ("bowl_1 -> adapter", own["bowl_1"], own["adapter"], gt.CLR, 0.05)]
    for k in range(2, len(N_POTS) + 1):
        seq.append((f"bowl_{k} -> bowl_{k - 1}", own[f"bowl_{k}"], own[f"bowl_{k - 1}"],
                    gt.CLR, 0.05))
    seq.append(("distributor -> pipe", own["distributor"], pipe() + own["bowl_6"], 0.2, 0.05))
    for name, mv, fx, wig, lift in seq:
        path, seat, w = gt.drop_check(mv, fx, 30.0, wig, lift, step=1.0)
        line(f"{name:22s} path {path:.4f} seated {seat:7.1f} wiggle {w:.4f}",
             path < 1e-3 and seat > 1e-3 and w < 1e-3)

    print("-- 2. turning vs fixed, min gap (mm), swept")
    dist = own["distributor"]
    bell = dist ^ rev([(BUSH_R + 2, Z_P - 60), (60, Z_P - 60), (60, Z_P + 20), (BUSH_R + 2, Z_P + 20)])
    pp = pipe()
    fixed = {"lid": base["lid"], "pod": base["pod_base"] + base["pod_roof"],
             "pinion": base["pinion"], "pipe": pp, "bell": bell}
    pairs = [("adapter", "lid"), ("adapter", "pod"), ("adapter", "pinion"), ("adapter", "pipe"),
             ("bowl_1", "lid"), ("bowl_1", "pod"), ("bowl_1", "pinion"), ("bowl_6", "bell")]
    pairs += [(f"bowl_{k}", "pipe") for k in range(1, len(N_POTS) + 1)]
    for tn, sn in pairs:
        per = 120.0 if tn == "adapter" else 360.0 / N_POTS[int(tn[-1]) - 1]
        g = min(own[tn].rotate((0, 0, a)).min_gap(fixed[sn], 12.0)
                for a in np.arange(0, per, per / 6))
        line(f"{tn:8s} vs {sn:7s} {g:6.2f} (period {per:.0f} deg)", g >= 0.8)
    g = own["bowl_6"].min_gap(dist, 5.0)
    line(f"bowl_6 bushing on distributor stub {g:5.2f} (running fit >= 0.25)", 0.25 <= g < 0.8)
    pin_gap = (Z_P - 7 - PIN_D / 2) - Z_STEM_TOP
    line(f"cross pin above bowl_6 stem top     {pin_gap:5.2f}", pin_gap >= 0.8)

    print("-- 3. water path")
    # top bowl fed by the bell rim
    rr6 = core_r(5)[1] - WALL / math.cos(math.radians(FLARE))
    fall = (Z_P - BELL_DROP) - (Z_BOWL[5] + FT + POOL)
    d = drift(fall)
    line(f"bell rim r={BELL_RI + 1.2:.0f} drips {fall:.0f} mm into bowl_6 pool "
         f"(r {BELL_RI - d:.0f}..{BELL_RO + d:.0f} within {STEM_RO:.0f}..{rr6:.0f})",
         BELL_RO + d < rr6 and BELL_RI > STEM_RO + 0.8)
    # scupper threads land in the bowl below
    for k in range(len(N_POTS) - 1, 0, -1):
        fall = Z_BOWL[k] - (Z_BOWL[k - 1] + FT + POOL)
        d = 1.5 * drift(fall) + 5
        rin = core_r(k - 1)[1] - WALL / math.cos(math.radians(FLARE))
        line(f"bowl_{k + 1} scuppers r={R_SCUP:.0f} fall {fall:.0f} mm, wind {WIND} m/s "
             f"-> r <= {R_SCUP + SCUP_RI + d:.0f} < bowl_{k} rim {rin:.0f}",
             R_SCUP + SCUP_RI + d < rin)
    d = 5.0                     # closed chamber (bowl_1 floor + adapter ring): splash only
    line(f"bowl_1 scuppers drop sheltered, r<={R_SCUP + SCUP_RI + d:.0f} < funnel mouth "
         f"{FUNNEL_R:.0f}; funnel lip r={FUNNEL_R:.0f}, rotor lip r="
         f"{gt.R_TI - (gt.Z_RT - gt.SOCK_D - gt.Z_RB + gt.ROTOR_GAP_DRIP):.1f}"
         f" < drain {gt.R_DRAIN:.0f}",
         R_SCUP + SCUP_RI + d < FUNNEL_R and FUNNEL_R < gt.R_DRAIN)
    # roots: pot bottoms under the pool surface
    a = math.radians(TILT)
    s_bot = MOUTH_S - POT_LEN
    zb = s_bot * math.cos(a) - POT_BOT_R * math.sin(a)
    zc = s_bot * math.cos(a)
    line(f"36 pots: pot bottom {zb:.1f}..{zc + POT_BOT_R * math.sin(a):.1f} mm over the floor, "
         f"pool {POOL:.0f} mm (sleeve windows open {0.5:.1f}..{WIN + 0.5:.1f})",
         0 < zb and zc + 5 < POOL and sum(N_POTS) == 36)
    for k in range(len(N_POTS)):
        x, y, z = axis_pt(k, 0, s_bot)
        inside = gt.vol(gt.cyl(1, 1, z=Z_BOWL[k] + FT + 1, x=x, y=y) ^ pool_region(k)) > 2.5
        free = gt.vol(gt.cyl(1, 1, z=Z_BOWL[k] + FT + 1, x=x, y=y) ^ own[f"bowl_{k + 1}"]) < 1e-3
        if not (inside and free):
            line(f"bowl_{k + 1} pot foot not in the pool", False)
    # overflow capacity: petal notches never spill
    fb = H_W - NOTCH - FT - POOL
    h3, h2 = weir_head(Q_MAX, N_SCUP), weir_head(Q_MAX, N_SCUP - 1)
    line(f"scupper head at {Q_MAX:.0f} L/h: {h3:.1f} mm (3 open) / {h2:.1f} mm (1 blocked) "
         f"< freeboard {fb:.0f} mm to the petal notches", h2 < fb)
    rmax = max(np.max(np.linalg.norm(np.asarray(m.to_mesh().vert_properties)[:, :2], axis=1))
               for n, m in own.items() if n != "distributor")
    line(f"widest bowl r={rmax:.1f} inside the tank footprint RC={gt.RC:.1f}", rmax < gt.RC)
    return allok


def mass_torque(own):
    print("-- 5. mass / torque")
    plastic = sum(gt.vol(m) for n, m in own.items() if n != "distributor") / 1000 * RHO_ASA * FILL
    pools, drains = [], []
    for k in range(len(N_POTS)):
        v = gt.vol((pool_region(k) ^ zbox(Z_BOWL[k] + FT, Z_BOWL[k] + FT + POOL))
                   - own[f"bowl_{k + 1}"])
        pools.append(v / 1e6)
        area = v / POOL / 1e6
        a = math.pi * (WEEP_D / 2000) ** 2
        drains.append(area / (N_SCUP * 0.6 * a) * math.sqrt(2 * POOL / 1000 / G) / 60)
    water = sum(pools)
    plants = sum(N_POTS) * (PLANT_KG + POT_MEDIA_KG)
    total = plastic / 1000 + water + plants
    print(f"  plastic {plastic:.0f} g (ASA, ~{FILL:.0%} fill)  pools "
          + " + ".join(f"{p:.2f}" for p in pools) + f" = {water:.2f} kg")
    print(f"  plants + pots + wet media {plants:.1f} kg  -> turning {total:.1f} kg")
    print(f"  ebb: weeps empty the pools in " + ", ".join(f"{t:.0f}" for t in drains)
          + " min (pump off 5-15 min)")
    w = total * G
    side = 0.5 * 1.2 * 5.0 ** 2 * 1.0 * (0.24 * (Z_TOP - Z_A) / 1000) / 2 + 0.5
    t_b = MU_BUSH * side * BUSH_R / 1000
    for c in C_ROLL:
        t = c * w * gt.RACE_R / 1000 + t_b
        print(f"  c={c:.3f}: race {c * w * gt.RACE_R / 1000:.3f} + bushing {t_b:.3f} "
              f"= {t:.3f} N m ({t / T_MOTOR:.0%} of {T_MOTOR})")
    t = C_ROLL[1] * w * gt.RACE_R / 1000 + t_b
    ok = t < 0.5 * T_MOTOR
    print(f"  worst case (full pools, c=0.01, 5 m/s side load {side:.1f} N on the bushing) "
          f"-> {gt.ok(ok)}")
    head = (Z_P - (gt.Z_LID0 - 60)) / 1000
    q = Q_MAX * max(0.0, 1 - head / H_MAX)
    print(f"  pump: lift {head:.2f} m from a full tank -> ~{q:.0f} L/h "
          f"({weir_head(q, N_SCUP):.1f} mm over the scuppers)")
    return ok, total, plastic


# ---- section -------------------------------------------------------------------
def section(base, own):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Polygon
    col = {"tank": "#3d4a3f", "lid": "#56645a", "fill": "#56645a", "hub": "#2b2b2b",
           "leg": "#2b2b2b", "pod": "#7a6a55", "pinion": "#c9a227", "rotor": "#b8862e",
           "pipe": "#9fb7c9", "float": "#4a90c2", "adapter": "#a8743a",
           "bowl": "#f2c6d4", "distributor": "#c9b458"}
    parts = dict(base, **own, pipe=pipe())
    ang = pot_ang(0, 0)
    fig, ax = plt.subplots(figsize=(9, 16), dpi=110)
    seen = set()
    for name, m in parts.items():
        key = name.rstrip("0123456789").rstrip("_")
        c = next((v for kk, v in col.items() if name.startswith(kk)), "#999")
        for poly in m.rotate((0, 0, -ang)).rotate((-90, 0, 0)).slice(0.0).to_polygons():
            ax.add_patch(Polygon(poly, closed=True, fc=c, ec="k", lw=0.4,
                                 label=key if key not in seen else None))
            seen.add(key)
    blue = "#1f77b4"
    for k in range(len(N_POTS)):                    # pool surfaces
        rr = core_r(k)[1] - 3
        z = Z_BOWL[k] + FT + POOL
        for s in (1, -1):
            ax.plot([s * STEM_RO, s * rr], [z, z], color=blue, lw=1.5, alpha=0.7)
    ax.annotate("", (0, Z_P + 5), (0, gt.TANK_FLOOR + 60),
                arrowprops=dict(arrowstyle="->", color=blue, lw=2.5))
    for s in (1, -1):
        ax.annotate("", (s * (BELL_RI - 1), Z_P + 4), (s * 9, Z_P + 5),
                    arrowprops=dict(arrowstyle="->", color=blue, lw=1.5))
        ax.annotate("", (s * (BELL_RI + 1), Z_BOWL[5] + FT + POOL), (s * (BELL_RI + 1), Z_P - BELL_DROP),
                    arrowprops=dict(arrowstyle="->", color=blue, lw=1.5))
    ra = math.radians(scup_angs(0)[0] - ang)
    for k in range(len(N_POTS)):                    # scupper threads (shown at r_scup)
        z_to = Z_BOWL[k - 1] + FT + POOL if k else gt.Z_L - 4
        for s in (1, -1):
            ax.annotate("", (s * R_SCUP, z_to), (s * R_SCUP, Z_BOWL[k]),
                        arrowprops=dict(arrowstyle="->", color=blue, lw=1.2, ls="--"))
    ax.annotate("bell distributor (fixed)\nbowl_6 stem = top bushing", (BELL_RO, Z_P),
                (110, Z_P + 50), arrowprops=dict(arrowstyle="->"), fontsize=9)
    ax.annotate("15 mm pool, set by scupper\nstandpipes (weep -> ebb)", (R_SCUP + 4, Z_BOWL[3] + 18),
                (140, Z_BOWL[3] + 60), arrowprops=dict(arrowstyle="->"), fontsize=9)
    ax.annotate("2\" net pot sleeve, 20 deg", axis_pt(2, 0, 40)[0::2], (150, Z_BOWL[2] + 110),
                arrowprops=dict(arrowstyle="->"), fontsize=9)
    ax.annotate("adapter: tier spigot +\n45 deg drain funnel", (FUNNEL_R + 10, Z_SEAT),
                (150, Z_SEAT - 90), arrowprops=dict(arrowstyle="->"), fontsize=9)
    ax.annotate("threads fall straight down\n(no lip spill: wind)", (-R_SCUP, Z_BOWL[4] - 50),
                (-300, Z_BOWL[4] - 20), arrowprops=dict(arrowstyle="->"), fontsize=9)
    ax.set_xlim(-gt.LEG_R_END - 10, gt.LEG_R_END + 10)
    ax.set_ylim(-gt.HUB_T - 20, Z_TOP + 60)
    ax.set_aspect("equal")
    ax.set_xlabel("mm")
    ax.set_title(f"Lotus Cascade: {len(N_POTS)} bowls, {sum(N_POTS)} plants, "
                 f"{Z_TOP + gt.HUB_T:.0f} mm tall (cut at {ang:.0f} deg)")
    ax.legend(loc="upper left", fontsize=7)
    ax.grid(alpha=0.25)
    fig.savefig(os.path.join(HERE, "preview", "section_2d.png"), bbox_inches="tight")


# ---- print checks + export --------------------------------------------------------
def overhang(m, rot):
    """Down-facing area steeper than 45 deg (mm^2), bed face excluded."""
    tm = gt.to_trimesh(rot(m) if rot else m)
    z0 = tm.bounds[0][2]
    n = tm.face_normals
    zc = tm.triangles_center[:, 2]
    bad = (n[:, 2] < -0.72) & (zc > z0 + 0.05)
    return float(tm.area_faces[bad].sum())


ORIENT = {"adapter": (None, "spigot down"), "distributor": (gt.FLIP, "bell rim up")}
for _k in range(len(N_POTS)):
    ORIENT[f"bowl_{_k + 1}"] = (None, "floor down")


def export(base, own):
    print("-- print overhangs > 45 deg (bed face excluded): only bridges over the "
          "1.8 mm weeps, 1 mm drip grooves, 2.6 mm jets, 3.6 mm pin holes")
    for n, m in own.items():
        print(f"  {n:12s} {overhang(m, ORIENT[n][0]):7.1f} mm^2")
    preview = {n: f"preview/{n}.stl" for n in base}
    preview.update(own)
    preview["pipe"] = pipe()
    meta = {n: gt.base_meta(n) for n in base}
    meta["pipe"] = gt.base_meta("pipe")
    meta["adapter"] = ("#a8743a", 4, True)
    for k in range(len(N_POTS)):
        meta[f"bowl_{k + 1}"] = ("#f2c6d4" if k % 2 == 0 else "#f8e1e8", 5 + k, True)
    meta["distributor"] = ("#c9b458", 11.5)
    return gt.export_set(HERE, own, ORIENT, {}, preview, meta,
                         f"Lotus Cascade: {len(N_POTS)} bowls, {sum(N_POTS)} plants",
                         target_z=820.0)


def main():
    base, leg, own = build()
    print("-- lotus cascade")
    for k in range(len(N_POTS)):
        rf, rr = core_r(k)
        print(f"  bowl_{k + 1}: z={Z_BOWL[k]:.0f}  {N_POTS[k]} pots at r={R_POT[k]:.0f}  "
              f"core r {rf:.0f}->{rr:.0f}")
    print(f"  pipe 1/2in PVC {Z_P - gt.PIPE_Z0:.0f} mm, top z={Z_P:.0f}; "
          f"height on stand {Z_TOP + gt.HUB_T:.0f} mm")
    ok = checks(base, own)
    ok_m, _, _ = mass_torque(own)
    os.makedirs(os.path.join(HERE, "preview"), exist_ok=True)
    section(base, own)
    ok_e = export(base, own)
    print(f"-- all checks -> {gt.ok(ok and ok_m and ok_e)}")


if __name__ == "__main__":
    main()
