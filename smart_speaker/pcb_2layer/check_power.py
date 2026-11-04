#!/usr/bin/env python3
"""Production checks that connectivity alone can't show, read from the Gerber zip.

1. Holes: measured from the drill files against the part data they must suit,
   the ESP32 pin grid, and fab limits for annular ring and hole spacing.
2. Current: solves the resistive network of the real copper (both layers, with
   vias) for the 5 V and GND paths at peak load, and reports voltage drop and
   the highest current per mm of copper width, wherever that falls.

Run from the repo root: PYTHONPATH=.pydeps python3 -W ignore smart_speaker/pcb_2layer/check_power.py
"""
import math
import os
import re
import sys

import numpy as np
from scipy import ndimage, sparse
from scipy.sparse.linalg import spsolve

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check_gerbers as cg  # noqa: E402

from gerbonara import ExcellonFile, GerberFile  # noqa: E402
from gerbonara.utils import MM  # noqa: E402

cg.PPM = PPM = 20                # 0.05 mm: nets must be separated at this resolution
RS = 0.49e-3                     # ohm per square, 1 oz copper (35 um)
RHO = 1.7e-5                     # copper, ohm mm
PLATING = 0.02                   # mm of hole wall copper
BOARD_T = 1.6
LOAD_LED, LOAD_AMP, LOAD_ESP = 2.3, 0.8, 0.35    # A, peak budget from WIRING.md
LIMIT_A_PER_MM = 3.0             # about 20 C rise for 1 oz outer copper, IPC-2221 long-trace curve
HERE = cg.HERE
fails = []


def check_holes():
    print("== holes ==")
    text = open(os.path.join(HERE, "interface_board_2l.kicad_pcb")).read()
    tmp = cg.load_zip()
    d = tmp.name
    plated = []
    for obj in ExcellonFile.open(os.path.join(d, f"{cg.PREFIX}PTH.drl")).drills():
        for p in obj.to_primitives(MM):
            plated.append((round(p.x, 3), round(p.y, 3), round(2 * p.r, 3)))
    npth = []
    for obj in ExcellonFile.open(os.path.join(d, f"{cg.PREFIX}NPTH.drl")).drills():
        for p in obj.to_primitives(MM):
            npth.append((round(p.x, 3), round(p.y, 3), round(2 * p.r, 3)))
    tmp.cleanup()

    # ESP32 grid: two rows of 15 at 2.54 pitch, 25.4 apart.
    sock = sorted(h for h in plated if h[2] == 1.0)
    ys = sorted({h[1] for h in sock})
    if len(sock) != 30 or len(ys) != 2 or abs((ys[1] - ys[0]) - 25.4) > 0.005:
        fails.append(f"socket rows wrong: {len(sock)} holes, y {ys}")
    for y in ys:
        xs = sorted(h[0] for h in sock if h[1] == y)
        steps = np.diff(xs)
        if len(xs) != 15 or abs(steps - 2.54).max() > 0.005:
            fails.append(f"socket pitch wrong in row y={y}: {steps}")
    if len({tuple(sorted(h[0] for h in sock if h[1] == y)) for y in ys}) != 1:
        fails.append("socket rows are offset from each other")
    print(f"ESP32 sockets: {len(sock)} holes, rows {ys[1] - ys[0]:.2f} mm apart, 2.54 mm pitch")

    # Hole size against what goes through it (finished sizes).
    need = {1.0: ("socket pin, 0.6 mm square, 0.85 diagonal", 0.85),
            1.2: ("22 AWG stranded, 0.76 mm conductor", 0.76),
            1.5: ("up to 18 AWG, 1.02 mm conductor", 1.02),
            0.9: ("C1 lead, 0.6 mm", 0.6)}
    for size, (what, min_d) in need.items():
        n = sum(1 for h in plated if h[2] == size)
        ok = size >= min_d + 0.1
        print(f"  {size} mm x{n}: {what} -> {'OK' if ok else 'TOO SMALL'}")
        if not ok:
            fails.append(f"{size} mm hole is too small for {what}")

    # Annular ring and hole spacing.
    rings = []
    for size, drill in re.findall(r'\(size ([\d.]+) [\d.]+\)\s*\(drill ([\d.]+)\)', text):
        if float(size) != float(drill):
            rings.append((float(size) - float(drill)) / 2)
    m = re.search(r'\(via\s*\(at [^)]*\)\s*\(size ([\d.]+)\)\s*\(drill ([\d.]+)\)', text)
    via_ring = (float(m.group(1)) - float(m.group(2))) / 2
    print(f"annular ring: pads min {min(rings):.2f} mm, vias {via_ring:.3f} mm")
    if min(rings + [via_ring]) < 0.15:
        fails.append("annular ring below 0.15 mm")
    all_h = plated + npth
    gap = 1e9
    for i, a in enumerate(all_h):
        for b in all_h[i + 1:]:
            gap = min(gap, math.dist(a[:2], b[:2]) - (a[2] + b[2]) / 2)
    print(f"closest two holes, edge to edge: {gap:.2f} mm")
    if gap < 0.25:
        fails.append(f"holes only {gap:.2f} mm apart")
    if sorted(h[2] for h in npth) != [2.7] * 4:
        fails.append("mounting holes are not 4 x 2.7 mm")
    print(f"mounting: {len(npth)} x 2.7 mm unplated")
    return plated


