#!/usr/bin/env python3
"""Generate the speaker's 2-layer interface board as a KiCad 9 .kicad_pcb.

One source of truth: the parts and nets below, the placement in enclosure
coordinates (same X/Y as ../round_sub/round_sub.py, seen from above), and a
small grid router.  GND is copper fill on both layers, tied by stitching vias.
5 V is a hand-placed trunk on both layers through the gap beside the sockets,
with routed branches.

Run: python3 make_pcb.py      then see export.sh for zone fill, DRC and Gerbers.
Needs numpy and scipy.
"""
import csv
import heapq
import json
import math
import os
import re
import uuid

import numpy as np
from scipy import ndimage

HERE = os.path.dirname(os.path.abspath(__file__))
NAME = "interface_board_2l"
TRUNK = 1.0          # 5 V through the socket gap, on both layers
BRANCH = 0.5         # 5 V branches
WIDE = 1.2           # 5 V to the LED port and C1

# ---- enclosure geometry this board has to agree with -------------------------
# From round_sub.py: inner bay radius 90.34, ESP32 USB end at x = rb_in - 3.
ESP_USB_END_X = 87.339
ESP_L = 51.0
# Devkit B0F1MS5S8R, measured off the listing's top-down pinout photo using the
# 2.54 mm pin pitch as the scale: rows 25.4 apart; pin 1 is 9.6 mm from the
# USB-end board edge.  CHECK WITH CALIPERS BEFORE ORDERING.
ROW_Y = 12.7
PITCH = 2.54
PIN1_X = ESP_USB_END_X - 9.6

# Board outline, enclosure coordinates.  The centre notch clears the ESP32
# ledges and end stop (x <= 38.84, |y| <= 9); x >= 29 clears the wire clips.
EDGE_L, EDGE_N, EDGE_R, EDGE_Y, NOTCH_Y = 29.0, 39.6, 83.5, 31.0, 10.5
MOUNTS = [(32.0, 13.5), (32.0, -13.5), (81.0, 27.0), (81.0, -27.0)]
MOUNT_D = 2.7        # M2.5 clearance
ROW = 22.5           # |y| of the cable solder rows
SLOT_Y = 27.0        # |y| of the strain relief slots
SLOT_H = 2.2

# ---- design rules ------------------------------------------------------------
TRACK = 0.25
CLEAR = 0.2
VIA_D, VIA_DRILL = 0.7, 0.3
GRID = 0.2
SAFETY = 0.03        # added to router clearances for grid rounding
EDGE_CLEAR = 0.5

# ---- nets --------------------------------------------------------------------
NETS = ["", "GND", "+5V", "VIN_RAW", "+3V3", "MIC_SCK", "MIC_WS", "MIC_SD", "SCK_ESP", "WS_ESP",
        "SPK_LRC", "SPK_BCLK", "SPK_DIN", "LED_RAW", "LED_BUF", "LED_SEL", "LED_OUT"]
NET_ID = {n: i for i, n in enumerate(NETS)}

# Devkit pin order from the USB end, per the listing's pinout image.
# Row A is y = -12.7 (VIN side), row B is y = +12.7 (3V3 side), USB toward +X.
ROW_A = ["VIN", "GND", "13", "12", "14", "27", "26", "25", "33", "32", "35", "34",
         "39", "36", "EN"]
ROW_B = ["3V3", "GND", "15", "2", "4", "16", "17", "5", "18", "19", "21", "3", "1",
         "22", "23"]
ESP_NET = {"VIN": "+5V", "GND": "GND", "3V3": "+3V3", "32": "SCK_ESP", "33": "WS_ESP",
           "35": "MIC_SD", "25": "SPK_LRC", "26": "SPK_BCLK", "22": "SPK_DIN",
           "27": "LED_RAW"}

MIC_PINS = [("GND", "GND"), ("3V3", "+3V3"), ("SCK", "MIC_SCK"), ("WS", "MIC_WS"),
            ("SD", "MIC_SD")]
AMP_PINS = [("GND", "GND"), ("5V", "+5V"), ("LRC", "SPK_LRC"), ("BCK", "SPK_BCLK"),
            ("DIN", "SPK_DIN")]
LED_PINS = [("GND", "GND"), ("5V", "+5V"), ("DIN", "LED_OUT"), ("NC", ""), ("NC", "")]


def K(x, y):
    """Enclosure mm -> KiCad page mm (y flips; KiCad's y runs downward)."""
    return (round(x + 60.0, 4), round(100.0 - y, 4))


class Pad:
    def __init__(s, ref, num, net, x, y, shape, w, h=None, drill=None):
        s.ref, s.num, s.net = ref, str(num), net
        s.x, s.y = x, y             # KiCad coordinates
        s.shape, s.w, s.h, s.drill = shape, w, h if h is not None else w, drill

    @property
    def tht(s):
        return s.drill is not None


class Part:
    def __init__(s, ref, value, x, y, pads, lib="speaker", rot=0, fitted=True):
        s.ref, s.value, s.x, s.y, s.pads, s.lib = ref, value, x, y, pads, lib
        s.rot = rot          # footprint angle (deg, KiCad CCW); pads stay in board coords
        s.fitted = fitted    # False: copper only (solder jumper), keep out of BOM/placement
        s.silk = []


parts, texts, silk_lines, silk_rects = [], [], [], []
tracks, vias = [], []        # (x0,y0,x1,y1,w,layer,net) / (x,y,net)


