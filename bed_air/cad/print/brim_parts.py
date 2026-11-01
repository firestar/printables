"""P1S print copies of the standing duct parts (segment, segment_vented,
diffuser): rotated 45 deg so the flat profile sits diagonally on the 256 bed,
plus a modelled brim around the socket rim they stand on (2.4 mm wall only).
The outside brim is limited by the bed; the inside one is wider.
Trim the brim off after printing.
Run: PYTHONPATH=../../../.pydeps python3 brim_parts.py
"""
import os

import manifold3d as m3d
import numpy as np
import trimesh

HERE = os.path.dirname(os.path.abspath(__file__))
PARTS = ("segment", "segment_vented", "diffuser")
BED = 256.0 - 2 * 3.0      # usable P1S bed
BRIM_OUT = 6.0
BRIM_IN = 15.0
BRIM_T = 0.4               # two 0.2 mm layers


def load(name):
    tm = trimesh.load(os.path.join(HERE, "..", "stl", f"{name}.stl"))
    return m3d.Manifold(m3d.Mesh(vert_properties=np.asarray(tm.vertices, np.float32),
                                 tri_verts=np.asarray(tm.faces, np.uint32)))


for name in PARTS:
    part = load(name)
    base = part.slice(0.1)
    outer = base.offset(BRIM_OUT, m3d.JoinType.Round, circular_segments=96)
    # inner brim: fill BRIM_IN inward from the rim, i.e. shrink the hole
    hull = m3d.CrossSection.hull(base)
    inner = hull - hull.offset(-BRIM_IN, m3d.JoinType.Round, circular_segments=96)
    brim = m3d.Manifold.extrude((outer - hull) + inner, BRIM_T)
    m = (part + brim).rotate((0, 0, 45))
    mesh = m.to_mesh()
    out = trimesh.Trimesh(np.asarray(mesh.vert_properties)[:, :3], np.asarray(mesh.tri_verts))
    out.apply_translation(-out.bounds[0] - np.r_[out.extents[:2] / 2, 0])
    path = os.path.join(HERE, f"{name}_p1s_brim.stl")
    out.export(path)
    fits = max(out.extents[:2]) <= BED and out.extents[2] <= 256 - 3
    print(f"{name:15s} size {np.round(out.extents, 1)} fits P1S {fits}")
