#!/usr/bin/env python3
"""Test the Gerbers a fab would actually receive, using a parser other than KiCad.

Reads the exported zip with gerbonara, rasterises each layer, rebuilds the
electrical connections from the copper images and plated holes alone, then
compares them with the nets in the board file.  Also checks layer alignment, the
outline, holes and solder mask openings, and proves the check can fail by damaging
the copper on purpose.

Run from the repo root:  PYTHONPATH=.pydeps python3 smart_speaker/pcb/check_gerbers.py
"""
import math
import os
import re
import sys
import tempfile
import zipfile
from collections import defaultdict

import numpy as np
from gerbonara import ExcellonFile, GerberFile
from gerbonara.graphic_primitives import Arc, ArcPoly, Circle, Line, Rectangle
from gerbonara.utils import MM
from PIL import Image, ImageDraw
from scipy import ndimage

HERE = os.path.dirname(os.path.abspath(__file__))
PPM = 20                       # pixels per mm: 0.05 mm, a quarter of the 0.2 mm gap
PREFIX = "interface_board-"
COPPER = ["F_Cu", "In1_Cu", "In2_Cu", "B_Cu"]


def load_zip():
    tmp = tempfile.TemporaryDirectory(dir=HERE, prefix=".gerber_check_")
    with zipfile.ZipFile(os.path.join(HERE, "interface_board-gerbers.zip")) as z:
        z.extractall(tmp.name)
    return tmp


class Canvas:
    def __init__(s, bbox):
        s.x0, s.y0, s.x1, s.y1 = bbox
        s.w = int((s.x1 - s.x0) * PPM) + 1
        s.h = int((s.y1 - s.y0) * PPM) + 1

    def px(s, x, y):
        return (x - s.x0) * PPM, (s.y1 - y) * PPM

    def cell(s, x, y):
        a, b = s.px(x, y)
        return int(round(b)), int(round(a))


def arc_points(x1, y1, x2, y2, cx, cy, clockwise):
    """Flatten an arc into points, finely enough for the 0.05 mm raster."""
    r = math.hypot(x1 - cx, y1 - cy)
    a0, a1 = math.atan2(y1 - cy, x1 - cx), math.atan2(y2 - cy, x2 - cx)
    if clockwise:
        while a1 >= a0:
            a1 -= 2 * math.pi
    else:
        while a1 <= a0:
            a1 += 2 * math.pi
    n = max(4, int(abs(a1 - a0) * max(r, 0.5) * PPM))
    return [(cx + r * math.cos(a0 + (a1 - a0) * i / n), cy + r * math.sin(a0 + (a1 - a0) * i / n))
            for i in range(n + 1)]


def draw_prim(d, c, p):
    fill = 255 if getattr(p, "polarity_dark", True) else 0
    if isinstance(p, Circle):
        x, y = c.px(p.x, p.y)
        r = p.r * PPM
        d.ellipse((x - r, y - r, x + r, y + r), fill=fill)
    elif isinstance(p, Line):
        a, b = c.px(p.x1, p.y1), c.px(p.x2, p.y2)
        w = p.width * PPM
        d.line((a, b), fill=fill, width=max(1, int(round(w))))
        for q in (a, b):
            d.ellipse((q[0] - w / 2, q[1] - w / 2, q[0] + w / 2, q[1] + w / 2), fill=fill)
    elif isinstance(p, Rectangle):
        ca, sa = math.cos(p.rotation or 0), math.sin(p.rotation or 0)
        pts = []
        for dx, dy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            lx, ly = dx * p.w / 2, dy * p.h / 2
            pts.append(c.px(p.x + lx * ca - ly * sa, p.y + lx * sa + ly * ca))
        d.polygon(pts, fill=fill)
    elif isinstance(p, Arc):
        pts = [c.px(x, y) for x, y in arc_points(p.x1, p.y1, p.x2, p.y2, p.cx, p.cy, p.clockwise)]
        w = p.width * PPM
        d.line(pts, fill=fill, width=max(1, int(round(w))), joint="curve")
        for q in (pts[0], pts[-1]):
            d.ellipse((q[0] - w / 2, q[1] - w / 2, q[0] + w / 2, q[1] + w / 2), fill=fill)
    elif isinstance(p, ArcPoly):
        pts = []
        for a, b, (clockwise, (cx, cy)) in p.segments:
            if clockwise is None:
                pts.append(c.px(*a))
            else:
                pts += [c.px(x, y) for x, y in arc_points(*a, *b, cx, cy, clockwise)[:-1]]
        d.polygon(pts, fill=fill)
    else:
        raise TypeError(f"unhandled primitive {type(p)}")