def tht_row(ref, value, pins, x0, y, pitch, drill, pad, first_square=True):
    """Row of plated holes along X, in enclosure coordinates."""
    pads = []
    for i, (label, net) in enumerate(pins):
        kx, ky = K(x0 + i * pitch, y)
        shape = "rect" if (i == 0 and first_square) else "circle"
        pads.append(Pad(ref, i + 1, net, kx, ky, shape, pad, pad, drill))
    cx, cy = K(x0, y)
    p = Part(ref, value, cx, cy, pads)
    parts.append(p)
    return p


def smd2(ref, value, x, y, net1, net2, vertical=False):
    """0805 two-terminal part, hand-solderable land pattern.
    Vertical parts use the standard horizontal footprint turned to 270 deg
    (pad 1 on top), so the placement file rotation matches the pads."""
    kx, ky = K(x, y)
    d = 0.95
    if vertical:
        pads = [Pad(ref, 1, net1, kx, ky - d, "rect", 1.4, 1.0),
                Pad(ref, 2, net2, kx, ky + d, "rect", 1.4, 1.0)]
    else:
        pads = [Pad(ref, 1, net1, kx - d, ky, "rect", 1.0, 1.4),
                Pad(ref, 2, net2, kx + d, ky, "rect", 1.0, 1.4)]
    p = Part(ref, value, kx, ky, pads, rot=270 if vertical else 0)
    parts.append(p)
    return p


def sot23(ref, value, x, y, nets):
    kx, ky = K(x, y)
    a, b = 1.1375, 0.95
    pos = [(-a, -b), (-a, b), (a, 0)]
    pads = [Pad(ref, i + 1, n, kx + dx, ky + dy, "rect", 1.325, 0.6)
            for i, ((dx, dy), n) in enumerate(zip(pos, nets))]
    p = Part(ref, value, kx, ky, pads)
    parts.append(p)
    return p


def sot235(ref, value, x, y, nets):
    kx, ky = K(x, y)
    a, b = 1.1375, 0.95
    pos = [(-a, -b), (-a, 0), (-a, b), (a, b), (a, -b)]
    pads = [Pad(ref, i + 1, n, kx + dx, ky + dy, "rect", 1.325, 0.6)
            for i, ((dx, dy), n) in enumerate(zip(pos, nets))]
    p = Part(ref, value, kx, ky, pads)
    parts.append(p)
    return p


def solder_jumper(ref, value, x, y, nets):
    kx, ky = K(x, y)
    pads = [Pad(ref, i + 1, n, kx + (i - 1) * 1.25, ky, "rect", 0.9, 1.4)
            for i, n in enumerate(nets)]
    p = Part(ref, value, kx, ky, pads, fitted=False)
    parts.append(p)
    return p


def pad_of(ref, num):
    for p in parts:
        if p.ref == ref:
            for q in p.pads:
                if q.num == str(num):
                    return q
    raise KeyError((ref, num))


def stub_via(ref, num, dx, dy, net=None, width=0.4):
    """Short F.Cu stub from an SMD pad to a plane via (dx, dy in KiCad mm)."""
    q = pad_of(ref, num)
    n = net or q.net
    x, y = round(q.x + dx, 4), round(q.y + dy, 4)
    tracks.append((q.x, q.y, x, y, width, "F.Cu", n))
    vias.append((x, y, n))


# ---- placement ---------------------------------------------------------------
def esp_col_x(i):
    return PIN1_X - i * PITCH


def build_parts():
    tht_row("J1", "Socket 1x15 2.54mm, ESP32 VIN row",
            [(n, ESP_NET.get(n, "")) for n in ROW_A], PIN1_X, -ROW_Y, -PITCH, 1.0, 1.6)
    tht_row("J2", "Socket 1x15 2.54mm, ESP32 3V3 row",
            [(n, ESP_NET.get(n, "")) for n in ROW_B], PIN1_X, ROW_Y, -PITCH, 1.0, 1.6)
    # Cable rows: 22 AWG pigtails soldered in by hand; 1.2 mm plated holes.
    # Wire pads only, so they stay out of the fab BOM and placement file.
    for ref, value, pins, x, y in (("J3", "MIC L: 5-pin JST SM pigtail", MIC_PINS, 65.0, ROW),
                                   ("J4", "MIC R: 5-pin JST SM pigtail", MIC_PINS, 65.0, -ROW),
                                   ("J5", "AMP: 5-pin JST SM pigtail", AMP_PINS, 44.0, ROW),
                                   ("J6", "LED: 5-pin JST SM pigtail", LED_PINS, 33.0, -ROW)):
        tht_row(ref, value, pins, x, y, PITCH, 1.2, 2.1).fitted = False
    # 5 V input: the wires from the screw-terminal barrel connector.
    tht_row("J7", "5V IN: 2 wires, up to 18 AWG", [("GND", "GND"), ("+5V", "VIN_RAW")],
            33.5, ROW, 5.0, 1.5, 3.0).fitted = False

    # Reverse polarity protection: drain to input, source to load, gate to GND.
    sot23("Q1", "AO3401A", 37.0, 17.0, ["GND", "+5V", "VIN_RAW"])
    # Bulk capacitor at the LED supply: 10 mm can, 5 mm lead spacing.
    c1 = tht_row("C1", "1000uF 10V, 10x12.5mm", [("+", "+5V"), ("-", "GND")], 48.5, -21.0,
                 5.0, 0.9, 1.8)
    c1.silk.append(("circle", K(51.0, -21.0), 5.25))
    # Amp port decoupling.
    smd2("C2", "10uF 10V 0805", 47.0, 18.0, "+5V", "GND")
    smd2("C3", "100nF 0805", 53.5, 18.0, "+5V", "GND")
    # Mic port decoupling.
    smd2("C4", "100nF 0805", 70.0, 18.0, "+3V3", "GND")
    smd2("C5", "100nF 0805", 70.0, -18.0, "+3V3", "GND")
    # LED data: level shifter, bypass jumper, series resistor.
    sot235("U1", "74AHCT1G125", 62.0, -5.0, ["GND", "LED_RAW", "GND", "LED_BUF", "+5V"])
    smd2("C6", "100nF 0805", 68.0, -5.0, "+5V", "GND")
    solder_jumper("JP1", "LED data: 1-2 bypass, 2-3 shifter", 53.0, -5.0,
                  ["LED_RAW", "LED_SEL", "LED_BUF"])
    smd2("R1", "330R 0805", 47.0, -5.0, "LED_OUT", "LED_SEL")
    # Mic SD pull-down, close to the ESP32 input.
    smd2("R2", "100k 0805", 50.5, -9.2, "MIC_SD", "GND")
    # Damp the mic clocks at the ESP32; simulation showed interference without them.
    smd2("R3", "100R 0805", 57.38, -9.6, "WS_ESP", "MIC_WS", vertical=True)
    smd2("R4", "100R 0805", 54.84, -9.6, "SCK_ESP", "MIC_SCK", vertical=True)

    # Plane stubs.
    q1s = pad_of("Q1", 2)
    for dx, dy in ((-1.25, -0.35), (-1.25, 0.75), (0.1, 1.2)):
        stub_via("Q1", 2, dx, dy, width=0.8)
    stub_via("Q1", 1, -1.25, 0.0)
    q1d = pad_of("Q1", 3)
    j7 = pad_of("J7", 2)
    tracks.append((q1d.x, q1d.y, j7.x, j7.y, 2.5, "F.Cu", "VIN_RAW"))   # also Q1's heat path
    stub_via("C2", 1, -1.2, 0.0)
    stub_via("C2", 2, 1.2, 0.0)
    stub_via("C3", 1, -1.2, 0.0)
    stub_via("C3", 2, 1.2, 0.0)
    stub_via("C4", 2, 1.2, 0.0)
    stub_via("C5", 2, 1.2, 0.0)
    stub_via("U1", 5, 1.2, -0.5)
    stub_via("U1", 1, -1.2, -0.5)
    stub_via("U1", 3, -1.2, 0.5)
    stub_via("C6", 1, -0.0, 1.2)
    stub_via("C6", 2, 1.2, 0.0)
    stub_via("R2", 2, 1.2, 0.0)
    add_trunk()


