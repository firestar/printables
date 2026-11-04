#!/usr/bin/env python3
"""Printable plate with the interface board's ESP32 hole pattern.

If the devkit's pins drop into the holes and its USB end sits against the two
tabs, the socket footprint on the board fits.  Print flat, no supports, 0.2 mm.

Run from the repo root:  PYTHONPATH=.pydeps python3 smart_speaker/pcb/esp32_fit_gauge.py
Writes esp32_fit_gauge.stl beside this script.
"""
import os

import manifold3d as m3d
import numpy as np
import trimesh

PITCH, ROW_Y, N = 2.54, 12.7, 15      # must match make_pcb.py
USB_EDGE = 9.6                        # pin 1 to USB-end board edge, from make_pcb.py
HOLE_D = 1.5                          # generous: FDM holes print small
T = 3.0
TAB_GAP = 0.4                         # room between board edge and tab
TAB_H = 6.0


def box(x0, x1, y0, y1, z0, z1):
    return m3d.Manifold.cube((x1 - x0, y1 - y0, z1 - z0)).translate((x0, y0, z0))


x_last = -(N - 1) * PITCH
plate = box(x_last - 4, USB_EDGE + TAB_GAP + 2, -ROW_Y - 3, ROW_Y + 3, 0, T)
# Tabs sit outside the USB connector's width, so they only touch the board edge.
for s in (1, -1):
    y0, y1 = sorted((s * 7.0, s * 12.0))
    plate = plate + box(USB_EDGE + TAB_GAP, USB_EDGE + TAB_GAP + 2, y0, y1, T - 0.01, T + TAB_H)
for row in (ROW_Y, -ROW_Y):
    for i in range(N):
        hole = m3d.Manifold.cylinder(T + 2, HOLE_D / 2, HOLE_D / 2, 24).translate((-i * PITCH, row, -1))
        plate = plate - hole

mesh = plate.to_mesh()
tm = trimesh.Trimesh(np.asarray(mesh.vert_properties)[:, :3], np.asarray(mesh.tri_verts), process=False)
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "esp32_fit_gauge.stl")
tm.export(out)
print(f"watertight={tm.is_watertight} size={np.round(tm.extents, 1)} -> {out}")
