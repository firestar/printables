"""Generate the wiring diagram (wiring.svg) for the card scanner motion controller.

ESP32-S3-DevKitC-1 + 4x TMC2209 + 2x MCP23017 + MOSFET board + DRV8833 + servos + power tree.
Pins match ../firmware/include/config.h.  Run: python3 wiring.py
"""
import os

W, H = 1600, 1580
RED, ORANGE, BLACK, GREY = "#d62728", "#ff7f0e", "#222", "#555"
C_STEP, C_DIR, C_EN, C_UART, C_I2C = "#1f77b4", "#2ca02c", "#9467bd", "#8c564b", "#17becf"

out = []


def add(s):
    out.append(s)


def line(pts, color, w=2.5, dash=None):
    d = " ".join(f"{x},{y}" for x, y in pts)
    extra = f' stroke-dasharray="{dash}"' if dash else ""
    add(f'<polyline points="{d}" fill="none" stroke="{color}" stroke-width="{w}"'
        f' stroke-linejoin="round"{extra}/>')


def dot(x, y, color=BLACK):
    add(f'<circle cx="{x}" cy="{y}" r="4.5" fill="{color}"/>')


def text(x, y, s, size=14, anchor="start", weight="normal", color="#111"):
    add(f'<text x="{x}" y="{y}" font-size="{size}" text-anchor="{anchor}" '
        f'font-weight="{weight}" fill="{color}" font-family="Helvetica, Arial, sans-serif">{s}</text>')


def box(x0, y0, x1, y1, title, sub=None, fill="#f3f3f3"):
    add(f'<rect x="{x0}" y="{y0}" width="{x1 - x0}" height="{y1 - y0}" rx="10" '
        f'fill="{fill}" stroke="#444" stroke-width="2"/>')
    text((x0 + x1) / 2, y0 + 22, title, 16, "middle", "bold")
    if sub:
        for i, s in enumerate(sub.split("\n")):
            text((x0 + x1) / 2, y0 + 40 + 15 * i, s, 12, "middle", color=GREY)


def pin(x, y, name, side):
    """Pin stub on a box edge; side 'l' or 'r' = which edge."""
    add(f'<rect x="{x - 5}" y="{y - 5}" width="10" height="10" fill="#fff" stroke="#444"/>')
    if side == "r":
        text(x - 10, y + 5, name, 13, "end")
    else:
        text(x + 10, y + 5, name, 13, "start")


def label(x, y, s, side, color=GREY):
    """Net label off a pin: a short stub and the destination."""
    dx = 30 if side == "r" else -30
    line([(x, y), (x + dx, y)], color, 2)
    text(x + dx + (6 if side == "r" else -6), y + 5, s, 12, "start" if side == "r" else "end", color=color)


def arrow(x0, y0, x1, y1, color=RED, w=3):
    line([(x0, y0), (x1, y1)], color, w)
    if x1 != x0:
        s = 1 if x1 > x0 else -1
        add(f'<polygon points="{x1},{y1} {x1 - 10 * s},{y1 - 6} {x1 - 10 * s},{y1 + 6}" fill="{color}"/>')
    else:
        s = 1 if y1 > y0 else -1
        add(f'<polygon points="{x1},{y1} {x1 - 6},{y1 - 10 * s} {x1 + 6},{y1 - 10 * s}" fill="{color}"/>')


