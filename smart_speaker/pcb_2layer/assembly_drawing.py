#!/usr/bin/env python3
"""Assembly drawing for the speaker interface board: where each part goes,
which way round, and how to tell the loose resistors and capacitors apart.

Positions and pads come straight from make_pcb.py, so the drawing always
matches the board.  Both the 2-layer and 4-layer boards share the same
placement, so one drawing serves both.

Run from the repo root:
    PYTHONPATH=.pydeps python3 smart_speaker/pcb_2layer/assembly_drawing.py
Writes smart_speaker/assembly.png and smart_speaker/assembly.pdf.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import matplotlib                                     # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt                       # noqa: E402
from matplotlib.patches import Circle, FancyBboxPatch, Polygon, Rectangle  # noqa: E402

import make_pcb as mp                                 # noqa: E402

OUT = os.path.join(HERE, "..")

# Colour per part family, so a glance at the drawing says what kind of part goes where.
RES, CAP, ELEC, SEMI, CONN, JUMP = "#1f6fd1", "#1a9b4b", "#8a3ffc", "#e07000", "#6b6b6b", "#c9a400"

# label, colour, value, marking on the part
INFO = {
    "R1": (RES, "330 Ω", "331 or 3300"),
    "R2": (RES, "100 kΩ", "104 or 1003"),
    "R3": (RES, "100 Ω", "101 or 1000"),
    "R4": (RES, "100 Ω", "101 or 1000"),
    "C2": (CAP, "10 µF", "unmarked"),
    "C3": (CAP, "100 nF", "unmarked"),
    "C4": (CAP, "100 nF", "unmarked"),
    "C5": (CAP, "100 nF", "unmarked"),
    "C6": (CAP, "100 nF", "unmarked"),
    "C1": (ELEC, "1000 µF 10 V", "printed on can"),
    "Q1": (SEMI, "AO3401A", ""),
    "U1": (SEMI, "74AHCT1G125", ""),
    "J1": (CONN, "1x15 socket", ""),
    "J2": (CONN, "1x15 socket", ""),
    "J3": (CONN, "MIC L wires", ""),
    "J4": (CONN, "MIC R wires", ""),
    "J5": (CONN, "AMP wires", ""),
    "J6": (CONN, "LED wires", ""),
    "J7": (CONN, "5V IN wires", ""),
    "JP1": (JUMP, "solder bridge", ""),
}

# Label per part: offset from the part centre (KiCad mm, y down), alignment, and text
# (None = "REF\nvalue").  Tuned by eye so nothing overlaps on the rendered drawing.
LABEL_AT = {
    "R1": (-1.9, 0, "right", "center", None), "R2": (-1.9, 0, "right", "center", None),
    "R3": (0, -1.55, "center", "bottom", "R3"), "R4": (0, -1.55, "center", "bottom", "R4"),
    "C2": (0, 1.8, "center", "top", None), "C3": (0, 1.8, "center", "top", None),
    "C4": (0, 1.8, "center", "top", None), "C5": (0, 1.8, "center", "top", None),
    "C6": (0, 1.8, "center", "top", None),
    "Q1": (0, 2.2, "center", "top", None), "U1": (0, 2.2, "center", "top", None),
    "JP1": (0, -2.4, "center", "bottom", "JP1: bridge 2–3"),
}


def build():
    mp.build_parts()
    return {p.ref: p for p in mp.parts}


def draw(ax, parts):
    pts = mp.outline()
    ax.add_patch(Polygon(pts, closed=True, fc="#f4f1e8", ec="black", lw=1.4, zorder=0))
    for x0, x1, y in mp.slots():
        (a, b), (c, d) = mp.K(x0, y + mp.SLOT_H / 2), mp.K(x1, y - mp.SLOT_H / 2)
        ax.add_patch(FancyBboxPatch((a, b), c - a, d - b, boxstyle="round,pad=0,rounding_size=1.1",
                                    fc="white", ec="black", lw=0.8, zorder=1))
    for x, y in mp.MOUNTS:
        ax.add_patch(Circle(mp.K(x, y), mp.MOUNT_D / 2, fc="white", ec="black", lw=0.8, zorder=1))

    # ESP32 module footprint (it sits on J1/J2, above everything else).
    x0, y0 = mp.K(mp.ESP_USB_END_X - mp.ESP_L, 14.0)
    x1, y1 = mp.K(mp.EDGE_R - 0.3, -14.0)
    x0 = max(x0, mp.K(mp.EDGE_N + 0.3, 0)[0])
    ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, fc="none", ec="#999", lw=0.8, ls="--", zorder=1))
    ux, uy = mp.K(mp.ESP_USB_END_X - 25.0, 2.5)
    ax.text(ux, uy, "ESP32 module plugs in above the board here:\nparts side up, USB end to the right →",
            ha="center", va="center", fontsize=6.5, color="#777", zorder=2)

    for p in parts.values():
        colour, value, _ = INFO.get(p.ref, (CONN, p.value, ""))
        for a in p.pads:
            w, h = a.w, a.h
            if a.tht:
                if a.shape == "rect":
                    ax.add_patch(Rectangle((a.x - w / 2, a.y - h / 2), w, h, fc="#d9a441", ec="k",
                                           lw=0.4, zorder=3))
                else:
                    ax.add_patch(Circle((a.x, a.y), w / 2, fc="#d9a441", ec="k", lw=0.4, zorder=3))
                ax.add_patch(Circle((a.x, a.y), a.drill / 2, fc="white", ec="none", zorder=4))
            else:
                ax.add_patch(Rectangle((a.x - w / 2, a.y - h / 2), w, h, fc="#d9a441", ec="k",
                                       lw=0.4, zorder=3))

        # Part bodies.
        xs = [a.x for a in p.pads]
        ys = [a.y for a in p.pads]
        if p.ref.startswith(("R", "C")) and p.ref != "C1":
            vertical = p.rot % 180 != 0
            bw, bh = (1.25, 2.0) if vertical else (2.0, 1.25)
            ax.add_patch(Rectangle((p.x - bw / 2, p.y - bh / 2), bw, bh, fc=colour, ec="k", lw=0.5,
                                   alpha=0.85, zorder=5))
        elif p.ref == "C1":
            (cx, cy), r = mp.K(51.0, -21.0), 5.0
            ax.add_patch(Circle((cx, cy), r, fc=colour, ec="k", lw=0.8, alpha=0.25, zorder=2))
            # Negative stripe on the side away from the + pad.
            ax.add_patch(Rectangle((cx + r * 0.55, cy - r * 0.83), r * 0.35, r * 1.66, fc="#333",
                                   alpha=0.6, zorder=2))
            ax.text(xs[0], ys[0] - 2.0, "+", ha="center", va="center", fontsize=12, weight="bold",
                    color=colour, zorder=6)
            ax.text(cx + r * 0.72, cy, "−", ha="center", va="center", fontsize=12, weight="bold",
                    color="white", zorder=6)
        elif p.ref in ("Q1", "U1"):
            ax.add_patch(Rectangle((p.x - 0.75, p.y - 1.5), 1.5, 3.0, fc="#333", ec="k", lw=0.5, zorder=5))
            ax.add_patch(Circle((p.x - 0.4, p.y - 1.1), 0.22, fc="white", zorder=6))   # pin 1 dot
            if p.ref == "U1":
                ax.text(min(xs) - 1.0, min(ys), "1", ha="right", va="center", fontsize=7, weight="bold",
                        color=colour, zorder=6)
            else:
                for a, name in zip(p.pads, ("G", "S", "D")):
                    dx = -1.1 if a.x < p.x else 1.1
                    ax.text(a.x + dx, a.y, name, ha="right" if dx < 0 else "left", va="center",
                            fontsize=6.5, weight="bold", color="#333", zorder=6)
        elif p.ref == "JP1":
            b, c = p.pads[1], p.pads[2]
            ax.add_patch(Rectangle((b.x, b.y - 0.35), c.x - b.x, 0.7, fc="#b0b0b0", ec="k", lw=0.4,
                                   zorder=6))
            for i, a in enumerate(p.pads, 1):
                ax.text(a.x, a.y - 1.0, str(i), ha="center", va="bottom", fontsize=5.5, zorder=6)
        elif p.ref in ("J1", "J2"):
            x0b, x1b = min(xs) - 1.27, max(xs) + 1.27
            ax.add_patch(Rectangle((x0b, p.y - 1.27), x1b - x0b, 2.54, fc="none", ec=colour, lw=0.8,
                                   zorder=2))
        # Labels.
        if p.ref in LABEL_AT:
            dx, dy, ha, va, text = LABEL_AT[p.ref]
            size = 6.5 if text is None or p.ref == "JP1" else 6
            ax.text(p.x + dx, p.y + dy, text or f"{p.ref}\n{value}", ha=ha, va=va, fontsize=size,
                    weight="bold", color=colour, zorder=7, linespacing=1.0)
            if p.ref == "R3":
                ax.text(p.x + 1.3, p.y, "← R4, R3:\n100 Ω each", ha="left", va="center", fontsize=6,
                        weight="bold", color=colour, zorder=7, linespacing=1.0)
        elif p.ref == "C1":
            (cx, cy) = mp.K(51.0, -21.0)
            ax.text(cx - 0.8, cy + 2.6, f"C1\n{value}", ha="center", va="center", fontsize=6.5,
                    weight="bold", color=colour, zorder=7, linespacing=1.0)
        elif p.ref in ("J1", "J2"):
            ax.text(sum(xs) / len(xs), p.y + (1.8 if p.ref == "J1" else 1.6),
                    f"{p.ref} ({'VIN' if p.ref == 'J1' else '3V3'} row): 15-pin socket, square pad = USB end",
                    ha="center", va="top", fontsize=6, color=colour, zorder=7)
        else:   # wire ports
            yoff = 2.2 if p.y > 100 else -2.2
            ax.text(sum(xs) / len(xs), p.y + yoff, f"{p.ref}  {value}", ha="center",
                    va="top" if yoff > 0 else "bottom", fontsize=6, color=colour, zorder=7)
    xs = [x for x, _ in pts]
    ys = [y for _, y in pts]
    ax.set_xlim(min(xs) - 3, max(xs) + 3)
    ax.set_ylim(max(ys) + 3, min(ys) - 3)      # KiCad y runs down
    ax.set_aspect("equal")
    ax.axis("off")


def legend(ax):
    ax.axis("off")
    y = 0.98

    def line(text, size=8.5, weight="normal", colour="black", gap=0.027):
        nonlocal y
        ax.text(0.0, y, text, fontsize=size, weight=weight, color=colour, va="top", transform=ax.transAxes)
        y -= gap

    line("Speaker interface board – assembly", 12, "bold", gap=0.035)
    line("Top view, actual layout. Same placement on the 2-layer and 4-layer boards.", 8, gap=0.042)

    line("Resistors (blue) – 0805, printed code", 9.5, "bold", RES)
    for ref, val, code in (("R1", "330 Ω", "331  or  3300"), ("R2", "100 kΩ", "104  or  1003"),
                           ("R3, R4", "100 Ω", "101  or  1000")):
        line(f"   {ref:<7} {val:<8} reads  {code}", 8.5, colour=RES)
    line("   3 digits (5%): first two digits, then number of zeros. 4 digits (1%):", 7.5)
    line("   first three digits, then number of zeros. Either way round.", 7.5, gap=0.042)

    line("Ceramic capacitors (green) – 0805, NOT marked", 9.5, "bold", CAP)
    line("   C2 = 10 µF.   C3, C4, C5, C6 = 100 nF.   Either way round.", 8.5, colour=CAP)
    line("   Keep each value in its tape strip until fitted; the tape label is", 7.5)
    line("   the only marking. If two get mixed up, measure them: 10 µF vs 0.1 µF.", 7.5)
    line("   Fit C2 first, alone, so it can't be confused with the 100 nF parts.", 7.5, gap=0.042)

    line("Polarised and one-way parts", 9.5, "bold", ELEC)
    line("   C1 1000 µF: long lead (+) in the square pad marked +;", 8.5, colour=ELEC)
    line("   the printed stripe (−) faces right, away from the +.", 8.5, colour=ELEC)
    line("   U1 74AHCT1G125 (SOT-23-5): pin 1 dot to the '1' at top left;", 8.5, colour=SEMI)
    line("   3 legs on the left, 2 on the right.", 8.5, colour=SEMI)
    line("   Q1 AO3401A (SOT-23): 2 legs on the left (G, S), 1 on the right (D).", 8.5, colour=SEMI)
    line("   Both only fit one way; check the text on the chip reads upright.", 7.5, gap=0.042)

    line("Solder bridge", 9.5, "bold", JUMP)
    line("   JP1: bridge the middle pad (2) to the right pad (3). Required.", 8.5, colour=JUMP, gap=0.042)

    line("Sockets and wires (grey)", 9.5, "bold", CONN)
    line("   J1, J2: 15-pin female sockets, either way round.", 8.5, colour=CONN)
    line("   ESP32 also fits turned 180°, which misconnects power: USB end to the right.", 8.5,
         "bold", CONN)
    line("   J3–J7: cable wires, square pad = first pin (see PCB_PARTS.md).", 8.5, colour=CONN, gap=0.042)

    line("Suggested order", 9.5, "bold")
    for s in ("1. U1, Q1 (smallest, need flat access)", "2. R1–R4, then C2, then C3–C6",
              "3. Bridge JP1 2–3", "4. C1, then J1/J2 sockets", "5. Cable wires J3–J7 last"):
        line("   " + s, 8.5)


def main():
    parts = build()
    fig = plt.figure(figsize=(16.5, 9.6))
    ax = fig.add_axes([0.01, 0.02, 0.56, 0.96])
    draw(ax, parts)
    lg = fig.add_axes([0.59, 0.02, 0.40, 0.96])
    legend(lg)
    for ext in ("png", "pdf"):
        fig.savefig(os.path.join(OUT, f"assembly.{ext}"), dpi=200)
    print("wrote", os.path.normpath(os.path.join(OUT, "assembly.png")), "and .pdf")


if __name__ == "__main__":
    main()
