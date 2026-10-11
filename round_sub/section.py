"""2D cut-section drawing through the enclosure axis (like a box sketch's side view).
Run: PYTHONPATH=../.pydeps python3 section.py"""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Polygon

import round_sub as rs


def cut(m, ang=0.0):
    """Slice part m by the vertical plane through the axis at angle ang (deg)."""
    # rotate so the plane becomes z=0 (x stays radial, real z becomes y)
    cs = m.rotate((0, 0, -ang)).rotate((-90, 0, 0)).slice(0.0)
    return cs.to_polygons()


def air_path():
    """Centre-line of the folded port, chamber -> mouth (right half)."""
    zlo = rs.Z_F + 2.5
    zhi = rs.Z_B - 2.5
    pts = [(rs.at(rs.R_CH, rs.Z_F + 25) - 8, rs.Z_F + 25), (rs.R_CH - 3, zlo)]
    for k, (r0, r1) in enumerate(rs.PASSES):
        rc = (r0 + r1) / 2
        lo, hi = (rs.at(rc, zlo), zlo), (rs.at(rc, zhi), zhi)
        pts += [lo, hi] if k % 2 == 0 else [hi, lo]   # up / down
    pts.append((rs.at(rc, rs.H + 6), rs.H + 6))
    return np.array(pts)


def main():
    parts = [(rs.make_baffle(), "#a9824f", "baffle (drops on)"),
             (rs.make_body(), "#dcbc8c", "body (floor + all rings, one print)"),
             (rs.make_base(), "#6a6f7a", "base (electronics bay)")]
    fig, ax = plt.subplots(figsize=(14, 9), dpi=110)
    for m, c, lab in parts:
        for i, poly in enumerate(cut(m, 3.5)):     # 3.5 deg: through the arch windows, misses fins
            ax.add_patch(Polygon(poly, closed=True, fc=c, ec="k", lw=0.5,
                                 label=lab if i == 0 else None))
    p = air_path()
    for sgn in (1, -1):
        q = p * [sgn, 1]
        ax.plot(q[:, 0], q[:, 1], color="red", lw=2.2, alpha=0.85,
                label="port air path" if sgn == 1 else None)
    ax.annotate("2\" driver", (0, rs.H), (0, rs.H + 14), ha="center",
                arrowprops=dict(arrowstyle="->"))
    rm = (rs.at(rs.PASSES[-1][0], rs.H) + rs.R_TOP - rs.T) / 2
    ax.annotate("ring port mouth", (rm, rs.H), (rm - 10, rs.H + 14), ha="center",
                arrowprops=dict(arrowstyle="->"))
    v, length, fb = rs.acoustics()
    ax.text(0, rs.Z_F + rs.PORT_H / 2 - 4, f"chamber\n{v / 1000:.2f} L net", ha="center", fontsize=11)
    ax.text(0, 12, "electronics bay\n(ESP32 + MAX98357)", ha="center", fontsize=10)
    ax.text(0, -18, "back / wall side (keyhole slots)", ha="center", fontsize=10)
    z0 = rs.Z_FLOOR + rs.SOCKET + rs.HALO_GAP
    hp = (rs.skin_r(z0) + rs.HALO_W / 2 / np.sqrt(2), z0 + rs.HALO_W / 2 / np.sqrt(2))
    ax.annotate("LED halo ring\n(aims 45 deg at the wall)", hp, (hp[0] - 30, hp[1] - 30),
                ha="center", arrowprops=dict(arrowstyle="->"))
    ax.annotate("", (hp[0] + 14, hp[1] - 14), hp,
                arrowprops=dict(arrowstyle="->", color="orange", lw=2))
    ax.set_xlim(-rs.R_TOP - 8, rs.R_TOP + 8)
    ax.set_ylim(-25, rs.H + 25)
    ax.set_xlabel("mm")
    ax.set_title(f"Cut section: {rs.N_RINGS}-pass folded ring port, centre -> out "
                 f"({length:.0f} mm long, Fb ~{fb:.0f} Hz)")
    ax.legend(loc="lower right", fontsize=8)
    ax.grid(alpha=0.25)
    os.makedirs(os.path.join(rs.OUT, "preview"), exist_ok=True)
    fig.savefig(os.path.join(rs.OUT, "preview", "section_2d.png"), bbox_inches="tight")


if __name__ == "__main__":
    main()
