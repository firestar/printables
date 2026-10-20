"""2D sections of the indoor mounts -> preview/section_2d.png:
post (fingerprint arm) cut on the ball axis y = YC with the cable path down the
pipe, a zoom of the post base cut x = XB (pipe stop cone, cable window, duct,
ballast), the tabletop base cut beside the cable duct and across the ballast
pockets.
Run: PYTHONPATH=../../../.pydeps python3 section.py"""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import PathPatch
from matplotlib.path import Path
import numpy as np

import indoor as ind

mb = ind.mb
Y_TO_Z = [[1, 0, 0, 0], [0, 0, 1, 0], [0, 1, 0, 0]]      # (x, z) view of the plane y = c
X_TO_Z = [[0, 1, 0, 0], [0, 0, 1, 0], [1, 0, 0, 0]]      # (y, z) view of the plane x = c


def draw(ax, m, h, fc, label=None):
    """Slice m at height h; all contours in one even-odd path so holes stay open."""
    verts, codes = [], []
    for poly in m.slice(h).to_polygons():
        verts += [tuple(p) for p in poly] + [tuple(poly[0])]
        codes += [Path.MOVETO] + [Path.LINETO] * (len(poly) - 1) + [Path.CLOSEPOLY]
    if verts:
        ax.add_patch(PathPatch(Path(verts, codes), fc=fc, ec="k", lw=0.3, label=label))


def colour(name, me):
    if me["group"] == "component":
        return "#2e8b57"
    if name.endswith("ballast"):
        return "#c8a96a"
    if name == "post_pipe":
        return "#8c959e"
    if me["group"] == "context":
        return "#e6e1d6"
    if name.startswith("post_"):
        return "#2f6b3e"
    if name.startswith("table_"):
        return "#555b62"
    return "#aab0b6"


def cut(ax, objs, view, c, labels=()):
    seen = set()
    for n, (m, me) in objs.items():
        if n == "magicband":
            continue
        key = n.split("_")[0] + "_" + n.split("_")[1] if n.startswith(("post_collar", "post_sleeve")) else n
        lab = key if key in labels and key not in seen else None
        seen.add(key)
        draw(ax, ind.xform(m, view), c, colour(n, me), lab)


def path_xy(path, axes):
    p = np.array([tuple(q) for q in path])
    return p[:, axes[0]], p[:, axes[1]]


def main():
    singles, objs, L = ind.build()
    cache = {}
    XB, YC = mb.XB, mb.YC
    post = ind.combo(objs, L, "fp", "post", "aio", cache)
    table = ind.combo(objs, L, "fp", "table", "aio", cache)
    fig = plt.figure(figsize=(18, 16), dpi=100)
    gs = fig.add_gridspec(2, 3, width_ratios=[0.8, 1.2, 1.2])
    ax1 = fig.add_subplot(gs[:, 0])
    labels = ("post_base", "post_floor", "post_collar", "post_sleeve", "post_saddle", "post_pipe", "post_ballast",
              "arm_base", "ball_rear", "floor")
    cut(ax1, post, Y_TO_Z, YC + 0.3, labels)
    cable = ind.cable_path("fp", "post", L)[-1][1]
    ax1.plot(*path_xy(cable, (0, 2)), "r--", lw=1.2, label="cable (6 mm)")
    ax1.set_title(f"Post, cut y = ball axis: face centre {ind.FACE_H:.0f}, {ind.PIPE.upper()} "
                  f"D{ind.PIPE_OD} x {L['pipe_len']:.0f}", fontsize=10)
    ax1.set_xlim(XB - 170, XB + 170)
    ax1.set_ylim(-30, ind.FACE_H + 120)
    ax1.legend(loc="upper left", fontsize=7)
    ax2 = fig.add_subplot(gs[0, 1:])
    cut(ax2, post, X_TO_Z, XB + 3.0)
    ax2.plot(*path_xy(cable, (1, 2)), "r--", lw=1.5)
    ax2.set_title("Post base, cut x = pipe axis + 3: pipe on the 35 deg stop cone, cable out of the tube window, "
                  "through the duct and the rim notch at the back; sand ballast in the pockets", fontsize=10)
    ax2.set_xlim(YC - ind.PB_R - 15, YC + ind.PB_R + 15)
    ax2.set_ylim(-25, 140)
    ax3 = fig.add_subplot(gs[1, 1])
    cut(ax3, table, X_TO_Z, XB + 15.0)
    tcable = ind.cable_path("fp", "table", L)[-1][1]
    ax3.plot(*path_xy(tcable, (1, 2)), "r--", lw=1.5, label="cable (at x = seat, behind the cut)")
    ax3.set_title("Tabletop base, cut x = seat + 15: service bay, ballast pockets, duct", fontsize=10)
    ax3.set_xlim(YC - 100, YC + 100)
    ax3.set_ylim(-30, 120)
    ax3.legend(loc="upper right", fontsize=7)
    ax4 = fig.add_subplot(gs[1, 2])
    cut(ax4, table, Y_TO_Z, YC + 40.0)
    ax4.set_title("Tabletop base + arm, cut y = ball axis + 40: ballast pockets along the base", fontsize=10)
    ax4.set_xlim(XB - 200, XB + 200)
    ax4.set_ylim(-30, 260)
    for ax in (ax1, ax2, ax3, ax4):
        ax.set_aspect("equal")
        ax.grid(alpha=0.25)
        ax.set_xlabel("mm")
    fig.tight_layout()
    os.makedirs(os.path.join(ind.OUT, "preview"), exist_ok=True)
    fig.savefig(os.path.join(ind.OUT, "preview", "section_2d.png"), bbox_inches="tight")


if __name__ == "__main__":
    main()
