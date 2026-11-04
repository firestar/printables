#!/usr/bin/env python3
"""List what each piece of copper in the Gerber zip actually connects.

Uses only the copper layers and drill file to group pads, with no net names, then
walks every circuit from the 5 V input through to each load, crossing a part only
where the part itself joins two groups.  Pad positions come from the board file.

Run from the repo root: PYTHONPATH=.pydeps python3 -W ignore smart_speaker/pcb_2layer/trace_circuits.py
"""
import os
import sys
from collections import defaultdict

import numpy as np
from gerbonara import ExcellonFile, GerberFile
from gerbonara.utils import MM
from scipy import ndimage

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check_gerbers as cg  # noqa: E402

J1 = ["VIN", "GND", "13", "12", "14", "27", "26", "25", "33", "32", "35", "34", "39", "36", "EN"]
J2 = ["3V3", "GND", "15", "2", "4", "16", "17", "5", "18", "19", "21", "3", "1", "22", "23"]
PORT = {"J3": ["GND", "3V3", "SCK", "WS", "SD"], "J4": ["GND", "3V3", "SCK", "WS", "SD"],
        "J5": ["GND", "5V", "LRC", "BCK", "DIN"], "J6": ["GND", "5V", "DIN", "NC", "NC"],
        "J7": ["GND", "+5V"]}
ROLE = {"Q1": ["G", "S", "D"], "U1": ["OE", "A", "GND", "Y", "VCC"], "JP1": ["1", "2", "3"]}
NICE = {"J3": "MIC L", "J4": "MIC R", "J5": "AMP", "J6": "LED", "J7": "5V IN"}


def name(ref, num):
    if ref == "J1":
        return "ESP32 " + ("GPIO" if J1[int(num) - 1].isdigit() else "") + J1[int(num) - 1]
    if ref == "J2":
        return "ESP32 " + ("GPIO" if J2[int(num) - 1].isdigit() else "") + J2[int(num) - 1]
    if ref in PORT:
        return f"{NICE[ref]} {PORT[ref][int(num) - 1]}"
    if ref in ROLE:
        return f"{ref}.{ROLE[ref][int(num) - 1]}"
    return f"{ref}.{num}"


