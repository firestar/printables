"""Print copy of the adapter for the P1S: rotated 45 deg so the flat end fits the
256 bed, plus a modelled brim on both sides of the spigot rim (the part stands
on a 2.4 mm wall ring only).  Trim the brim off after printing.
Run: PYTHONPATH=../../../.pydeps python3 adapter_brim.py
"""
import os

import manifold3d as m3d
import numpy as np
import trimesh

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "stl", "adapter.stl")
OUT = os.path.join(HERE, "adapter_p1s_brim.stl")

HOSE_R, WALL = 75.0, 2.4   # matches bed_air.py
BRIM_W = 15.0
BRIM_T = 0.4               # two 0.2 mm layers

tm = trimesh.load(SRC)
part = m3d.Manifold(m3d.Mesh(vert_properties=np.asarray(tm.vertices, np.float32),
                             tri_verts=np.asarray(tm.faces, np.uint32)))
ring = lambda r0, r1: m3d.Manifold.cylinder(BRIM_T, r1, r1, 192) - \
    m3d.Manifold.cylinder(3 * BRIM_T, r0, r0, 192).translate((0, 0, -BRIM_T))
brim = ring(HOSE_R - 0.2, HOSE_R + BRIM_W) + ring(HOSE_R - WALL - BRIM_W, HOSE_R - WALL + 0.2)
m = (part + brim).rotate((0, 0, 45))
mesh = m.to_mesh()
out = trimesh.Trimesh(np.asarray(mesh.vert_properties)[:, :3], np.asarray(mesh.tri_verts))
out.export(OUT)
print("size", np.round(out.extents, 1), "watertight", out.is_watertight,
      "base area cm2", round(np.pi * ((HOSE_R + BRIM_W) ** 2 - (HOSE_R - WALL - BRIM_W) ** 2) / 100))
