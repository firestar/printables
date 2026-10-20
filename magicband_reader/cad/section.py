"""2D sections: vertical cut through ball + neck + arm + pod + bracket (plane
on the ball axis, y = YC), a cut through the ball centre (x = 0) and a zoom of
the face stack with the PN532 antenna -> face distance.
Run: PYTHONPATH=../../.pydeps python3 section.py"""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import PathPatch
from matplotlib.path import Path
import numpy as np

import magicband as mb

COL = {"ball_front": "#c3c8ce", "ball_rear": "#aab0b6", "rear_hatch": "#8f969d", "face_carrier": "#f1f1ee",
       "electronics_tray": "#d8d8d0", "halo_ring": "#bfe3ff", "face_disc": "#18191b", "mickey_inlay": "#fffbe0",
       "neck": "#4a4f55", "arm_base": "#5d6369", "pod_cap": "#7a8188", "wall_bracket": "#3f454b",
       "pn532": "#c0392b", "speaker": "#333333", "led_strip": "#ffd84d", "r503": "#202020",
       "tamper_switch": "#222222", "wall": "#d9d4c7"}


def draw(ax, m, h, fc, label=None):
    """Slice m at height h; all contours in one even-odd path so holes stay open."""
    verts, codes = [], []
    for poly in m.slice(h).to_polygons():
        verts += [tuple(p) for p in poly] + [tuple(poly[0])]
        codes += [Path.MOVETO] + [Path.LINETO] * (len(poly) - 1) + [Path.CLOSEPOLY]
    if verts:
        ax.add_patch(PathPatch(Path(verts, codes), fc=fc, ec="k", lw=0.35, label=label))


def colour(name):
    if "gasket" in name or name == "r503_washer":
        return "#111111"
    return COL.get(name, "#2e8b57")


def main():
    parts, _ = mb.build()
    objs = dict(parts)
    objs.update(mb.components())
    objs["wall"] = mb.context()["wall"]
    y_to_z = [[1, 0, 0, 0], [0, 0, 1, 0], [0, 1, 0, 0]]      # (x, z) view of the plane y = c
    x_to_z = [[0, 1, 0, 0], [0, 0, 1, 0], [1, 0, 0, 0]]      # (y, z) view of the plane x = c
    fig = plt.figure(figsize=(16, 15), dpi=100)
    ax1 = fig.add_subplot(2, 1, 1)
    for n, m in objs.items():
        draw(ax1, mb.xform(m, y_to_z), mb.YC + 0.3, colour(n), n if n in COL else None)
    ax1.set_title(f"Cut y = {mb.YC + 0.3:.1f} (ball axis): ball {2 * mb.R_BALL:.0f}, neck, arm channel "
                  f"(roof 50 deg), pod D{2 * mb.R_POD:.0f} @ x={mb.POD_X:.0f} with R503, bracket shelf")
    ax1.set_xlim(-90, 220)
    ax1.set_ylim(-110, 230)
    ax2 = fig.add_subplot(2, 2, 3)
    ax3 = fig.add_subplot(2, 2, 4)
    for n, m in objs.items():
        mm = mb.xform(m, x_to_z)
        draw(ax2, mm, 0.5, colour(n))
        draw(ax3, mm, 0.5, colour(n), n if n in COL else None)
    ax2.set_title("Cut x = 0.5: wall, hatch, ball halves, carrier, face stack, neck")
    ax2.set_xlim(-45, 175)
    ax2.set_ylim(-110, 230)
    yf, ya = mb.YC + mb.FACE_Y, mb.YC + mb.PN_FRONT
    z = mb.ZC + mb.PN_Z
    ax3.annotate("", xy=(yf, z), xytext=(ya, z), arrowprops=dict(arrowstyle="<->", color="#1f77b4", lw=1.5))
    ax3.text((yf + ya) / 2, z + 2, f"{yf - ya:.1f} mm\nantenna -> face", ha="center", fontsize=8, color="#1f77b4")
    ax3.set_title("Face stack zoom: halo, disc + inlay, LED ring, PN532, speaker duct")
    ax3.set_xlim(mb.YC + 20, mb.YC + 56)
    ax3.set_ylim(mb.ZC - 62, mb.ZC + 62)
    for ax in (ax1, ax2, ax3):
        ax.set_aspect("equal")
        ax.grid(alpha=0.25)
        ax.set_xlabel("mm")
    ax1.legend(loc="upper right", fontsize=7, ncol=2)
    ax3.legend(loc="lower left", fontsize=6)
    fig.tight_layout()
    os.makedirs(os.path.join(mb.OUT, "preview"), exist_ok=True)
    fig.savefig(os.path.join(mb.OUT, "preview", "section_2d.png"), bbox_inches="tight")


if __name__ == "__main__":
    main()