def main():
    tmp = cg.load_zip()
    d = tmp.name
    G = {n: GerberFile.open(os.path.join(d, f"{cg.PREFIX}{n}.gbr")) for n in ("F_Cu", "B_Cu", "Edge_Cuts")}
    bbox = cg.outline_bbox(G["Edge_Cuts"])
    canvas = cg.Canvas((bbox[0] - 1, bbox[1] - 1, bbox[2] + 1, bbox[3] + 1))
    rast = {n: cg.raster(G[n], canvas) for n in ("F_Cu", "B_Cu")}
    holes = [(p.x, p.y) for o in ExcellonFile.open(os.path.join(d, f"{cg.PREFIX}PTH.drl")).drills()
             for p in o.to_primitives(MM)]
    tmp.cleanup()

    labels = {n: ndimage.label(rast[n], structure=np.ones((3, 3)))[0] for n in rast}
    uf = cg.UF()
    for x, y in holes:
        r, c = canvas.cell(x, y)
        here = [(n, labels[n][r, c]) for n in cg.COPPER if labels[n][r, c]]
        for a, b in zip(here, here[1:]):
            uf.union(a, b)

    groups = defaultdict(list)
    where = {}
    for ref, num, _net, x, y, npth in cg.read_pads():
        if npth:
            continue
        r, c = canvas.cell(x, y)
        g = uf.find(("F_Cu", labels["F_Cu"][r, c]))
        groups[g].append((ref, num))
        where[(ref, num)] = g

    print(f"{len(groups)} separate pieces of copper from the Gerbers\n")
    connected = [g for g in groups.values() if len(g) > 1]
    for members in sorted(connected, key=lambda m: -len(m)):
        print(f"{len(members):3d} pads: " + ", ".join(name(*p) for p in sorted(members)
                                                     if not (p[0] in "J1 J2" and name(*p).endswith("GND") and False)))
    single = sorted(name(*m[0]) for m in groups.values() if len(m) == 1)
    print(f"\nnot connected to anything, by design: {', '.join(single)}\n")

    def same(a, b):
        return where[a] == where[b]

    # Circuits, one hop at a time, each hop being copper from the Gerbers.
    paths = {
        "Power in: 5V IN + to Q1 drain": [(("J7", "2"), ("Q1", "3"))],
        "Q1 gate held at ground (switches on)": [(("Q1", "1"), ("J7", "1"))],
        "Q1 source to ESP32 VIN, amp and LED 5 V": [(("Q1", "2"), ("J1", "1")), (("Q1", "2"), ("J5", "2")), (("Q1", "2"), ("J6", "2"))],
        "C1 across LED supply": [(("C1", "1"), ("J6", "2")), (("C1", "2"), ("J6", "1"))],
        "C2, C3 across amp supply": [(("C2", "1"), ("J5", "2")), (("C2", "2"), ("J5", "1")), (("C3", "1"), ("J5", "2")), (("C3", "2"), ("J5", "1"))],
        "C6 across shifter supply": [(("C6", "1"), ("U1", "5")), (("C6", "2"), ("U1", "3"))],
        "All grounds joined": [(("J7", "1"), ("J1", "2")), (("J7", "1"), ("J2", "2")), (("J7", "1"), ("J3", "1")), (("J7", "1"), ("J4", "1")), (("J7", "1"), ("J5", "1")), (("J7", "1"), ("J6", "1"))],
        "ESP32 3V3 to both mics": [(("J2", "1"), ("J3", "2")), (("J2", "1"), ("J4", "2")), (("C4", "1"), ("J3", "2")), (("C5", "1"), ("J4", "2"))],
        "C4, C5 to ground": [(("C4", "2"), ("J7", "1")), (("C5", "2"), ("J7", "1"))],
        "Mic SCK: GPIO32 to R4, R4 to both mics": [(("J1", "10"), ("R4", "1")), (("R4", "2"), ("J3", "3")), (("R4", "2"), ("J4", "3"))],
        "Mic WS: GPIO33 to R3, R3 to both mics": [(("J1", "9"), ("R3", "1")), (("R3", "2"), ("J3", "4")), (("R3", "2"), ("J4", "4"))],
        "Mic SD: both mics to GPIO35, R2 to ground": [(("J3", "5"), ("J1", "11")), (("J4", "5"), ("J1", "11")), (("R2", "1"), ("J1", "11")), (("R2", "2"), ("J7", "1"))],
        "Amp: GPIO25 LRC, GPIO26 BCK, GPIO22 DIN": [(("J1", "8"), ("J5", "3")), (("J1", "7"), ("J5", "4")), (("J2", "14"), ("J5", "5"))],
        "LED data: GPIO27 to U1 A and JP1.1": [(("J1", "6"), ("U1", "2")), (("J1", "6"), ("JP1", "1"))],
        "LED data: U1 Y to JP1.3": [(("U1", "4"), ("JP1", "3"))],
        "LED data: JP1.2 to R1, R1 to LED DIN": [(("JP1", "2"), ("R1", "2")), (("R1", "1"), ("J6", "3"))],
        "Shifter enabled and powered": [(("U1", "1"), ("J7", "1")), (("U1", "3"), ("J7", "1")), (("U1", "5"), ("Q1", "2"))],
    }
    bad = 0
    print("Circuit paths:")
    for title, hops in paths.items():
        ok = all(same(a, b) for a, b in hops)
        bad += not ok
        print(f"  {'OK  ' if ok else 'FAIL'} {title}")
    # Things that must NOT touch.
    apart = [(("J2", "1"), ("J1", "1"), "3V3 and 5 V"), (("J1", "1"), ("J7", "1"), "5 V and GND"),
             (("J2", "1"), ("J7", "1"), "3V3 and GND"), (("J7", "2"), ("Q1", "2"), "Q1 drain and source"),
             (("J7", "2"), ("J7", "1"), "input + and GND"), (("R4", "1"), ("R4", "2"), "across R4"),
             (("R3", "1"), ("R3", "2"), "across R3"), (("R1", "1"), ("R1", "2"), "across R1"),
             (("JP1", "1"), ("JP1", "2"), "JP1 1-2, open until bridged"), (("JP1", "2"), ("JP1", "3"), "JP1 2-3, open until bridged")]
    print("\nMust stay separate:")
    for a, b, title in apart:
        ok = not same(a, b)
        bad += not ok
        print(f"  {'OK  ' if ok else 'FAIL'} {title}")
    print("\nCOPPER IS COMPLETE" if not bad else f"\n{bad} PROBLEMS")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