FIVE = []          # 5 V stub vias the router still has to reach


def add_trunk():
    """The 5 V trunk, hand-placed: only the gap at x = 40.6 is wide enough."""
    FIVE.extend(v for v in vias if v[2] == "+5V")
    del FIVE[:3]       # the first three are Q1's, joined below

    def run(layer, pts, w):
        for a, b in zip(pts, pts[1:]):
            tracks.append((*K(*a), *K(*b), w, layer, "+5V"))

    s1, s2, s3 = [v for v in vias if v[2] == "+5V"][:3]
    enc = lambda v: (round(v[0] - 60.0, 4), round(100.0 - v[1], 4))
    gap = [(39.6, 14.0), (40.6, 13.0), (40.6, -15.0)]
    run("F.Cu", [enc(s3), (36.3, 14.0)] + gap, TRUNK)
    run("B.Cu", [enc(s1), enc(s2), enc(s3), (36.3, 14.0)] + gap, TRUNK)
    for layer in ("F.Cu", "B.Cu"):
        run(layer, [(39.4, -15.0), (41.8, -15.0)], TRUNK)
    for x in (39.4, 40.6, 41.8):
        vias.append((*K(x, -15.0), "+5V"))
    j6, c1 = pad_of("J6", 2), pad_of("C1", 1)
    run("B.Cu", [(39.4, -15.0), (j6.x - 60.0, -18.0), (j6.x - 60.0, 100.0 - j6.y)], WIDE)
    run("B.Cu", [(41.8, -15.0), (45.0, -18.0), (c1.x - 60.0, 100.0 - c1.y)], WIDE)