def solve(name, canvas, rasters, plated, ref, loads, pads, factor=1):
    """ref: pad at 0 V. loads: [(pad, amps)]. Prints drops and the worst neck."""
    lab = {n: ndimage.label(rasters[n], structure=np.ones((3, 3)))[0] for n in ("F_Cu", "B_Cu")}
    r, c = canvas.cell(ref[3], ref[4])
    keep = {"F_Cu": {lab["F_Cu"][r, c]}, "B_Cu": set()}
    changed = True
    while changed:
        changed = False
        for x, y, _ in plated:
            r, c = canvas.cell(x, y)
            f, b = lab["F_Cu"][r, c], lab["B_Cu"][r, c]
            if f and b:
                if f in keep["F_Cu"] and b not in keep["B_Cu"]:
                    keep["B_Cu"].add(b)
                    changed = True
                if b in keep["B_Cu"] and f not in keep["F_Cu"]:
                    keep["F_Cu"].add(f)
                    changed = True
    masks = {n: np.isin(lab[n], list(keep[n])) for n in lab}
    # Separate the nets at full resolution first, then coarsen one net at a time.
    ppm = PPM / factor
    if factor > 1:
        for n in masks:
            h, w = (s // factor * factor for s in masks[n].shape)
            masks[n] = masks[n][:h, :w].reshape(h // factor, factor, w // factor, factor).mean(axis=(1, 3)) >= 0.5
    idx = {}
    total = 0
    for n in ("F_Cu", "B_Cu"):
        arr = -np.ones(masks[n].shape, np.int64)
        count = int(masks[n].sum())
        arr[masks[n]] = np.arange(total, total + count)
        idx[n] = arr
        total += count
    g = 1.0 / RS
    rows, cols, vals = [], [], []

    def add(a, b, cond):
        rows.extend([a, b, a, b])
        cols.extend([a, b, b, a])
        vals.extend([cond, cond, -cond, -cond])

    for n in idx:
        arr = idx[n]
        for dy, dx in ((0, 1), (1, 0)):
            a = arr[:arr.shape[0] - dy, :arr.shape[1] - dx]
            b = arr[dy:, dx:]
            ok = (a >= 0) & (b >= 0)
            aa, bb = a[ok], b[ok]
            rows.extend(aa.tolist() + bb.tolist() + aa.tolist() + bb.tolist())
            cols.extend(aa.tolist() + bb.tolist() + bb.tolist() + aa.tolist())
            vals.extend([g] * (2 * len(aa)) + [-g] * (2 * len(aa)))

    def cells_near(x, y, rad):
        r0, c0 = canvas.cell(x, y)
        r0, c0 = r0 // factor, c0 // factor
        k = max(1, int(round(rad * ppm)))
        return [(r0 + j, c0 + i) for j in range(-k, k + 1) for i in range(-k, k + 1)
                if i * i + j * j <= k * k]

    for x, y, d in plated:
        here = [(rc, idx["F_Cu"][rc], idx["B_Cu"][rc]) for rc in cells_near(x, y, d / 2)]
        here = [h for h in here if h[1] >= 0 and h[2] >= 0]
        if here:
            cond = 1.0 / (RHO * BOARD_T / (math.pi * d * PLATING)) / len(here)
            for _, a, b in here:
                add(int(a), int(b), cond)

    A = sparse.coo_matrix((vals, (rows, cols)), shape=(total, total)).tocsr()
    rhs = np.zeros(total)
    for p, amps in loads:
        nodes = [idx["F_Cu"][rc] for rc in cells_near(p[3], p[4], 0.3) if idx["F_Cu"][rc] >= 0]
        for q in nodes:
            rhs[q] += amps / len(nodes)
    fixed = sorted({int(idx["F_Cu"][rc]) for rc in cells_near(ref[3], ref[4], 0.3)
                    if idx["F_Cu"][rc] >= 0})
    free = np.setdiff1d(np.arange(total), fixed)
    # Copper not reachable carries no current; keep the matrix solvable.
    v = np.zeros(total)
    v[free] = spsolve(A[free][:, free].tocsc() + sparse.eye(len(free), format="csc") * 1e-6, rhs[free])

    print(f"\n== {name}: {total} cells ==")
    drops = {}
    for p, amps in loads:
        nodes = [idx["F_Cu"][rc] for rc in cells_near(p[3], p[4], 0.3) if idx["F_Cu"][rc] >= 0]
        drops[p[0]] = float(np.mean(v[nodes]))
        print(f"  {p[0]}.{p[1]} at {amps} A: {drops[p[0]] * 1000:.1f} mV")

    exclude = np.zeros(masks["F_Cu"].shape, bool)
    for x, y, d in plated:
        for rc in cells_near(x, y, d / 2 + 1.0):
            if 0 <= rc[0] < exclude.shape[0] and 0 <= rc[1] < exclude.shape[1]:
                exclude[rc] = True
    for q in pads:
        for rc in cells_near(q[3], q[4], 1.5):
            if 0 <= rc[0] < exclude.shape[0] and 0 <= rc[1] < exclude.shape[1]:
                exclude[rc] = True
    worst = (0, None, None)
    corner = 0.0
    for n in idx:
        V = np.where(idx[n] >= 0, v[np.maximum(idx[n], 0)], np.nan)
        gy, gx = np.gradient(V, 1.0 / ppm)
        J = np.hypot(gx, gy) / RS          # A per mm of width
        J[~masks[n] | exclude | np.isnan(J)] = 0
        # Average over 1 mm of copper: a sharp inner corner is a mathematical
        # singularity that grows with grid resolution, not a real heating figure.
        size = max(3, int(ppm))
        share = ndimage.uniform_filter(masks[n].astype(float), size)
        avg = ndimage.uniform_filter(J, size) / np.maximum(share, 0.1)
        avg[~masks[n] | exclude] = 0
        corner = max(corner, float(J.max()))
        peak = float(avg.max())
        if peak > worst[0]:
            j, i = np.unravel_index(int(avg.argmax()), avg.shape)
            worst = (peak, n, (canvas.x0 + i / ppm, canvas.y1 - j / ppm))
    ex, ey = worst[2]
    print(f"  worst current density away from pads, 1 mm average: {worst[0]:.2f} A/mm on {worst[1]}"
          f" at enclosure x {ex - 60:.1f}, y {ey + 100:.1f} (single-cell peak {corner:.2f})")
    if worst[0] > LIMIT_A_PER_MM:
        fails.append(f"{name}: {worst[0]:.2f} A/mm exceeds {LIMIT_A_PER_MM} A/mm")
    return drops


def main():
    plated = check_holes()
    tmp = cg.load_zip()
    d = tmp.name
    G = {n: GerberFile.open(os.path.join(d, f"{cg.PREFIX}{n}.gbr"))
         for n in ("F_Cu", "B_Cu", "Edge_Cuts")}
    bbox = cg.outline_bbox(G["Edge_Cuts"])
    canvas = cg.Canvas((bbox[0] - 1, bbox[1] - 1, bbox[2] + 1, bbox[3] + 1))
    rasters = {n: cg.raster(G[n], canvas) for n in ("F_Cu", "B_Cu")}
    tmp.cleanup()
    pads = cg.read_pads()

    def pad(ref, num):
        return next(p for p in pads if p[0] == ref and p[1] == str(num))

    five = solve("5 V from Q1", canvas, rasters, plated, pad("Q1", 2),
                 [(pad("J6", 2), LOAD_LED), (pad("J5", 2), LOAD_AMP), (pad("J1", 1), LOAD_ESP)], pads)
    gnd = solve("GND return to the 5 V input", canvas, rasters, plated, pad("J7", 1),
                [(pad("J6", 1), LOAD_LED), (pad("J5", 1), LOAD_AMP), (pad("J1", 2), LOAD_ESP)], pads, factor=2)
    total = max(abs(five["J6"]) + abs(gnd["J6"]), abs(five["J1"]) + abs(gnd["J1"]))
    print(f"\ntotal copper drop to the worst load, 5 V plus GND: {total * 1000:.0f} mV")
    if total > 0.15:
        fails.append(f"copper drop {total * 1000:.0f} mV exceeds 150 mV")

    if fails:
        print("\nFAILED")
        for f in fails:
            print(" -", f)
        sys.exit(1)
    print("\nALL POWER AND HOLE CHECKS OK")


if __name__ == "__main__":
    main()
