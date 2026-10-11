"""Check that the real parts fit: simple solid models of each board / driver
(with headers, connectors, magnet) are placed where they mount and tested for
collisions against the printed parts, plus a picture of the bay layout.

Run: PYTHONPATH=../.pydeps python3 check_fit.py
"""
import math
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon

import round_sub as rs
from round_sub import box, cyl, vol


def esp32():
    """Hosyond 30-pin devkit on its ledges, USB-C toward +X."""
    rb_in = rs.skin_r(rs.Z_FLOOR) - rs.T / rs.COS
    xu = rb_in - 3.0
    xa = xu - 51.0                                   # real board 51 x 28
    z = rs.ESP_LEDGE
    pcb = box(xa, xu, -14, 14, z, z + 1.6)
    module = box(xa, xa + 25.5, -9, 9, z + 1.6, z + 4.8)          # WROOM can
    usb = box(xu - 7.3, xu + 0.8, -4.5, 4.5, z + 1.6, z + 4.8)    # USB-C receptacle
    pins = box(xa + 7.5, xu - 7.5, -11.43 - 1.27, -11.43 + 1.27, z - 8.5, z)
    pins = pins + pins.mirror((0, 1, 0))
    dupont = box(xa + 7.5, xu - 7.5, -11.43 - 1.3, -11.43 + 1.3, z - 16.5, z - 2.5)
    dupont = dupont + dupont.mirror((0, 1, 0))
    return pcb + module + usb + pins, dupont


def usb_plug():
    rb_in = rs.skin_r(rs.Z_FLOOR) - rs.T / rs.COS
    xu = rb_in - 3.0
    z = rs.ESP_LEDGE + 1.6 + 1.6
    metal = box(xu - 6.5, xu + 0.8, -4.2, 4.2, z - 1.3, z + 1.3)
    over = box(xu + 0.8, xu + 25, -6.2, 6.2, z - 3.25, z + 3.25)   # overmold
    return metal + over


def amp():
    """MAX98357A 18 x 20.1 on the platform, header edge overhanging +X."""
    rb_in = rs.skin_r(rs.Z_FLOOR) - rs.T / rs.COS
    xa = (rb_in - 3.0) - rs.ESP_L
    cx = xa - 22.0
    x0 = cx - rs.AMP_PLAT_D / 2
    z = rs.AMP_PLAT_H
    worst = None
    for d, w in ((rs.AMP_L, rs.AMP_W), (rs.AMP_W, rs.AMP_L)):     # both orientations
        pcb = box(x0, x0 + d, -w / 2, w / 2, z, z + 1.6)
        hdr = box(x0 + d - 2.5, x0 + d, -8.9, 8.9, z - 8.5, z)
        term = box(x0 + 2, x0 + 9.5, -5, 5, z + 1.6, z + 11)      # 5.08 mm terminal
        part = pcb + hdr + term
        worst = part if worst is None else worst + part
    return worst


def mics():
    out = None
    rb_in = rs.skin_r(rs.Z_FLOOR) - rs.T / rs.COS
    seat = rb_in - 0.4
    for ang in rs.MIC_ANGS:
        m = m3d_cyl_x(seat - 1.6, seat, rs.MIC_PCB_D / 2) + \
            box(seat - 1.6 - 1.0, seat - 1.6, -2, 2, rs.MIC_Z - 1.5, rs.MIC_Z + 1.5)
        m = m.rotate((0, 0, ang))
        out = m if out is None else out + m
    return out


def m3d_cyl_x(x0, x1, r):
    import manifold3d as m3d
    c = m3d.Manifold.cylinder(x1 - x0, r, r, 64)
    return c.rotate((0, 90, 0)).translate((x0, 0, rs.MIC_Z))


def speaker():
    """Gikfun EK1725, rear mounted: frame in the baffle pocket, 30 mm deep."""
    import manifold3d as m3d
    top = rs.Z_B + rs.SPK_POCKET
    f = rs.SPK_FRAME / 2
    frame = box(-f, f, -f, f, top - 1.0, top)
    basket = m3d.Manifold.cylinder(30 - 8 - 1, 39.5 / 2, 50.8 / 2, 64).translate((0, 0, top - 22))
    magnet = cyl(8, 39.5 / 2, z=top - 30, seg=64)
    return frame + basket + magnet


