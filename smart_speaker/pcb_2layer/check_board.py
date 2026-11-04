#!/usr/bin/env python3
"""Check the saved board and the exported Gerbers, independently of make_pcb.py's
tables.  The expected connections below are typed from ../electronics/WIRING.md
and the listing's pinout.  Needs only the standard library.

Run from smart_speaker/pcb/ after export.sh:  python3 check_board.py
"""
import glob
import json
import re
import sys

BOARD = "interface_board_2l.kicad_pcb"
text = open(BOARD).read()

# ---- read pad nets out of the saved board ------------------------------------
pads = {}
for block in re.split(r"\n\s*\(footprint ", text)[1:]:
    ref = re.search(r'"Reference" "([^"]+)"', block).group(1)
    for num, body in re.findall(r'\(pad "([^"]*)" (.*?)\n\s*\)', block, re.S):
        m = re.search(r'\(net \d+ "([^"]*)"\)', body)
        pads[(ref, num)] = m.group(1) if m else ""

# ESP32 socket pin number -> name, counted from the USB end. J1 = VIN row, J2 = 3V3 row.
J1 = ["VIN", "GND", "13", "12", "14", "27", "26", "25", "33", "32", "35", "34", "39", "36", "EN"]
J2 = ["3V3", "GND", "15", "2", "4", "16", "17", "5", "18", "19", "21", "3", "1", "22", "23"]
esp = {name: ("J1", str(i + 1)) for i, name in enumerate(J1) if name != "GND"}
esp.update({name: ("J2", str(i + 1)) for i, name in enumerate(J2) if name != "GND"})

fails = []


def same(label, *items):
    nets = {pads[i] for i in items}
    if len(nets) != 1 or nets == {""}:
        fails.append(f"{label}: {items} -> {nets}")


# WIRING.md pin map, by connection rather than by net name.
same("mic SCK GPIO32 to R4", esp["32"], ("R4", "1"))
same("mic SCK R4 to mics", ("R4", "2"), ("J3", "3"), ("J4", "3"))
same("mic WS GPIO33 to R3", esp["33"], ("R3", "1"))
same("mic WS R3 to mics", ("R3", "2"), ("J3", "4"), ("J4", "4"))
if pads[("R4", "1")] == pads[("R4", "2")] or pads[("R3", "1")] == pads[("R3", "2")]:
    fails.append("R3 or R4 is bypassed")
same("mic SD GPIO35", esp["35"], ("J3", "5"), ("J4", "5"), ("R2", "1"))
same("mic 3V3", esp["3V3"], ("J3", "2"), ("J4", "2"), ("C4", "1"), ("C5", "1"))
same("amp LRC GPIO25", esp["25"], ("J5", "3"))
same("amp BCLK GPIO26", esp["26"], ("J5", "4"))
same("amp DIN GPIO22", esp["22"], ("J5", "5"))
same("5 V rail", esp["VIN"], ("J5", "2"), ("J6", "2"), ("C1", "1"), ("C2", "1"), ("C3", "1"),
     ("C6", "1"), ("U1", "5"), ("Q1", "2"))
same("GND", ("J1", "2"), ("J2", "2"), ("J3", "1"), ("J4", "1"), ("J5", "1"), ("J6", "1"),
     ("J7", "1"), ("C1", "2"), ("C2", "2"), ("C3", "2"), ("C4", "2"), ("C5", "2"), ("C6", "2"),
     ("R2", "2"), ("U1", "1"), ("U1", "3"), ("Q1", "1"))
same("input to FET drain", ("J7", "2"), ("Q1", "3"))
same("LED data in", esp["27"], ("U1", "2"), ("JP1", "1"))
same("LED shifted", ("U1", "4"), ("JP1", "3"))
same("LED jumper to R1", ("JP1", "2"), ("R1", "2"))
same("LED out", ("R1", "1"), ("J6", "3"))
if pads[("Q1", "3")] == pads[("Q1", "2")]:
    fails.append("Q1 drain and source shorted")
if pads[esp["3V3"]] == pads[esp["VIN"]]:
    fails.append("3V3 and 5V on the same net")
# Used ESP32 pins only: nothing else on the socket may carry a net.
used = {"VIN", "3V3", "22", "25", "26", "27", "32", "33", "35"}
for name, key in esp.items():
    if name not in used and pads[key]:
        fails.append(f"ESP32 {name} unexpectedly on net {pads[key]}")

# ---- DRC report ------------------------------------------------------------
rpt = open("drc.rpt").read()
for pat in (r"Found 0 DRC violations", r"Found 0 unconnected pads", r"Found 0 Footprint errors"):
    if pat not in rpt:
        fails.append("drc.rpt lacks: " + pat)

# ---- Gerbers -----------------------------------------------------------------
job = json.load(open("gerbers/interface_board_2l-job.gbrjob"))
if job["GeneralSpecs"]["LayerNumber"] != 2:
    fails.append("Gerber job is not 2 layers")
size = job["GeneralSpecs"]["Size"]
print(f"board size {size['X']:.1f} x {size['Y']:.1f} mm, "
      f"{job['GeneralSpecs']['LayerNumber']} layers")
for name in ("F_Cu", "B_Cu", "Edge_Cuts", "F_Mask", "B_Mask", "F_Silkscreen"):
    files = glob.glob(f"gerbers/*-{name}.gbr")
    if not files or "M02*" not in open(files[0]).read():
        fails.append(f"Gerber {name} missing or truncated")


def holes(path):
    tools, count, cur = {}, {}, None
    for line in open(path):
        line = line.strip()
        m = re.match(r"T(\d+)C([\d.]+)", line)
        if m:
            tools[m.group(1)] = float(m.group(2))
        elif re.fullmatch(r"T\d+", line):
            cur = line[1:]
        elif line.startswith("X") and cur:
            count[tools[cur]] = count.get(tools[cur], 0) + 1
    return count


pth, npth = holes("gerbers/interface_board_2l-PTH.drl"), holes("gerbers/interface_board_2l-NPTH.drl")
print("plated holes:", dict(sorted(pth.items())), " unplated:", dict(sorted(npth.items())))
vias = len(re.findall(r"\n\s*\(via\b", text))
want = {1.0: 30, 1.2: 20, 1.5: 2, 0.9: 2, 0.3: vias}
if pth != want:
    fails.append(f"plated holes {pth} != {want}")
if npth != {2.7: 4}:
    fails.append(f"unplated holes {npth}")

if fails:
    print("FAILED")
    for f in fails:
        print(" -", f)
    sys.exit(1)
print(f"ALL BOARD CHECKS OK ({len(pads)} pads, {vias} vias)")