# ---- router ------------------------------------------------------------------
class Router:
    LAYERS = ("F.Cu", "B.Cu")

    def __init__(s):
        x0, y0 = K(EDGE_L, EDGE_Y)
        x1, y1 = K(EDGE_R, -EDGE_Y)
        s.x0, s.y0 = x0, y0
        s.nx = int(round((x1 - x0) / GRID)) + 1
        s.ny = int(round((y1 - y0) / GRID)) + 1
        s.xs = x0 + np.arange(s.nx) * GRID
        s.ys = y0 + np.arange(s.ny) * GRID
        s.track_all = [np.zeros((s.ny, s.nx), np.int32) for _ in s.LAYERS]
        s.via_all = [np.zeros((s.ny, s.nx), np.int32) for _ in s.LAYERS]
        s.own_t, s.own_v = {}, {}
        s.mt = TRACK / 2 + CLEAR + SAFETY
        s.mv = VIA_D / 2 + CLEAR + SAFETY

    def _own(s, table, net):
        if net not in table:
            table[net] = [np.zeros((s.ny, s.nx), np.int32) for _ in s.LAYERS]
        return table[net]

    def _mark(s, dist, layers, net, extra_t=None, extra_v=None):
        t = dist <= (s.mt if extra_t is None else extra_t)
        v = dist <= (s.mv if extra_v is None else extra_v)
        for l in layers:
            s.track_all[l][t] += 1
            s.via_all[l][v] += 1
            if net is not None:
                s._own(s.own_t, net)[l][t] += 1
                s._own(s.own_v, net)[l][v] += 1

    def _grid(s):
        return np.meshgrid(s.xs, s.ys)

    def add_rect(s, cx, cy, w, h, layers, net, keep=None):
        X, Y = s._grid()
        dx = np.maximum(np.abs(X - cx) - w / 2, 0)
        dy = np.maximum(np.abs(Y - cy) - h / 2, 0)
        d = np.hypot(dx, dy)
        if keep is not None:
            s._mark(d, layers, net, keep + TRACK / 2 + SAFETY, keep + VIA_D / 2 + SAFETY)
        else:
            s._mark(d, layers, net)

    def add_seg(s, x0, y0, x1, y1, w, layers, net):
        X, Y = s._grid()
        vx, vy = x1 - x0, y1 - y0
        L2 = vx * vx + vy * vy
        if L2 == 0:
            d = np.hypot(X - x0, Y - y0)
        else:
            t = np.clip(((X - x0) * vx + (Y - y0) * vy) / L2, 0, 1)
            d = np.hypot(X - (x0 + t * vx), Y - (y0 + t * vy))
        s._mark(np.maximum(d - w / 2, 0), layers, net)

    def add_pad(s, q):
        layers = (0, 1) if q.tht else (0,)
        net = NET_ID[q.net] if q.net else 0
        s.add_rect(q.x, q.y, q.w, q.h, layers, net)

    def blocked(s, l, net):
        own = s._own(s.own_t, net)[l]
        return (s.track_all[l] - own) > 0

    def via_blocked(s, net):
        v = s._own(s.own_v, net)
        return ((s.via_all[0] - v[0]) > 0) | ((s.via_all[1] - v[1]) > 0)

    def snap_cells(s, q):
        """Grid cells inside pad q, nearest to its centre first."""
        ix = np.where(np.abs(s.xs - q.x) <= max(q.w / 2, GRID))[0]
        iy = np.where(np.abs(s.ys - q.y) <= max(q.h / 2, GRID))[0]
        cells = [(i, j) for j in iy for i in ix]
        cells.sort(key=lambda c: math.hypot(s.xs[c[0]] - q.x, s.ys[c[1]] - q.y))
        return cells

    def _blocks(s, nid):
        b = [s.blocked(0, nid), s.blocked(1, nid)]
        if s.w > TRACK:
            r = int(math.ceil((s.w - TRACK) / 2 / GRID))
            yy, xx = np.ogrid[-r:r + 1, -r:r + 1]
            disk = xx * xx + yy * yy <= r * r
            b = [ndimage.binary_dilation(x, structure=disk) for x in b]
        return b

    def route(s, net, pads, width=TRACK):
        """Connect all pads of one net, growing a tree from the first pad.
        Search state includes direction, so bends cost extra and traces stay
        straight, 45-degree runs."""
        nid = NET_ID[net]
        s.w = width
        block = s._blocks(nid)
        vblock = s.via_blocked(nid)
        tree = {}   # (l, i, j) -> pad the cell belongs to, or None for track
        layers0 = (0, 1) if pads[0].tht else (0,)
        for c in s.snap_cells(pads[0])[:6]:
            for l in layers0:
                if not block[l][c[1], c[0]]:
                    tree[(l, c[0], c[1])] = pads[0]
        if not tree:
            raise RuntimeError(f"{net}: no free cell at {pads[0].ref}.{pads[0].num}")
        remaining = list(pads[1:])
        moves = [(1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0),
                 (1, 1, 1.414), (1, -1, 1.414), (-1, 1, 1.414), (-1, -1, 1.414)]
        while remaining:
            def d(q):
                return min(abs(s.xs[i] - q.x) + abs(s.ys[j] - q.y) for (_, i, j) in tree)
            remaining.sort(key=d)
            q = remaining.pop(0)
            lq = (1,) if q.ref == "V" else (0, 1) if q.tht else (0,)   # stub vias: reach them on B
            goals = set()
            for c in s.snap_cells(q)[:6]:
                for l in lq:
                    if not block[l][c[1], c[0]]:
                        goals.add((l, c[0], c[1]))
            if not goals:
                raise RuntimeError(f"{net}: pad {q.ref}.{q.num} has no free cell")
            gx = (q.x - s.x0) / GRID
            gy = (q.y - s.y0) / GRID
            h = lambda i, j: math.hypot(i - gx, j - gy)
            dist, prev, heap = {}, {}, []
            for n in tree:
                st = (*n, -1)
                dist[st] = 0.0
                heapq.heappush(heap, (h(n[1], n[2]), st))
            end = None
            while heap:
                f, n = heapq.heappop(heap)
                l, i, j, dr = n
                if (l, i, j) in goals:
                    end = n
                    break
                gn = dist[n]
                if f > gn + h(i, j) + 1e-9:
                    continue
                for k, (di, dj, c) in enumerate(moves):
                    a, b = i + di, j + dj
                    if not (0 <= a < s.nx and 0 <= b < s.ny) or block[l][b, a]:
                        continue
                    if di and dj and (block[l][j, a] or block[l][b, i]):
                        continue
                    m = (l, a, b, k)
                    ng = gn + c + (0.0 if dr in (-1, k) else 3.0)
                    if ng < dist.get(m, 1e18):
                        dist[m], prev[m] = ng, n
                        heapq.heappush(heap, (ng + h(a, b), m))
                if not vblock[j, i] and not block[1 - l][j, i]:
                    m = (1 - l, i, j, -1)
                    ng = gn + 25.0
                    if ng < dist.get(m, 1e18):
                        dist[m], prev[m] = ng, n
                        heapq.heappush(heap, (ng + h(i, j), m))
            if end is None:
                raise RuntimeError(f"{net}: no route to {q.ref}.{q.num}")
            path = [end]
            while path[-1] in prev:
                path.append(prev[path[-1]])
            path.reverse()
            cells = [n[:3] for n in path]
            s._commit(net, nid, cells, q, tree.get(cells[0]))
            for n in cells:
                tree.setdefault(n, None)
            block = s._blocks(nid)
            vblock = s.via_blocked(nid)

    def _commit(s, net, nid, cells, end_pad, start_pad):
        """Turn a cell path into tracks and vias, joining the pad centres."""
        pts = [(c[0], round(float(s.xs[c[1]]), 4), round(float(s.ys[c[2]]), 4)) for c in cells]
        if start_pad is not None:
            pts.insert(0, (pts[0][0], start_pad.x, start_pad.y))
        pts.append((pts[-1][0], end_pad.x, end_pad.y))
        run = [pts[0]]
        for p in pts[1:]:
            if p[0] != run[-1][0]:
                s._emit(net, nid, run)
                vias.append((p[1], p[2], net))
                s.add_seg(p[1], p[2], p[1], p[2], VIA_D, (0, 1), nid)
                run = [p]
            elif (p[1], p[2]) != (run[-1][1], run[-1][2]):
                if len(run) >= 2 and abs((run[-1][1] - run[-2][1]) * (p[2] - run[-2][2])
                                         - (run[-1][2] - run[-2][2]) * (p[1] - run[-2][1])) < 1e-6:
                    run[-1] = p
                else:
                    run.append(p)
        s._emit(net, nid, run)

    def _emit(s, net, nid, run):
        for a, b in zip(run, run[1:]):
            tracks.append((a[1], a[2], b[1], b[2], s.w, s.LAYERS[a[0]], net))
            s.add_seg(a[1], a[2], b[1], b[2], s.w, (a[0],), nid)

    def finish(s):
        pass