# ---- layout ---------------------------------------------------------------------
add(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">')
add(f'<rect width="{W}" height="{H}" fill="#fff"/>')
text(40, 40, "Card scanner / sleever / sorter - motion controller wiring", 26, weight="bold")
text(40, 64, "ESP32-S3-DevKitC-1 (host link: native USB to the Raspberry Pi 5)  |  4x TMC2209 (UART addr 0-3)  |"
     "  2x MCP23017  |  9x logic MOSFET  |  DRV8833 + N20  |  3x MG90S  |  pins = firmware/include/config.h", 14,
     color=GREY)

# ESP32
EX0, EX1, EY0, EY1 = 640, 860, 110, 800
box(EX0, EY0, EX1, EY1, "ESP32-S3-DevKitC-1", "N8R8, 3.3 V flash\npowered by the Pi's USB", "#e8f0fe")

# ---- steppers (left) ----
AXES = [("ELEVATOR", "#0  MS1=L MS2=L", "NEMA17 + T8x8 leadscrew", 4, 5),
        ("PICK", "#1  MS1=H MS2=L", "NEMA17 + GT2 20T", 6, 7),
        ("FEED", "#2  MS1=L MS2=H", "NEMA17 + O-ring rollers", 15, 16),
        ("TONGUE", "#3  MS1=H MS2=H", "NEMA17 pancake + GT2", 17, 18)]
TX0, TX1 = 290, 470
EN_BUS, UART_BUS = 540, 575
for i, (name, addr, motor, sp, dp) in enumerate(AXES):
    y0 = 130 + 140 * i
    box(TX0, y0, TX1, y0 + 120, f"TMC2209 {name}", addr)
    for pn, dy in [("STEP", 64), ("DIR", 82), ("EN", 100), ("PDN_UART", 116)]:
        pin(TX1, y0 + dy, pn, "r")
    # STEP / DIR straight to the ESP
    line([(TX1, y0 + 64), (EX0, y0 + 64)], C_STEP)
    line([(TX1, y0 + 82), (EX0, y0 + 82)], C_DIR)
    pin(EX0, y0 + 64, f"GPIO{sp}", "l")
    pin(EX0, y0 + 82, f"GPIO{dp}", "l")
    # EN / UART buses
    line([(TX1, y0 + 100), (EN_BUS, y0 + 100)], C_EN)
    dot(EN_BUS, y0 + 100, C_EN)
    line([(TX1, y0 + 116), (UART_BUS, y0 + 116)], C_UART)
    dot(UART_BUS, y0 + 116, C_UART)
    # motor
    box(70, y0 + 20, 230, y0 + 100, name.title(), motor, "#fff7e6")
    line([(230, y0 + 60), (TX0, y0 + 60)], BLACK, 4)
    text(260, y0 + 52, "A1A2B1B2", 11, "middle", color=GREY)

YEN, YTX, YRX = 700, 730, 760
line([(EN_BUS, 230), (EN_BUS, YEN), (EX0, YEN)], C_EN)
pin(EX0, YEN, "GPIO8 EN", "l")
text(EN_BUS - 6, YEN - 8, "10k to 3V3", 11, "end", color=C_EN)
line([(UART_BUS, 246), (UART_BUS, YRX), (EX0, YRX)], C_UART)
pin(EX0, YRX, "GPIO10 RX", "l")
dot(UART_BUS, YTX, C_UART)
line([(UART_BUS, YTX), (590, YTX)], C_UART)
line([(590, YTX), (595, YTX - 6), (601, YTX + 6), (607, YTX - 6), (613, YTX + 6), (619, YTX - 6),
      (625, YTX), (EX0, YTX)], C_UART)
text(607, YTX - 12, "1k", 11, "middle")
pin(EX0, YTX, "GPIO9 TX", "l")
text(TX0, 700, "VM = 24V_SW via F2 4 A,", 12, color=RED)
text(TX0, 716, "100 uF 35 V at each module.", 12, color=RED)
text(TX0, 736, "VIO = 3V3.  Current: UART", 12, color=GREY)
text(TX0, 752, "(cur_* settings); Vref = fallback", 12, color=GREY)

# ---- I2C expanders (right) ----
SDA_Y, SCL_Y = 140, 165
pin(EX1, SDA_Y, "GPIO11 SDA", "r")
pin(EX1, SCL_Y, "GPIO12 SCL", "r")
MX0, MX1 = 1000, 1170
SDA_X, SCL_X = 920, 945
IN_Y0 = 500
line([(EX1, SDA_Y), (SDA_X, SDA_Y), (SDA_X, IN_Y0 + 20)], C_I2C)
line([(EX1, SCL_Y), (SCL_X, SCL_Y), (SCL_X, IN_Y0 + 45)], C_I2C)
text(932, 128, "4.7k pull-ups", 11, "middle", color=C_I2C)

box(MX0, 110, MX1, 480, "MCP23017 0x20", "outputs")
for pn, dy in [("SDA", 30), ("SCL", 55)]:
    pin(MX0, 110 + dy, pn, "l")
line([(SDA_X, 140), (MX0, 140)], C_I2C)
line([(SCL_X, 165), (MX0, 165)], C_I2C)
dot(SDA_X, 140, C_I2C)
dot(SCL_X, 165, C_I2C)

OUTS = [("GPA0", "Q1", "vacuum pump 12 V"), ("GPA1", "Q2", "valve pick_cup NC"), ("GPA2", "Q3", "valve platen NC"),
        ("GPA3", "Q4", "valve lift_cup NC"), ("GPA4", "Q5", "air pump 12 V"), ("GPA5", "Q6", "valve stack_puff NC"),
        ("GPA6", "Q7", "valve mouth_jet NC")]
QX0, QX1 = 1230, 1330
ROW0, ROW = 196, 24
box(QX0, 110, QX1, 400, "MOSFETs", "IRLB8721\n100R / 10k\nSS34 flyback", "#fdecea")
for i, (mp, q, load) in enumerate(OUTS):
    y = ROW0 + ROW * i
    pin(MX1, y, mp, "r")
    line([(MX1, y), (QX0, y)], ORANGE)
    text(QX0 + 50, y + 5, q, 13, "middle", "bold")
    line([(QX1, y), (1350, y)], ORANGE)
    text(1356, y + 5, load, 12)
for i, (gp, q, load) in enumerate([("GPIO39", "Q8", "LED ring top 12 V"), ("GPIO40", "Q9", "LED ring bottom 12 V")]):
    y = ROW0 + ROW * (7 + i)
    line([(QX0 - 30, y), (QX0, y)], ORANGE)
    text(QX0 - 34, y + 4, gp + " PWM", 11, "end", color=ORANGE)
    text(QX0 + 50, y + 5, q, 13, "middle", "bold")
    line([(QX1, y), (1350, y)], ORANGE)
    text(1356, y + 5, load, 12)
# sleeve_pick: DRV8833 channel A from two expander outputs (no PWM: run until sleeve_present, 1/1 = brake)
box(QX0, 410, QX1, 480, "DRV8833", "VM 5V_SERVO", "#fdecea")
for mp, pn, y in [("GPA7", "AIN1", 448), ("GPB0", "AIN2", 468)]:
    pin(MX1, y, mp, "r")
    line([(MX1, y), (QX0, y)], ORANGE)
    text(QX0 + 8, y + 4, pn, 11)
line([(QX1, 458), (1350, 458)], BLACK, 4)
text(1356, 452, "N20 6 V sleeve_pick", 12)
text(1356, 468, "fwd 1/0, brake 1/1", 11, color=GREY)

box(MX0, IN_Y0, MX1, 790, "MCP23017 0x21", "")
for pn, dy in [("SDA", 20), ("SCL", 45)]:
    pin(MX0, IN_Y0 + dy, pn, "l")
line([(SDA_X, IN_Y0 + 20), (MX0, IN_Y0 + 20)], C_I2C)
line([(SCL_X, IN_Y0 + 45), (MX0, IN_Y0 + 45)], C_I2C)
text((MX0 + MX1) / 2, IN_Y0 + 62, "inputs, pull-ups on", 12, "middle", color=GREY)
INS = [("GPA0", "stack_top  TCRT5000, LOW=card"), ("GPA1", "exit  TCRT5000, LOW=card"),
       ("GPA2", "elev_home  NC switch"), ("GPA3", "elev_limit  NC switch"), ("GPA4", "pick_home  NC switch"),
       ("GPA5", "tongue_home  NC switch"), ("GPA6", "lid  NC (2nd contact)"), ("GPB0", "mag_low  TCRT5000"),
       ("GPB1", "mag_empty  TCRT5000"), ("GPB2", "sleeve_present  TCRT5000, LOW=sleeve")]
for i, (mp, s) in enumerate(INS):
    y = IN_Y0 + 92 + 20 * i
    pin(MX1, y, mp, "r")
    label(MX1, y, s, "r", C_I2C)

# ---- other ESP pins: the destination is written inside the board outline ----
RIGHT = [(250, "lift servo  GPIO13"), (275, "pusher servo  GPIO14"), (300, "diverter servo  GPIO21"),
         (390, "LED top Q8  GPIO39"), (415, "LED bottom Q9  GPIO40"), (450, "vacuum 10k/20k  GPIO1"),
         (540, "scan_stop NO  GPIO41"), (565, "sleeve_mouth TCRT  GPIO42"), (590, "double_feed  GPIO2"),
         (660, "E-stop NC2  GPIO47"), (720, "3V3 out"), (745, "GND -> star"), (775, "USB native -> Pi 5")]
for y, s in RIGHT:
    pin(EX1, y, s, "r")
    line([(EX1, y), (885, y)], GREY, 2)

# servos + light rings
box(1000, 800, 1180, 880, "3x MG90S servos", "lift / pusher / diverter\n5V_SERVO, 470 uF", "#fff7e6")
box(1230, 800, 1450, 880, "2x 12 V COB LED rings", "top / bottom scan light\nQ8 / Q9, PWM 20 kHz", "#fff7e6")

# ---- power tree (bottom) ----
PY = 1020
text(40, PY - 40, "POWER", 18, weight="bold")
box(40, PY, 230, PY + 80, "24 V 6.5 A PSU", "Mean Well LRS-150-24")
arrow(230, PY + 40, 300, PY + 40)
box(300, PY + 15, 380, PY + 65, "F0 8A")
arrow(380, PY + 40, 440, PY + 40)
text(445, PY + 30, "24V_ALWAYS", 13, weight="bold", color=RED)
line([(440, PY + 40), (520, PY + 40)], RED, 3)
# Pi branch
line([(470, PY + 40), (470, PY - 40), (520, PY - 40)], RED, 3)
box(520, PY - 65, 600, PY - 15, "F1 3A")
arrow(600, PY - 40, 650, PY - 40)
box(650, PY - 70, 830, PY - 10, "5 V 5 A buck", "Pololu D36V50F5")
arrow(830, PY - 40, 880, PY - 40)
box(880, PY - 70, 1040, PY - 10, "Raspberry Pi 5", "PSU_MAX_CURRENT=5000")
arrow(1040, PY - 40, 1100, PY - 40, C_STEP)
text(1106, PY - 35, "USB -> ESP32-S3 (always on)", 12, color=C_STEP)
# K1 + safety chain
box(520, PY + 10, 640, PY + 70, "K1 relay", "24 V coil")
chain_y = PY + 120
line([(470, PY + 40), (470, chain_y), (540, chain_y)], RED, 2)
box(540, chain_y - 18, 660, chain_y + 18, "E-stop NC1")
line([(660, chain_y), (690, chain_y)], RED, 2)
box(690, chain_y - 18, 790, chain_y + 18, "Lid NC")
line([(790, chain_y), (820, chain_y), (820, PY + 90), (580, PY + 90), (580, PY + 70)], RED, 2)
text(830, chain_y + 5, "coil loop (1N4007 across the coil)", 12, color=GREY)
arrow(640, PY + 40, 700, PY + 40)
text(706, PY + 30, "24V_SW", 13, weight="bold", color=RED)
SW_X = 790
line([(700, PY + 40), (SW_X, PY + 40)], RED, 3)
for i, (fuse, dest, sub) in enumerate([("F2 4A", "TMC2209 VM x4", "steppers"),
                                       ("F3 4A", "24->12 V 8 A buck", "12V_SW -> MOSFET board"),
                                       ("F4 1A", "5 V 3 A servo buck", "5V_SERVO -> servos, DRV8833")]):
    y = PY - 10 + 60 * i + 50
    line([(SW_X, PY + 40), (SW_X, y), (900, y)], RED, 3)
    box(900, y - 22, 980, y + 22, fuse)
    arrow(980, y, 1030, y)
    box(1030, y - 25, 1250, y + 25, dest, sub)
dot(SW_X, PY + 40, RED)
text(1280, PY + 50, "E-stop / lid open: K1 drops,", 12, color=GREY)
text(1280, PY + 66, "24V_SW off (motors, pumps,", 12, color=GREY)
text(1280, PY + 82, "valves, servos, N20). Pi + ESP32", 12, color=GREY)
text(1280, PY + 98, "stay up and report it.", 12, color=GREY)

# notes
notes = [
    "NOTES",
    "1. One star ground at the PSU -V. Separate returns from: TMC power GND, 12 V buck minus (MOSFET sources), servo buck minus,"
    " Pi buck minus. Logic GND joins with one wire.",
    "2. Load currents never return through the ESP32, the USB cable or sensor wiring. MOSFET board gets one thin logic-GND wire"
    " for the gate reference.",
    "3. Every sensor module runs from 3V3 (outputs stay below 3.3 V). The vacuum sensor needs 5 V: the 10k/20k divider scales"
    " 4.5 V to 3.0 V.",
    "4. Endstops and the lid are normally closed to GND: a cut wire reads as 'at the switch' / 'lid open', which fails safe.",
    "5. GPIO8 EN has a 10k pull-up and every MOSFET gate a 10k pull-down: during reset or flashing, drivers are off and"
    " valves closed. DRV8833 inputs have internal pull-downs: the N20 coasts.",
    "6. Unused: GPIO0/3/45/46 (strapping), 19/20 (USB), 43/44 (UART0), 26-37 (flash/PSRAM), 38/48 (RGB LED).",
    "7. Air: one pump tees to the hopper puff and the sleeve-mouth jet. Each branch has its own NC valve downstream of the"
    " pump: Q6 stack_puff, Q7 mouth_jet.",
]
add(f'<line x1="40" y1="{H - 230}" x2="{W - 40}" y2="{H - 230}" stroke="#ccc"/>')
for i, n in enumerate(notes):
    text(40, H - 200 + 24 * i, n, 15 if i == 0 else 13, weight="bold" if i == 0 else "normal")
add("</svg>")

with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "wiring.svg"), "w") as f:
    f.write("\n".join(out))
print("wrote wiring.svg")
