"""Generate the wiring diagram (wiring.svg) for the round smart speaker.

ESP32-WROOM-32 devkit + MAX98357A amp + 2x INMP441 mics + WS2812B halo ring.
Run: python3 wiring.py
"""
import os

W, H = 1500, 1200
RED, ORANGE, BLACK = "#d62728", "#ff7f0e", "#222"
SIG = {"SCK": "#1f77b4", "WS": "#2ca02c", "SD": "#9467bd",
       "BCLK": "#1f77b4", "LRC": "#2ca02c", "DIN": "#9467bd", "LED": "#17becf"}

out = []


def add(s):
    out.append(s)


def line(pts, color, w=2.5, dash=None):
    d = " ".join(f"{x},{y}" for x, y in pts)
    extra = f' stroke-dasharray="{dash}"' if dash else ""
    add(f'<polyline points="{d}" fill="none" stroke="{color}" stroke-width="{w}"'
        f' stroke-linejoin="round"{extra}/>')


def dot(x, y, color=BLACK):
    add(f'<circle cx="{x}" cy="{y}" r="5" fill="{color}"/>')


def text(x, y, s, size=15, anchor="start", weight="normal", color="#111"):
    add(f'<text x="{x}" y="{y}" font-size="{size}" text-anchor="{anchor}" '
        f'font-weight="{weight}" fill="{color}" font-family="Helvetica, Arial, sans-serif">{s}</text>')


def box(x0, y0, x1, y1, title, sub=None, fill="#f3f3f3"):
    add(f'<rect x="{x0}" y="{y0}" width="{x1 - x0}" height="{y1 - y0}" rx="10" '
        f'fill="{fill}" stroke="#444" stroke-width="2"/>')
    text((x0 + x1) / 2, y0 + 24, title, 17, "middle", "bold")
    if sub:
        for i, s in enumerate(sub.split("\n")):
            text((x0 + x1) / 2, y0 + 44 + 17 * i, s, 13, "middle", color="#555")


def pin(x, y, name, side):
    """Pin stub on a box edge; side 'l' or 'r' = which edge."""
    add(f'<rect x="{x - 5}" y="{y - 5}" width="10" height="10" fill="#fff" stroke="#444"/>')
    if side == "r":
        text(x - 10, y + 5, name, 14, "end")
    else:
        text(x + 10, y + 5, name, 14, "start")


def ground(x, y):
    line([(x, y), (x, y + 14)], BLACK)
    for i, half in enumerate((12, 8, 4)):
        yy = y + 14 + 5 * i
        line([(x - half, yy), (x + half, yy)], BLACK, 2)


def resistor_h(x0, x1, y, color, label):
    """Horizontal resistor in a wire from x0 to x1."""
    mid0, mid1 = x0 + (x1 - x0) * 0.25, x0 + (x1 - x0) * 0.75
    n = 6
    zz = [(x0, y), (mid0, y)]
    for i in range(n):
        zz.append((mid0 + (mid1 - mid0) * (i + 0.5) / n, y + (-7 if i % 2 == 0 else 7)))
    zz += [(mid1, y), (x1, y)]
    line(zz, color)
    text((x0 + x1) / 2, y - 12, label, 13, "middle")


def resistor_v(x, y0, y1, color, label):
    mid0, mid1 = y0 + (y1 - y0) * 0.25, y0 + (y1 - y0) * 0.75
    n = 6
    zz = [(x, y0), (x, mid0)]
    for i in range(n):
        zz.append((x + (-7 if i % 2 == 0 else 7), mid0 + (mid1 - mid0) * (i + 0.5) / n))
    zz += [(x, mid1), (x, y1)]
    line(zz, color)
    text(x + 12, (y0 + y1) / 2 + 5, label, 13)


def cap_v(x, y0, y1, label):
    ym = (y0 + y1) / 2
    line([(x, y0), (x, ym - 4)], RED)
    line([(x - 14, ym - 4), (x + 14, ym - 4)], BLACK, 3)
    line([(x - 14, ym + 4), (x + 14, ym + 4)], BLACK, 3)
    line([(x, ym + 4), (x, y1)], BLACK)
    text(x + 20, ym + 5, label, 13)


