"""One 120 mm high-flow fan (230 CFM class) -> TWO Tesla V100 PCIe tails.

gpu_duct.py with the measured tail size and the press-fit sleeve from
v100_single.py (fit-tested at 0.3 mm/side): the splitter halves the air and its
fin fills the gap between the cards, so neither card can starve the other.
Set PITCH to your slot spacing (2 slots = 40.64 mm, 3 slots = 60.96 mm).

Run: PYTHONPATH=../../.pydeps python3 v100_pair.py
"""
import os

import numpy as np

import gpu_duct as gd
import v100_single as vs

PITCH = 100.7               # measured on the Kingwin frame: card A left screw -> card B left screw


def configure():
    vs.configure(vs.CLR)
    gd.N_CARDS = 2
    gd.PITCH = PITCH
    gd.ENV_X = PITCH + gd.CARD_T
    gd.ENV_Y = gd.CARD_H
    gd.FIN_T = PITCH - gd.CARD_T - 2 * gd.GAP_CLR


def main():
    configure()
    duct = gd.make_duct()
    cards = [gd.make_card(k) for k in range(2)]
    print(f"-- V100 pair: envelope {gd.ENV_X:.1f} x {gd.ENV_Y:.1f} mm, pitch {PITCH} mm, "
          f"{vs.CLR} mm/side, {gd.SLV:.0f} mm deep")
    for k, c in enumerate(cards):
        ov = (duct ^ c).volume()
        print(f"  card {k + 1}: overlap {ov:.3f} mm3, min gap {duct.min_gap(c, 5.0):.2f} "
              f"-> {gd.ok(ov < 1e-2)}")
    print(f"  gap fin {gd.FIN_T:.2f} mm in the {PITCH - gd.CARD_T:.2f} mm card gap "
          f"-> {gd.ok(gd.FIN_T > 1.6)}")
    tm = gd.to_trimesh(duct)
    down = (tm.face_normals[:, 2] < -np.cos(np.radians(45)) - 1e-3) & (tm.triangles_center[:, 2] > 0.2)
    print(f"  overhang > 45 deg (excluding bed): {tm.area_faces[down].sum():.1f} mm2")
    os.makedirs(os.path.join(gd.OUT, "stl"), exist_ok=True)
    vs.export("v100_pair_duct", duct)


if __name__ == "__main__":
    main()