def route_all():
    r = Router()
    # Board edge, mounting holes and slots block everything on both layers.
    X, Y = np.meshgrid(r.xs, r.ys)
    poly = outline()
    inside = _inside(X, Y, poly)
    r.track_all[0][~inside] += 1
    r.track_all[1][~inside] += 1
    r.via_all[0][~inside] += 1
    r.via_all[1][~inside] += 1
    for (ax, ay), (bx, by) in zip(poly, poly[1:] + poly[:1]):
        r.add_seg(ax, ay, bx, by, 0, (0, 1), None) if False else None
        vx, vy = bx - ax, by - ay
        t = np.clip(((X - ax) * vx + (Y - ay) * vy) / (vx * vx + vy * vy), 0, 1)
        d = np.hypot(X - (ax + t * vx), Y - (ay + t * vy))
        r._mark(d, (0, 1), None, EDGE_CLEAR + TRACK / 2 + SAFETY, EDGE_CLEAR + VIA_D / 2 + SAFETY)
    for (x, y) in MOUNTS:
        kx, ky = K(x, y)
        d = np.maximum(np.hypot(X - kx, Y - ky) - MOUNT_D / 2, 0)
        r._mark(d, (0, 1), None, 0.6 + TRACK / 2 + SAFETY, 0.6 + VIA_D / 2 + SAFETY)
    for (x0, x1, y) in slots():
        cx, cy = K((x0 + x1) / 2, y)
        r.add_rect(cx, cy, x1 - x0, SLOT_H, (0, 1), None, keep=EDGE_CLEAR)
    # Pads, fixed tracks and plane vias.
    for p in parts:
        for q in p.pads:
            r.add_pad(q)
    for (x0, y0, x1, y1, w, layer, net) in tracks:
        r.add_seg(x0, y0, x1, y1, w, (0,) if layer == "F.Cu" else (1,), NET_ID[net])
    for (x, y, net) in vias:
        r.add_seg(x, y, x, y, VIA_D, (0, 1), NET_ID[net])
    # Keep a B.Cu path open from J4 pin 1 to the GND fill, or traces wall it in.
    kx, ky = K(61.5, -ROW)
    r.add_rect(kx, ky, 7.0, 1.2, (1,), None, keep=CLEAR)
    # Signals. Crowded chains first, then the mic bus, then the amp lines.
    groups = {}
    for p in parts:
        for q in p.pads:
            if q.net:
                groups.setdefault(q.net, []).append(q)
    order = ["LED_SEL", "LED_BUF", "LED_RAW", "LED_OUT", "SCK_ESP", "WS_ESP", "MIC_SD", "MIC_WS", "MIC_SCK",
             "+3V3", "SPK_LRC", "SPK_BCLK", "SPK_DIN"]
    # 5 V branches first, since they are the widest routed traces.
    start = Pad("TK", 1, "+5V", *K(40.6, 5.0), "circle", 0.6, 0.6, 0.3)
    virt = {i: Pad("V", i, "+5V", x, y, "circle", 0.6, 0.6, 0.3) for i, (x, y, _) in enumerate(FIVE)}
    r.route("+5V", [start, pad_of("J5", 2), virt[0], virt[1]], BRANCH)   # amp, C2, C3
    r.route("+5V", [start, virt[2], virt[3], pad_of("J1", 1)], BRANCH)   # U1, C6, ESP32 VIN
    for net in order:
        r.route(net, groups[net])
    # Stitch the top and bottom GND fills together wherever a via fits.
    free = ~r.via_blocked(NET_ID["GND"])
    placed = []
    for j in range(0, r.ny, 15):
        for i in range(0, r.nx, 15):
            if free[j, i] and all(math.hypot(r.xs[i] - a, r.ys[j] - b) > 4.5 for a, b in placed):
                x, y = round(float(r.xs[i]), 4), round(float(r.ys[j]), 4)
                vias.append((x, y, "GND"))
                placed.append((x, y))
    print(f"GND stitching vias: {len(placed)}")
    r.finish()


