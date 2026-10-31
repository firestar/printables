"""2D layout + sections: side cut along the card path (y = 0.3), top view at the
track plane, a zoom of the sleeve station (tongues, platen, pusher) and a cross
cut through the scan station (x = camera axis).
Run: PYTHONPATH=../../.pydeps python3 section.py"""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import PathPatch
from matplotlib.path import Path

import card_scanner as cs

Y_TO_Z = [[1, 0, 0, 0], [0, 0, 1, 0], [0, 1, 0, 0]]      # (x, z) view of the plane y = c
X_TO_Z = [[0, 1, 0, 0], [0, 0, 1, 0], [1, 0, 0, 0]]      # (y, z) view of the plane x = c


def draw(ax, m, h, fc, lw=0.35):
    """Slice m at height h; all contours in one even-odd path so holes stay open."""
    verts, codes = [], []
    for poly in m.slice(h).to_polygons():
        verts += [tuple(p) for p in poly] + [tuple(poly[0])]
        codes += [Path.MOVETO] + [Path.LINETO] * (len(poly) - 1) + [Path.CLOSEPOLY]
    if verts:
        ax.add_patch(PathPatch(Path(verts, codes), fc=fc, ec="k", lw=lw))


def colour(name, group):
    if group == "frame":
        return "#c9cdd1"
    if group == "component":
        if name.startswith("glass"):
            return "#bfe3ff"
        if "card" in name or name.startswith("sleeve"):
            return "#f4a261"
        if "shim" in name:
            return "#7f8c8d"
        return "#2d6a4f"
    return cs.colour(name)


def main():
    A, _, ext = cs.build()
    comps = cs.components(cs.POSE)
    objs = [(k, m, "part") for k, (_, m) in A.items()]
    objs += [(k, m, "component") for k, m in comps.items()]
    objs += [(k, m, "frame") for k, m in ext.items()]
    fig = plt.figure(figsize=(20, 17), dpi=100)
    ax1 = fig.add_subplot(3, 1, 1)
    ax2 = fig.add_subplot(3, 1, 2)
    ax3 = fig.add_subplot(3, 2, 5)
    ax4 = fig.add_subplot(3, 2, 6)
    for n, m, g in objs:
        mm = cs.xform(m, Y_TO_Z)
        draw(ax1, mm, 0.3, colour(n, g))
        draw(ax3, mm, 0.3, colour(n, g), 0.25)
        draw(ax2, m, cs.Z_TRACK + 0.15, colour(n, g))
        draw(ax4, cs.xform(m, X_TO_Z), cs.X_SCAN, colour(n, g))
    stations = [("hopper", cs.X_HOP), ("feed", cs.X_FEED), ("scan_in", cs.X_SCAN_IN), ("camera", cs.X_SCAN),
                ("scan_out", cs.X_SCAN_OUT), ("stop", cs.X_STOP), ("xfer", cs.X_XFER), ("entry", cs.X_ENTRY),
                ("mouth", cs.X_MOUTH), ("exit", cs.X_EXIT), ("diverter", cs.X_DIV)]
    for i, (n, x) in enumerate(stations):
        for ax, y in ((ax1, 250 + 10 * (i % 2)), (ax2, 190 + 10 * (i % 2))):
            ax.axvline(x, color="#1f77b4", lw=0.5, ls="--")
            ax.text(x, y, f"{n}\n{x:.0f}", ha="center", fontsize=7, color="#1f77b4")
    ax1.set_title(f"Side cut y = 0.3 along the card path ({cs.CARD} card, track z {cs.Z_TRACK:.0f}, "
                  f"CM3 WD {cs.WD:.0f} mm above/below)")
    ax1.set_xlim(-130, 810)
    ax1.set_ylim(-70, 275)
    ax2.set_title("Top view at the track plane (z = track + 0.15)")
    ax2.set_xlim(-130, 810)
    ax2.set_ylim(-265, 215)
    x0 = cs.X_MOUTH
    ax3.set_title("Sleeve station zoom (y = 0.3): throat, tongues inserted 15 mm, platen, pusher pawl, exit nip")
    ax3.set_xlim(x0 - 70, x0 + 140)
    ax3.set_ylim(cs.Z_PLATEN - 40, cs.Z_PLATEN + 50)
    zp = cs.Z_PLATEN
    for z, lab in ((zp + cs.Z_SHIM_HI, "upper shim"), (zp + cs.Z_CARD_S, "card"), (zp + cs.Z_SHIM_LO, "lower shim")):
        ax3.annotate(lab, xy=(x0 + 10, z), xytext=(x0 + 45, z + 18 - (8 if lab == "card" else 0)
                                                   - (16 if lab == "lower shim" else 0)),
                     fontsize=7, arrowprops=dict(arrowstyle="->", lw=0.6))
    ax4.set_title(f"Scan cross cut x = {cs.X_SCAN:.0f}: hood, CM3 top/bottom, LED frames, glass, lower shroud")
    ax4.set_xlim(-110, 110)
    ax4.set_ylim(0, 240)
    for ax in (ax1, ax2, ax3, ax4):
        ax.set_aspect("equal")
        ax.grid(alpha=0.25)
        ax.set_xlabel("mm")
    fig.tight_layout()
    os.makedirs(os.path.join(cs.OUT, "preview"), exist_ok=True)
    fig.savefig(os.path.join(cs.OUT, "preview", "section_2d.png"), bbox_inches="tight")


if __name__ == "__main__":
    main()
