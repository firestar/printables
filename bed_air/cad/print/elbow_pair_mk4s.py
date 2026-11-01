"""Nest two elbow halves (cut face down) on one Prusa MK4S plate (250 x 210).
Run: PYTHONPATH=../../../.pydeps python3 elbow_pair_mk4s.py
"""
import itertools
import os

import manifold3d as m3d
import numpy as np
import trimesh

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "stl", "elbow_half.stl")
OUT = os.path.join(HERE, "elbow_half_x2_mk4s.stl")
BX, BY = 240.0, 200.0      # usable plate after margins
GAP = 5.0

tm = trimesh.load(SRC)
part = m3d.Manifold(m3d.Mesh(vert_properties=np.asarray(tm.vertices, np.float32),
                             tri_verts=np.asarray(tm.faces, np.uint32)))
foot = part.project()


def bbox(cs):
    b = cs.bounds()
    return b[2] - b[0], b[3] - b[1]


best = None
for a, b2 in itertools.product(range(0, 180, 5), (0, 90, 180, 270)):
    fa = foot.rotate(a)
    fb = foot.rotate(a + b2)
    ba, bb = fa.bounds(), fb.bounds()
    ga = fa.offset(GAP / 2, m3d.JoinType.Round)
    gb = fb.offset(GAP / 2, m3d.JoinType.Round)
    for dx in np.arange(-260, 260, 4.0):
        for dy in np.arange(-220, 220, 4.0):
            w = max(ba[2], bb[2] + dx) - min(ba[0], bb[0] + dx)
            h = max(ba[3], bb[3] + dy) - min(ba[1], bb[1] + dy)
            if w > BX or h > BY or (best and w * h >= best[0]):
                continue
            if (ga ^ gb.translate((dx, dy))).area() > 0:
                continue
            best = (w * h, a, b2, dx, dy, w, h)
if best is None:
    raise SystemExit("no fit")
_, a, b2, dx, dy, w, h = best
pa = part.rotate((0, 0, a))
pb = part.rotate((0, 0, a + b2)).translate((dx, dy, 0))
m = pa + pb
mesh = m.to_mesh()
out = trimesh.Trimesh(np.asarray(mesh.vert_properties)[:, :3], np.asarray(mesh.tri_verts))
out.apply_translation(-out.bounds[0] - np.r_[out.extents[:2] / 2, 0])
out.export(OUT)
print(f"rot {a} / +{b2}, offset ({dx:.0f},{dy:.0f}), plate footprint {w:.0f} x {h:.0f}")