def _inside(X, Y, poly):
    inside = np.zeros_like(X, bool)
    for (ax, ay), (bx, by) in zip(poly, poly[1:] + poly[:1]):
        cross = ((ay > Y) != (by > Y))
        with np.errstate(divide="ignore", invalid="ignore"):
            xint = ax + (Y - ay) * (bx - ax) / (by - ay)
        inside ^= cross & (X < xint)
    return inside


def outline():
    """Board outline as KiCad-coordinate points."""
    pts = [(EDGE_L, EDGE_Y), (EDGE_R, EDGE_Y), (EDGE_R, -EDGE_Y), (EDGE_L, -EDGE_Y),
           (EDGE_L, -NOTCH_Y), (EDGE_N, -NOTCH_Y), (EDGE_N, NOTCH_Y), (EDGE_L, NOTCH_Y)]
    return [K(*p) for p in pts]


def slots():
    """(x0, x1, y) of each strain relief slot, enclosure coordinates."""
    return [(63.0, 77.2, SLOT_Y), (63.0, 77.2, -SLOT_Y),   # mics
            (42.0, 56.2, SLOT_Y),                          # amp
            (31.5, 40.5, SLOT_Y),                          # 5 V in
            (31.0, 45.2, -SLOT_Y)]                         # LED


# ---- silkscreen --------------------------------------------------------------
def silk():
    def T(s, x, y, size=1.0, rot=0):
        texts.append((s, *K(x, y), size, rot))

    def row_labels(pins, x0, y, pitch):
        for i, (label, _) in enumerate(pins):
            T(label, x0 + i * pitch, y + (0.5 if i % 2 else -0.6) * (1 if y > 0 else -1), 0.8)   # staggered, so neighbours stay apart

    T("MIC L  (mic only: 3.3 V)", 70.0, 29.6, 1.0)
    T("MIC R  (mic only: 3.3 V)", 70.0, -29.6, 1.0)
    T("AMP  (5 V)", 49.0, 29.6, 1.0)
    T("LED  (5 V)", 38.0, -29.6, 1.0)
    T("5V IN", 36.0, 29.6, 1.0)
    row_labels(MIC_PINS, 65.0, 24.7, PITCH)
    row_labels(MIC_PINS, 65.0, -24.7, PITCH)
    row_labels(AMP_PINS, 44.0, 24.7, PITCH)
    row_labels(LED_PINS, 33.0, -24.7, PITCH)
    T("GND", 33.5, 24.9, 1.0)
    T("+5V", 38.5, 24.9, 1.0)
    T("USB END >>", 72.0, 1.0, 1.2)
    T("ESP32 faces up", 52.0, 1.0, 1.0)
    T("Speaker interface", 57.0, 8.0, 1.2)
    T("2-layer v1", 57.0, 5.8, 1.0)
    for i in (1, 2, 3):
        T(str(i), 53.0 + (i - 2) * 1.25, -6.3, 0.8)
    # References only; values and part details are in ../PCB_PARTS.md.
    for label, x, y in (("R1", 47.0, -7.2), ("R2", 47.6, -9.2), ("R3", 57.38, -7.5), ("R4", 54.84, -7.5),
                        ("C2", 47.0, 20.0), ("C3", 53.5, 20.0), ("C4", 67.2, 18.0), ("C5", 67.2, -18.0),
                        ("C6", 68.0, -2.9), ("U1", 62.0, -2.2), ("1", 59.6, -2.2), ("JP1", 53.0, -3.3),
                        ("Q1", 37.0, 14.0), ("C1", 51.0, -24.5), ("+", 48.5, -18.4)):
        T(label, x, y, 1.0)
    T("VIN", PIN1_X, -15.0, 1.0)
    T("3V3", PIN1_X, 15.0, 1.0)
    # ESP32 outline
    x0, y0 = K(ESP_USB_END_X - ESP_L, 14.0)
    x1, y1 = K(EDGE_R - 0.3, -14.0)
    silk_rects.append((max(x0, K(EDGE_N + 0.3, 0)[0]), y0, x1, y1))


# ---- writer ------------------------------------------------------------------
def uid(*a):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "speaker-if/" + "/".join(map(str, a))))


def q(s):
    return '"' + s.replace('"', '\\"') + '"'


