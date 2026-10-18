"""2D sections: duct profile through a vent slot (with sliders), diffuser
through the louvres, and a long cut through the foot end.
Run: PYTHONPATH=../../.pydeps python3 section.py"""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import PathPatch, Polygon
from matplotlib.path import Path

import bed_air as ba


def draw(ax, m, z, fc, label=None):
    """Slice m at height z; all contours in one even-odd path so holes stay open."""
    verts, codes = [], []
    for poly in m.slice(z).to_polygons():
        verts += [tuple(p) for p in poly] + [tuple(poly[0])]
        codes += [Path.MOVETO] + [Path.LINETO] * (len(poly) - 1) + [Path.CLOSEPOLY]
    if verts:
        ax.add_patch(PathPatch(Path(verts, codes), fc=fc, ec="k", lw=0.4, label=label))


def main():
    vseg, dif = ba.make_segment_vented(), ba.make_diffuser()
    sl = [ba.make_slider(1), ba.make_slider(-1)]
    fig = plt.figure(figsize=(14, 12), dpi=110)
    ax1 = fig.add_subplot(3, 1, 1)
    zs = ba.SLOTS[1] + ba.SLOT_L / 2
    draw(ax1, vseg, zs, "#dcd5c4", "vented segment")
    for k, s in enumerate(sl):
        draw(ax1, s, zs, "#d0763a", "slider (open)" if k == 0 else None)
    ax1.set_title(f"Vented segment through a slot: {ba.W:.0f} x {ba.H:.0f} mm, "
                  f"{len(ba.WEB_X)} webs, dovetail slider each flank")
    ax2 = fig.add_subplot(3, 1, 2)
    draw(ax2, dif, (ba.DZ0 + ba.DZ1) / 2, "#5b7fa6", "diffuser")
    ax2.set_title("Diffuser through the louvres (top + both flanks, slats aim toward the feet)")
    ax3 = fig.add_subplot(3, 1, 3)
    parts, _ = ba.build()
    ax3.add_patch(Polygon([(0, 0), (700, 0), (700, -300), (0, -300)], closed=True,
                          fc="#cfd8e3", ec="none", alpha=0.5, label="mattress"))
    for n, c in (("adapter", "#5b7fa6"), ("elbow_a", "#4a6d94"), ("seg_1", "#e9e4d8"),
                 ("seg_2", "#dcd5c4")):
        m = parts[n].rotate((-90, 0, 0))           # world y -> -z, z -> y
        draw(ax3, m, -40.0, c, n)
    ax3.set_title("Foot end, cut at y = 40: hose spigot -> adapter -> elbow -> segments")
    for ax in (ax1, ax2):
        ax.set_xlim(-ba.W / 2 - 10, ba.W / 2 + 10)
        ax.set_ylim(-ba.H / 2 - 5, ba.H / 2 + 5)
    ax3.set_xlim(-250, 700)
    ax3.set_ylim(-320, 120)
    ax3.set_xlabel("mm")
    for ax in (ax1, ax2, ax3):
        ax.set_aspect("equal")
        ax.grid(alpha=0.25)
        ax.legend(loc="upper right", fontsize=7)
    fig.tight_layout()
    os.makedirs(os.path.join(ba.OUT, "preview"), exist_ok=True)
    fig.savefig(os.path.join(ba.OUT, "preview", "section_2d.png"), bbox_inches="tight")


if __name__ == "__main__":
    main()