def main():
    baffle, body, base = rs.make_baffle(), rs.make_body(), rs.make_base()
    printed = baffle + body + base
    esp, dupont = esp32()
    parts = {
        "ESP32 board + pins": esp,
        "Dupont housings under ESP32": dupont,
        "USB-C plug in slot": usb_plug(),
        "MAX98357A (both orientations)": amp(),
        "INMP441 x2": mics(),
        "Gikfun driver": speaker(),
    }
    ok = True
    for name, p in parts.items():
        hit = vol(p ^ printed)
        print(f"{name:32s} collision {hit:8.3f} mm^3 -> {'OK' if hit < 0.01 else 'FAIL'}")
        ok &= hit < 0.01
    # board-to-board
    names = list(parts)
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            hit = vol(parts[names[i]] ^ parts[names[j]])
            mated = [{"ESP32 board + pins", "Dupont housings under ESP32"},   # plugged on
                     {"ESP32 board + pins", "USB-C plug in slot"}]          # plugged in
            if hit > 0.01 and {names[i], names[j]} not in mated:
                print(f"  {names[i]} x {names[j]}: {hit:.2f} mm^3 FAIL")
                ok = False
    print("ALL PARTS FIT" if ok else "FIT PROBLEMS")

    # top-down layout of the bay at board height
    fig, ax = plt.subplots(figsize=(9, 9), dpi=110)
    for m, c, lab in [(base, "#6a6f7a", "base"), (esp, "#1f77b4", "ESP32"),
                      (amp(), "#9467bd", "MAX98357A"), (mics(), "#2ca02c", "INMP441"),
                      (usb_plug(), "#ff7f0e", "USB-C plug")]:
        cs = m.project()
        for k, poly in enumerate(cs.to_polygons()):
            ax.add_patch(Polygon(poly, fc=c, ec="k", lw=0.4, alpha=0.55 if lab != "base" else 0.25,
                                 label=lab if k == 0 else None))
    # cable runs through the wire guides
    rb_in = rs.skin_r(rs.Z_FLOOR) - rs.T / rs.COS
    cl = rs.wire_routes(rb_in)
    edge = lambda ang: rs.polar(rb_in + 2, ang)
    runs = [("mic L", "#2ca02c", [edge(90)] + [c[:2] for c in cl[0:2]] + [(48, 12)]),
            ("mic R", "#2ca02c", [edge(270)] + [c[:2] for c in cl[2:4]] + [(48, -12)]),
            ("LED lead", "#17becf", [edge(rs.HALO_WIRE_ANG)] + [c[:2] for c in cl[4:7]] + [(48, -12)]),
            ("5 V in", "#d62728", [edge(rs.AUX_ANG)] + [c[:2] for c in cl[7:10]] + [(48, 12)])]
    for lab, c, pts in runs:
        xs, ys = zip(*pts)
        ax.plot(xs, ys, color=c, lw=2.5, ls="--", label=lab)
    clip = rs.wire_clip()
    for k, (x, y, a) in enumerate(cl):
        for poly in clip.rotate((0, 0, a)).translate((x, y, 0)).project().to_polygons():
            ax.add_patch(Polygon(poly, fc="#333", ec="k", lw=0.3,
                                 label="wire guide" if k == 0 and poly is not None and False else None))
    ax.plot([], [], marker="s", color="#333", ls="", label="wire guide")
    ax.set_aspect("equal")
    r = rs.skin_r(rs.Z_FLOOR) + 6
    ax.set_xlim(-r, r + 20)
    ax.set_ylim(-r, r)
    ax.grid(alpha=0.25)
    ax.legend(loc="lower left", fontsize=8)
    ax.set_title("Bay layout, top view (USB-C at +X = down when wall mounted)")
    fig.savefig(os.path.join(rs.OUT, "preview", "bay_layout.png"), bbox_inches="tight")


if __name__ == "__main__":
    main()