def write_pcb(path):
    o = []
    w = o.append
    w('(kicad_pcb (version 20241229) (generator "make_pcb") (generator_version "9.0")')
    w(' (general (thickness 1.6) (legacy_teardrops no))')
    w(' (paper "A4")')
    w(' (title_block (title "Round speaker interface board") (rev "1"))')
    w(''' (layers
  (0 "F.Cu" signal) (2 "B.Cu" signal)
  (9 "F.Adhes" user "F.Adhesive") (11 "B.Adhes" user "B.Adhesive")
  (13 "F.Paste" user) (15 "B.Paste" user)
  (5 "F.SilkS" user "F.Silkscreen") (7 "B.SilkS" user "B.Silkscreen")
  (1 "F.Mask" user) (3 "B.Mask" user)
  (17 "Dwgs.User" user "User.Drawings") (19 "Cmts.User" user "User.Comments")
  (21 "Eco1.User" user "User.Eco1") (23 "Eco2.User" user "User.Eco2")
  (25 "Edge.Cuts" user) (27 "Margin" user)
  (31 "F.CrtYd" user "F.Courtyard") (29 "B.CrtYd" user "B.Courtyard")
  (35 "F.Fab" user) (33 "B.Fab" user))''')
    w(''' (setup
  (stackup
   (layer "F.SilkS" (type "Top Silk Screen"))
   (layer "F.Mask" (type "Top Solder Mask") (thickness 0.01))
   (layer "F.Cu" (type "copper") (thickness 0.035))
   (layer "dielectric 1" (type "core") (thickness 1.51) (material "FR4") (epsilon_r 4.5) (loss_tangent 0.02))
   (layer "B.Cu" (type "copper") (thickness 0.035))
   (layer "B.Mask" (type "Bottom Solder Mask") (thickness 0.01))
   (layer "B.SilkS" (type "Bottom Silk Screen"))
   (copper_finish "HAL lead-free"))
  (pad_to_mask_clearance 0))''')
    for i, n in enumerate(NETS):
        w(f' (net {i} {q(n)})')

    for p in parts:
        w(f' (footprint {q(p.lib + ":" + p.ref)} (layer "F.Cu") (uuid {q(uid("fp", p.ref))})')
        w(f'  (at {p.x} {p.y}{" " + str(p.rot) if p.rot else ""})')
        w(f'  (property "Reference" {q(p.ref)} (at 0 -2) (layer "F.Fab") (uuid {q(uid("ref", p.ref))})'
          ' (effects (font (size 0.8 0.8) (thickness 0.12))))')
        w(f'  (property "Value" {q(p.value)} (at 0 2) (layer "F.Fab") (uuid {q(uid("val", p.ref))})'
          ' (effects (font (size 0.8 0.8) (thickness 0.12))))')
        smd = not any(a.tht for a in p.pads)
        flags = "" if p.fitted else " exclude_from_pos_files exclude_from_bom"
        w(f'  (attr {"smd" if smd else "through_hole"}{flags})')
        th = math.radians(p.rot)
        ct, st = round(math.cos(th), 9), round(math.sin(th), 9)

        def local(bx, by):
            # board offset -> footprint-local (undo KiCad's CCW footprint rotation)
            return round(bx * ct - by * st, 4), round(bx * st + by * ct, 4)
        for kind, c, r in p.silk:
            cx, cy = local(c[0] - p.x, c[1] - p.y)
            w(f'  (fp_circle (center {cx:.4f} {cy:.4f}) (end {cx+r:.4f} {cy:.4f})'
              f' (stroke (width 0.15) (type solid)) (fill no) (layer "F.SilkS") (uuid {q(uid("c", p.ref))}))')
        for a in p.pads:
            rx, ry = local(a.x - p.x, a.y - p.y)
            pw, ph = (a.h, a.w) if p.rot % 180 else (a.w, a.h)
            ang = f' {p.rot}' if p.rot else ''
            nid = NET_ID[a.net] if a.net else 0
            net = f'(net {nid} {q(a.net)})' if a.net else ''
            if a.tht:
                w(f'  (pad {q(a.num)} thru_hole {a.shape} (at {rx} {ry}{ang}) (size {pw} {ph})'
                  f' (drill {a.drill}) (layers "*.Cu" "*.Mask") {net}'
                  f' (uuid {q(uid("pad", p.ref, a.num))}))')
            else:
                w(f'  (pad {q(a.num)} smd {a.shape} (at {rx} {ry}{ang}) (size {pw} {ph})'
                  f' (layers "F.Cu" "F.Paste" "F.Mask") {net}'
                  f' (uuid {q(uid("pad", p.ref, a.num))}))')
        w(' )')
    for i, (x, y) in enumerate(MOUNTS):
        kx, ky = K(x, y)
        w(f' (footprint "speaker:MOUNT" (layer "F.Cu") (uuid {q(uid("m", i))}) (at {kx} {ky})')
        w(f'  (property "Reference" "H{i+1}" (at 0 -2.2) (layer "F.Fab") (uuid {q(uid("mr", i))})'
          ' (effects (font (size 0.8 0.8) (thickness 0.12))))')
        w(f'  (property "Value" "M2.5" (at 0 2.2) (layer "F.Fab") (uuid {q(uid("mv", i))})'
          ' (effects (font (size 0.8 0.8) (thickness 0.12))))')
        w('  (attr exclude_from_pos_files exclude_from_bom)')
        w(f'  (pad "" np_thru_hole circle (at 0 0) (size {MOUNT_D} {MOUNT_D}) (drill {MOUNT_D})'
          f' (layers "*.Cu" "*.Mask") (uuid {q(uid("mp", i))}))')
        w(' )')

    # outline + slots
    pts = outline()
    for i, (a, b) in enumerate(zip(pts, pts[1:] + pts[:1])):
        w(f' (gr_line (start {a[0]} {a[1]}) (end {b[0]} {b[1]}) (stroke (width 0.1) (type solid))'
          f' (layer "Edge.Cuts") (uuid {q(uid("edge", i))}))')
    for i, (x0, x1, y) in enumerate(slots()):
        a = K(x0, y + SLOT_H / 2)
        b = K(x1, y - SLOT_H / 2)
        w(f' (gr_rect (start {a[0]} {a[1]}) (end {b[0]} {b[1]}) (stroke (width 0.1) (type solid))'
          f' (fill no) (layer "Edge.Cuts") (uuid {q(uid("slot", i))}))')
    for i, (s, x, y, size, rot) in enumerate(texts):
        w(f' (gr_text {q(s)} (at {x} {y} {rot}) (layer "F.SilkS") (uuid {q(uid("t", i, s))})'
          f' (effects (font (size {size} {size}) (thickness {max(0.15, round(size*0.15,3))}))))')
    for i, (x0, y0, x1, y1) in enumerate(silk_rects):
        w(f' (gr_rect (start {x0} {y0}) (end {x1} {y1}) (stroke (width 0.12) (type dash))'
          f' (fill no) (layer "F.Fab") (uuid {q(uid("sr", i))}))')
    for i, (x0, y0, x1, y1, tw, layer, net) in enumerate(tracks):
        w(f' (segment (start {x0} {y0}) (end {x1} {y1}) (width {tw}) (layer {q(layer)})'
          f' (net {NET_ID[net]}) (uuid {q(uid("seg", i))}))')
    for i, (x, y, net) in enumerate(vias):
        w(f' (via (at {x} {y}) (size {VIA_D}) (drill {VIA_DRILL}) (layers "F.Cu" "B.Cu")'
          f' (net {NET_ID[net]}) (uuid {q(uid("via", i))}))')

    # planes
    poly = " ".join(f"(xy {x} {y})" for x, y in pts)
    zones = [("B.Cu", "GND", "thermal"), ("F.Cu", "GND", "thermal")]
    for i, (layer, net, mode) in enumerate(zones):
        conn = "(connect_pads yes (clearance 0.25))" if mode == "solid" else "(connect_pads (clearance 0.25))"
        w(f' (zone (net {NET_ID[net]}) (net_name {q(net)}) (layer {q(layer)}) (uuid {q(uid("z", i))})'
          f' (hatch edge 0.5) {conn} (min_thickness 0.2) (filled_areas_thickness no)'
          f' (fill yes (thermal_gap 0.3) (thermal_bridge_width 0.5))'
          f' (polygon (pts {poly})))')
    w(')')
    with open(path, "w") as f:
        f.write("\n".join(o) + "\n")