def raster(gerber, canvas):
    im = Image.new("L", (canvas.w, canvas.h), 0)
    d = ImageDraw.Draw(im)
    for obj in gerber.objects:
        for prim in obj.to_primitives(MM):
            draw_prim(d, canvas, prim)
    return np.asarray(im) > 127


def outline_bbox(gerber):
    xs, ys = [], []
    for obj in gerber.objects:
        for p in obj.to_primitives(MM):
            if isinstance(p, Line):
                xs += [p.x1, p.x2]
                ys += [p.y1, p.y2]
    return min(xs), min(ys), max(xs), max(ys)


def read_pads():
    """Pads from the board file: (ref, number, net, x, y) in Gerber coordinates."""
    text = open(os.path.join(HERE, "interface_board.kicad_pcb")).read()
    pads = []
    for block in re.split(r"\n\s*\(footprint ", text)[1:]:
        ref = re.search(r'"Reference" "([^"]+)"', block).group(1)
        fx, fy = map(float, re.search(r"\(at ([-\d.]+) ([-\d.]+)", block).groups())
        for num, body in re.findall(r'\(pad "([^"]*)" (.*?)\n\s*\)', block, re.S):
            at = re.search(r"\(at ([-\d.]+) ([-\d.]+)", body)
            net = re.search(r'\(net \d+ "([^"]*)"\)', body)
            pads.append((ref, num, net.group(1) if net else "", fx + float(at.group(1)),
                         -(fy + float(at.group(2))), "np_thru_hole" in body))
    return pads


class UF:
    def __init__(s):
        s.p = {}

    def find(s, a):
        s.p.setdefault(a, a)
        while s.p[a] != a:
            s.p[a] = s.p[s.p[a]]
            a = s.p[a]
        return a

    def union(s, a, b):
        s.p[s.find(a)] = s.find(b)


def connectivity(rasters, canvas, holes, pads):
    """Group pads purely from copper shapes and plated holes; report mismatches."""
    labels = {n: ndimage.label(rasters[n], structure=np.ones((3, 3)))[0] for n in COPPER}
    uf = UF()
    for x, y in holes:
        row, col = canvas.cell(x, y)
        here = [(n, labels[n][row, col]) for n in COPPER if labels[n][row, col]]
        for a, b in zip(here, here[1:]):
            uf.union(a, b)
    errors, by_group, group_nets = [], defaultdict(set), defaultdict(set)
    for ref, num, net, x, y, npth in pads:
        if npth:
            continue
        row, col = canvas.cell(x, y)
        lab = labels["F_Cu"][row, col]
        if not lab:
            errors.append(f"{ref}.{num}: no copper at the pad position")
            continue
        g = uf.find(("F_Cu", lab))
        if net:
            by_group[net].add(g)
            group_nets[g].add(net)
        else:
            group_nets[g].add(f"NC:{ref}.{num}")
    for net, groups in by_group.items():
        if len(groups) > 1:
            errors.append(f"OPEN: net {net} splits into {len(groups)} separate pieces")
    for g, nets in group_nets.items():
        if len(nets) > 1:
            errors.append(f"SHORT: {sorted(nets)} are connected")
    return errors, len(by_group)


