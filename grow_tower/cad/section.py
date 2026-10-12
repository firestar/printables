"""2D cut-section through the tower axis (plane through the drive pod).
Run: PYTHONPATH=../../.pydeps python3 section.py"""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon

import grow_tower as gt

COLORS = {"tank": "#3d4a3f", "lid": "#56645a", "fill_plug": "#56645a", "hub": "#2b2b2b",
          "leg": "#2b2b2b", "pod": "#7a6a55", "pinion": "#c9a227", "rotor": "#b8862e",
          "tier": "#e8e2d0", "cap": "#cfc6aa", "spray_head": "#4a90c2",
          "pipe": "#9fb7c9", "pipe_foot": "#4a90c2", "float_bracket": "#4a90c2"}


def color(name):
    for k, c in COLORS.items():
        if name.startswith(k):
            return c
    return "#999999"


def cut(m, ang=0.0):
    """Slice part m by the vertical plane through the axis at angle ang (deg)."""
    return m.rotate((0, 0, -ang)).rotate((-90, 0, 0)).slice(0.0).to_polygons()


def main():
    parts, _, _ = gt.build()
    parts["pipe"] = gt.pipe()
    fig, ax = plt.subplots(figsize=(9, 16), dpi=110)
    seen = set()
    for name, m in parts.items():
        key = name.rstrip("0123456789").rstrip("_")
        for poly in cut(m, gt.POD_ANG):
            ax.add_patch(Polygon(poly, closed=True, fc=color(name), ec="k", lw=0.4,
                                 label=key if key not in seen else None))
            seen.add(key)
    # water path: up the pipe, out of the jets, down the tier wall into the tank
    zj = gt.SPRAY_Z + 6
    ax.annotate("", (0, zj), (0, gt.TANK_FLOOR + 60),
                arrowprops=dict(arrowstyle="->", color="#1f77b4", lw=2.5))
    for s in (1, -1):
        ax.annotate("", (s * (gt.R_TI - 3), zj - 4), (s * 16, zj),
                    arrowprops=dict(arrowstyle="->", color="#1f77b4", lw=2))
        ax.annotate("", (s * (gt.R_TI - 25), gt.Z_L + 2), (s * (gt.R_TI - 3), zj - 20),
                    arrowprops=dict(arrowstyle="->", color="#1f77b4", lw=1.2, ls="--"))
    ax.text(-gt.R_IN + 8, gt.SEC_H, f"tank ~{3.14159 * gt.R_IN ** 2 * (gt.Z_LID0 - 15) / 1e6:.0f} L",
            fontsize=10, color="w")
    ax.annotate("ball race + ring gear\n(only the stack turns)", (gt.RACE_R, gt.Z_L + 2),
                (150, gt.Z_L - 80), arrowprops=dict(arrowstyle="->"), fontsize=9)
    ax.annotate("28BYJ-48 pod", (gt.CENTRE_DIST, gt.Z_L + 15), (150, gt.Z_L + 60),
                arrowprops=dict(arrowstyle="->"), fontsize=9)
    ax.annotate("spray head (fixed)\ncap bushing (turns)", (10, zj), (95, zj + 70),
                arrowprops=dict(arrowstyle="->"), fontsize=9)
    ax.annotate("2\" net-pot port, 45 deg", (95, gt.TIER_Z[2] + 80), (140, gt.TIER_Z[2] + 140),
                arrowprops=dict(arrowstyle="->"), fontsize=9)
    ax.set_xlim(-gt.LEG_R_END - 10, gt.LEG_R_END + 10)
    ax.set_ylim(-gt.HUB_T - 20, gt.CAP_Z + 60)
    ax.set_aspect("equal")
    ax.set_xlabel("mm")
    ax.set_title(f"Rotating aeroponic tower: {gt.N_TIERS} tiers x {gt.N_PORT} ports, "
                 f"{gt.CAP_Z + 8 + gt.HUB_T:.0f} mm tall")
    ax.legend(loc="upper left", fontsize=7)
    ax.grid(alpha=0.25)
    os.makedirs(os.path.join(gt.OUT, "preview"), exist_ok=True)
    fig.savefig(os.path.join(gt.OUT, "preview", "section_2d.png"), bbox_inches="tight")


if __name__ == "__main__":
    main()