def write_project(path):
    """Fab-friendly rules: 0.2 mm clearance, typical of cheap 4-layer service."""
    pro = {
        "board": {"design_settings": {
            "defaults": {"board_outline_line_width": 0.1, "copper_line_width": 0.2},
            "rule_severities": {"lib_footprint_issues": "ignore", "lib_footprint_mismatch": "ignore"},
            "rules": {"min_clearance": 0.15, "min_track_width": 0.15, "min_via_diameter": 0.5,
                      "min_through_hole_diameter": 0.3, "min_copper_edge_clearance": 0.3,
                      "min_hole_clearance": 0.25, "min_hole_to_hole": 0.25,
                      "min_silk_clearance": 0.0, "min_text_height": 0.6,
                      "min_text_thickness": 0.08},
        }},
        "meta": {"filename": NAME + ".kicad_pro", "version": 3},
        "net_settings": {"classes": [{"name": "Default", "clearance": 0.2, "track_width": 0.25,
                                      "via_diameter": 0.6, "via_drill": 0.3}],
                         "meta": {"version": 4}},
    }
    with open(path, "w") as f:
        json.dump(pro, f, indent=2)


def write_netlist(path):
    with open(path, "w", newline="") as f:
        out = csv.writer(f)
        out.writerow(["net", "ref", "pin", "value"])
        rows = []
        for p in parts:
            for a in p.pads:
                if a.net:
                    rows.append((a.net, p.ref, a.num, p.value))
        for r in sorted(rows):
            out.writerow(r)


def write_kicad_netlist(path):
    """Design connection list (pad -> net as assigned here, before routing) in
    KiCad netlist form, so a board checker can compare it with the routed copper."""
    def s(v):
        return '"' + str(v).replace('"', "'") + '"'
    nets = {}
    for p in parts:
        for a in p.pads:
            if a.net:
                nets.setdefault(a.net, []).append((p.ref, a.num))
    lines = ['(export (version "E")',
             f' (design (source {s(NAME + ".kicad_sch")}) (tool "make_pcb.py"))',
             ' (components']
    lines += [f'  (comp (ref {s(p.ref)}) (value {s(p.value)}))' for p in sorted(parts, key=lambda p: p.ref)]
    lines += [' )', ' (nets']
    for i, (n, nodes) in enumerate(sorted(nets.items()), 1):
        lines.append(f'  (net (code {s(i)}) (name {s(n)})'
                     + "".join(f' (node (ref {s(r)}) (pin {s(pin)}))' for r, pin in sorted(nodes)) + ')')
    lines += [' )', ')']
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")


# ---- check against the firmware --------------------------------------------
def check_firmware_pins():
    cfg = os.path.join(HERE, "..", "firmware", "include", "config.h")
    text = open(cfg).read()
    want = {"PIN_SPK_BCLK": "SPK_BCLK", "PIN_SPK_LRC": "SPK_LRC", "PIN_SPK_DIN": "SPK_DIN",
            "PIN_MIC_SCK": "SCK_ESP", "PIN_MIC_WS": "WS_ESP", "PIN_MIC_SD": "MIC_SD",
            "PIN_LED": "LED_RAW"}
    for define, net in want.items():
        pin = re.search(rf"#define {define} (\d+)", text).group(1)
        assert ESP_NET.get(pin) == net, f"{define}={pin} but board has {ESP_NET.get(pin)}"
    assert len(ROW_A) == 15 and len(ROW_B) == 15
    assert set(ESP_NET) <= set(ROW_A + ROW_B)
    print("firmware pin map OK:", ", ".join(f"{k}" for k in want))


def main():
    check_firmware_pins()
    build_parts()
    silk()
    route_all()
    write_pcb(os.path.join(HERE, NAME + ".kicad_pcb"))
    write_project(os.path.join(HERE, NAME + ".kicad_pro"))
    write_kicad_netlist(os.path.join(HERE, NAME + ".net"))
    write_netlist(os.path.join(HERE, "netlist.csv"))
    print(f"parts {len(parts)}, tracks {len(tracks)}, vias {len(vias)}")


if __name__ == "__main__":
    main()