def main():
    tmp = load_zip()
    d = tmp.name
    fails = []
    G = {}
    for n in COPPER + ["Edge_Cuts", "F_Mask", "B_Mask", "F_Silkscreen", "F_Paste"]:
        G[n] = GerberFile.open(os.path.join(d, f"{PREFIX}{n}.gbr"))
    bbox = outline_bbox(G["Edge_Cuts"])
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    print(f"outline from Gerber: {w:.2f} x {h:.2f} mm")
    if abs(w - 54.5) > 0.01 or abs(h - 62.0) > 0.01:
        fails.append(f"outline {w} x {h} is not 54.5 x 62")
    canvas = Canvas((bbox[0] - 1, bbox[1] - 1, bbox[2] + 1, bbox[3] + 1))
    rasters = {n: raster(G[n], canvas) for n in G}

    # Plated holes come from the drill file, not the board file.
    holes = []
    for obj in ExcellonFile.open(os.path.join(d, f"{PREFIX}PTH.drl")).drills():
        for p in obj.to_primitives(MM):
            holes.append((p.x, p.y))
    npth = []
    for obj in ExcellonFile.open(os.path.join(d, f"{PREFIX}NPTH.drl")).drills():
        for p in obj.to_primitives(MM):
            npth.append((p.x, p.y))
    print(f"drill file: {len(holes)} plated, {len(npth)} unplated")

    pads = read_pads()
    errors, n_nets = connectivity(rasters, canvas, holes, pads)
    fails += errors
    print(f"connectivity rebuilt from copper: {n_nets} nets, {len(errors)} problems")

    # Copper stays inside the outline, on every layer (layers are aligned).
    for n in COPPER:
        ys, xs = np.nonzero(rasters[n])
        gx = xs / PPM + canvas.x0
        gy = canvas.y1 - ys / PPM
        if gx.min() < bbox[0] or gx.max() > bbox[2] or gy.min() < bbox[1] or gy.max() > bbox[3]:
            fails.append(f"{n}: copper outside the board outline")
    # Every plated hole lands on F and B copper; every pad has its mask opening.
    for x, y in holes:
        row, col = canvas.cell(x, y)
        if not (rasters["F_Cu"][row, col] and rasters["B_Cu"][row, col]):
            fails.append(f"plated hole at {x:.2f},{y:.2f} misses outer copper")
    smd = tht = 0
    for ref, num, net, x, y, is_np in pads:
        if is_np:
            continue
        row, col = canvas.cell(x, y)
        if not rasters["F_Mask"][row, col]:
            fails.append(f"{ref}.{num}: covered by solder mask")
        if rasters["F_Silkscreen"][row, col]:
            fails.append(f"{ref}.{num}: silkscreen printed on the pad")
        if any(abs(hx - x) < 0.01 and abs(hy - y) < 0.01 for hx, hy in holes):
            tht += 1
            if not rasters["B_Mask"][row, col]:
                fails.append(f"{ref}.{num}: back solder mask covers the pad")
        else:
            smd += 1
            if not rasters["F_Paste"][row, col]:
                fails.append(f"{ref}.{num}: no paste opening")
    print(f"pads checked: {tht} through-hole, {smd} surface-mount")
    if (tht, smd) != (54, 29):
        fails.append(f"expected 54 through-hole and 29 surface-mount pads, got {tht}, {smd}")

    # Prove the check can fail.
    def pad(ref, num):
        return next(p for p in pads if p[0] == ref and p[1] == num)

    broken = {k: v.copy() for k, v in rasters.items()}
    a, b = pad("C2", "1"), pad("C2", "2")
    (r0, c0), (r1, c1) = canvas.cell(a[3], a[4]), canvas.cell(b[3], b[4])
    broken["F_Cu"][min(r0, r1) - 2:max(r0, r1) + 3, min(c0, c1):max(c0, c1)] = True
    short, _ = connectivity(broken, canvas, holes, pads)
    broken = {k: v.copy() for k, v in rasters.items()}
    q = pad("R1", "2")
    r0, c0 = canvas.cell(q[3], q[4])
    broken["F_Cu"][r0 - 40:r0 + 40, c0 - 40:c0 + 40] = False
    cut, _ = connectivity(broken, canvas, holes, pads)
    print(f"self-test: forced short -> {sum('SHORT' in e for e in short)} found; "
          f"forced cut -> {len(cut)} found")
    if not any("SHORT" in e for e in short) or not cut:
        fails.append("self-test failed: damaged copper was not detected")

    # Picture of what the fab will see, built from the Gerbers.
    img = np.zeros((canvas.h, canvas.w, 3), np.uint8) + 30
    img[rasters["B_Cu"]] = (40, 80, 170)
    img[rasters["F_Cu"]] = (180, 60, 50)
    img[rasters["F_Silkscreen"]] = (240, 240, 240)
    img[raster(G["Edge_Cuts"], canvas)] = (240, 210, 40)
    out = os.path.join(HERE, "render", "gerber_readback.png")
    Image.fromarray(img).save(out)
    tmp.cleanup()

    if fails:
        print("FAILED")
        for f in fails:
            print(" -", f)
        sys.exit(1)
    print("ALL GERBER CHECKS OK")


if __name__ == "__main__":
    main()