def speaker(x, y):
    add(f'<rect x="{x}" y="{y - 22}" width="18" height="44" fill="#ddd" stroke="#444" stroke-width="2"/>')
    add(f'<polygon points="{x + 18},{y - 22} {x + 50},{y - 48} {x + 50},{y + 48} {x + 18},{y + 22}" '
        f'fill="#eee" stroke="#444" stroke-width="2"/>')


# ---- layout ---------------------------------------------------------------------
add(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">')
add(f'<rect width="{W}" height="{H}" fill="#fff"/>')
text(40, 40, "Round smart speaker - wiring diagram", 26, weight="bold")
text(40, 64, "ESP32-WROOM-32 devkit (30-pin, USB-C)  |  MAX98357A I2S amp  |  2x INMP441 I2S mics  |"
     "  WS2812B halo ring  |  Gikfun 2&quot; 4 ohm 3 W driver", 14, color="#555")

# ESP32
EX0, EX1, EY0, EY1 = 600, 820, 150, 560
box(EX0, EY0, EX1, EY1, "ESP32 devkit", None, "#e8f0fe")
for name, y in [("3V3", 200), ("GND", 240), ("GPIO32", 320), ("GPIO33", 360), ("GPIO35", 400)]:
    pin(EX0, y, name, "l")
for name, y in [("VIN / 5V", 200), ("GND", 240), ("GPIO25", 290), ("GPIO26", 330),
                ("GPIO22", 370), ("GPIO27", 480)]:
    pin(EX1, y, name, "r")
text(EX0 + 110, EY1 - 60, "USB-C: flashing / opt. power", 13, "middle", color="#555")
text(EX0 + 110, EY1 - 40, "I2S0 = speaker   I2S1 = mics", 13, "middle", color="#555")
text(EX0 + 110, EY1 - 20, "no strapping pins used", 13, "middle", color="#555")

# Mics
for (y0, label, lr) in [(130, "INMP441 - LEFT mic", "GND"), (440, "INMP441 - RIGHT mic", "3V3")]:
    box(150, y0, 330, y0 + 270, label, "side wall pocket\nlabelled face to wall")
    for name, dy in [("VDD", 80), ("GND", 110), ("SCK", 150), ("WS", 180), ("SD", 210), ("L/R", 240)]:
        pin(330, y0 + dy, name, "r")
ML, MR = 130, 440

# 3V3 to mics (VDD bus x=370, L/R of right mic too)
line([(EX0, 200), (560, 200), (560, 95), (370, 95), (370, MR + 240)], ORANGE)
line([(330, ML + 80), (370, ML + 80)], ORANGE)
line([(330, MR + 80), (370, MR + 80)], ORANGE)
line([(330, MR + 240), (370, MR + 240)], ORANGE)
for y in (ML + 80, MR + 80, MR + 240):
    dot(370, y, ORANGE)
dot(560, 200, ORANGE)
text(465, 88, "3.3 V", 13, "middle", color=ORANGE)

# mic grounds + left mic L/R to ground
line([(330, ML + 110), (395, ML + 110)], BLACK)
ground(395, ML + 110)
line([(330, ML + 240), (395, ML + 240)], BLACK)
ground(395, ML + 240)
line([(330, MR + 110), (395, MR + 110)], BLACK)
ground(395, MR + 110)
text(255, ML + 262, "L/R to GND = left channel", 12, "middle", color="#555")
text(255, MR + 262, "L/R to 3V3 = right channel", 12, "middle", color="#555")

# shared mic I2S bus: SCK x=430 -> GPIO32, WS x=470 -> GPIO33, SD x=510 -> GPIO35
for sig, bx, ey, dy in [("SCK", 430, 320, 150), ("WS", 470, 360, 180), ("SD", 510, 400, 210)]:
    c = SIG[sig]
    line([(330, ML + dy), (bx, ML + dy), (bx, MR + dy), (330, MR + dy)], c)
    line([(bx, ey), (EX0, ey)], c)
    dot(bx, ey, c)
    text(bx + 6, ML + dy - 6, sig, 12, color=c)
# SD pull-down
dot(540, 400, SIG["SD"])
resistor_v(540, 400, 470, SIG["SD"], "100k")
ground(540, 470)

# ESP ground
line([(EX0, 240), (580, 240)], BLACK)
ground(580, 240)
line([(EX1, 240), (850, 240)], BLACK)
ground(850, 240)

# MAX98357A
AX0, AX1, AY0, AY1 = 1000, 1180, 150, 480
box(AX0, AY0, AX1, AY1, "MAX98357A", "bay floor pocket")
for name, y in [("VIN", 200), ("GND", 240), ("LRC", 290), ("BCLK", 330), ("DIN", 370),
                ("GAIN", 410), ("SD", 445)]:
    pin(AX0, y, name, "l")
for name, y in [("OUT +", 270), ("OUT -", 350)]:
    pin(AX1, y, name, "r")
for sig, y in [("LRC", 290), ("BCLK", 330), ("DIN", 370)]:
    line([(EX1, y), (AX0, y)], SIG[sig])
    text(960, y - 6, sig, 12, "middle", color=SIG[sig])
line([(AX0, 240), (975, 240)], BLACK)
ground(975, 240)
text(AX0 - 12, 414, "NC = 9 dB", 12, "end", color="#555")
text(AX0 - 12, 449, "NC = (L+R)/2", 12, "end", color="#555")

# speaker
line([(AX1, 270), (1290, 270), (1290, 285)], "#8c564b")
line([(AX1, 350), (1290, 350), (1290, 335)], "#444")
speaker(1300, 310)
text(1330, 390, "2&quot; 4 ohm 3 W", 14, "middle", "bold")
text(1330, 408, "wires: floor centre hole", 12, "middle", color="#555")
text(1330, 424, "(seal with hot glue)", 12, "middle", color="#555")

# 5 V distribution
RAIL = 900
line([(EX1, 200), (AX0, 200)], RED)
dot(900, 200, RED)
line([(900, 200), (900, RAIL)], RED)

# LED strip
LX0, LX1, LY0, LY1 = 1080, 1440, 600, 720
box(LX0, LY0, LX1, LY1, "WS2812B halo ring", "~39 LEDs / 642 mm, under the cone\nlead enters bay via base wall hole", "#e6f7f9")
for name, y in [("+5V", 630), ("DIN", 660), ("GND", 690)]:
    pin(LX0, y, name, "l")
line([(EX1, 480), (870, 480), (870, 660), (930, 660)], SIG["LED"])
resistor_h(930, 1010, 660, SIG["LED"], "330 ohm")
line([(1010, 660), (LX0, 660)], SIG["LED"])
line([(LX0, 630), (1040, 630), (1040, RAIL)], RED)
dot(1040, RAIL, RED)
line([(LX0, 690), (1060, 690), (1060, 760)], BLACK)
ground(1060, 760)
dot(1040, 800, RED)
line([(1040, 800), (1000, 800), (1000, 815)], RED)
cap_v(1000, 815, 865, "1000 uF 10 V")
ground(1000, 865)

# power input
box(80, 800, 400, 960, "5 V 3 A supply", "barrel jack or USB-C PD trigger\nthrough the aux cable hole", "#fdecea")
line([(400, RAIL), (1040, RAIL)], RED)
text(420, RAIL - 8, "+5 V", 14, color=RED, weight="bold")
line([(400, 940), (430, 940)], BLACK)
ground(430, 940)
pin(400, RAIL, "+5V", "r")
pin(400, 940, "GND", "r")

# notes
notes = [
    "NOTES",
    "1. All GND symbols are one common ground (star it at the ESP32 GND pin).",
    "2. Mics share one I2S bus: SCK/WS/SD paralleled; L/R pin picks the channel. 100k SD pull-down per INMP441 datasheet.",
    "3. LED data is 3.3 V into a 5 V strip: works on most strips with the 330 ohm resistor and short lead.",
    "    If the first LED flickers, add a 74AHCT125 level shifter (5 V powered) between GPIO27 and DIN.",
    "4. Power budget at 5 V: ESP32 ~0.25 A + amp ~0.8 A peaks + 39 LEDs up to 2.3 A (full white) = ~3.4 A.",
    "    Use the 5 V 3 A supply and cap LED brightness ~60%, or USB-C only with LEDs capped ~25%.",
]
add('<line x1="40" y1="995" x2="1460" y2="995" stroke="#ccc"/>')
for i, n in enumerate(notes):
    n = n.replace("    ", "&#160;" * 6)
    text(40, 1025 + 22 * i, n, 15 if i == 0 else 14, weight="bold" if i == 0 else "normal")
add("</svg>")

with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "wiring.svg"), "w") as f:
    f.write("\n".join(out))
print("wrote wiring.svg")
