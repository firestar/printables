# Round speaker interface board

A 4-layer, 54.5 x 62 mm carrier for the electronics bay. The ESP32 devkit plugs into two
sockets; the amp and both mics stay on their own boards and connect by cable. Pin
assignments match `../firmware/include/config.h`, so the firmware does not change.

**ESP32 footprint:** the row spacing (25.4 mm) and pin 1 position (9.6 mm from the USB-end
board edge) were scaled off the listing's photo, then confirmed by test-fitting a real devkit
in the printed plate from `esp32_fit_gauge.py`. The plate has loose 1.5 mm holes, so it
confirms the layout but not small errors.

## Ports

Pin 1 has the square pad. Labels are on the silkscreen.

| Port | Ref | Connector | Pin 1 → 5 |
|---|---|---|---|
| MIC L | J3 | 5-pin JST SM pigtail, soldered | GND, 3V3, SCK, WS, SD |
| MIC R | J4 | 5-pin JST SM pigtail, soldered | GND, 3V3, SCK, WS, SD |
| AMP | J5 | 5-pin JST SM pigtail, soldered | GND, 5V, LRC, BCK, DIN |
| LED | J6 | 5-pin JST SM pigtail, soldered | GND, 5V, DIN, unused, unused |
| 5V IN | J7 | 2 wires from the barrel connector, up to 18 AWG | GND, +5V |

- **Speaker:** wires straight to the amp's screw terminal, with your 2-pin JST ZH inline if
  you want a plug. It is not on this board.
- **Mic L/R pin:** there is no wire for it. Jumper it at each mic: GND on the left mic, VDD
  on the right mic.
- **Amp:** GAIN and SD stay unconnected.
- **LED strip:** cut off its 3-pin plug. Thread the wires through the wall slot first, then
  fit the 5-pin connector, which won't fit through the 12 x 7 mm slot.

**The 5-pin connectors are interchangeable.** A mic plugged into AMP or LED gets 5 V on its
3.3 V pin and will probably die. Mark every cable before first power-up.

## Assembly

1. Solder Q1, U1, R1, R2 and C2-C6, then C1 (`+` is marked; the square pad is positive).
2. **Bridge JP1, or the LEDs get no data.** 2-3 uses the level shifter (fit by default);
   1-2 bypasses it.
3. Solder the two 15-pin sockets on top, keeping them square.
4. For each cable, pass the wires through the slot, over the bar, into the holes from the
   top, and solder underneath. The slot takes the pull, not the joints.
5. Before plugging in the ESP32, power up from the 5 V input and check: 5 V at J5 pin 2,
   J6 pin 2 and J1 pin 1; no short on J2 pin 1 (3V3).
6. Fit the board with 4 x M2.5 x 6 self-tapping screws into the new base bosses.
7. Plug in the ESP32 with the USB connector at the `USB END >>` side, module up. **Turned
   180° it still fits, and that would misconnect power.**

## Fit

The sockets are 8.5 mm tall, so the board top sits at z 9 with the ESP32 on its existing
20 mm ledges. `../round_sub/base.stl` now has 4 screw bosses for it, so **the base needs
reprinting**. `check_fit.py` in `../round_sub/` passes with the board, sockets and C1 modeled.

## Layers

| Layer | Use |
|---|---|
| F.Cu | Signals, parts, GND fill |
| In1.Cu | Solid GND |
| In2.Cu | 5 V plane |
| B.Cu | Signals, GND fill |

3V3 is a routed trace rather than the small plane island first planned, because the mics
draw so little. Fab settings: 1.6 mm, 1 oz outer, minimum 0.2 mm track/gap, 0.3 mm via
drill. Give the fab `interface_board-gerbers.zip`.

## Files

| File | What |
|---|---|
| `make_pcb.py` | Parts, nets, placement and the router; generates the board |
| `export.sh` | Rebuilds everything using KiCad 9 in Docker |
| `check_board.py` | Checks the saved board and Gerbers against the pin map |
| `check_gerbers.py` | Rebuilds connections from the Gerbers with an independent parser |
| `trace_circuits.py` | Lists every circuit traced from the Gerber copper |
| `interface_board.kicad_pcb` / `.kicad_pro` | KiCad project; opens in KiCad 9 |
| `netlist.csv` | Every connection, in place of a schematic |
| `BOM.csv` | Parts list |
| `drc.rpt` | KiCad's design-rule report |
| `render/` | Top and bottom pictures, plus each copper layer |

There is no KiCad schematic file: the board is generated straight from the net tables in
`make_pcb.py`. KiCad's board-versus-schematic check therefore doesn't apply, and
`check_board.py` does that job instead. Editing the board by hand in KiCad means the next
`make_pcb.py` run overwrites the edits.

## Requirements from the 2-layer simulations

The same circuit was simulated in `../pcb_2layer/sim/`, and the planes here have less resistance than
the 2-layer copper. Those results apply: supply at least 4.9 V under load, C1 general purpose with
ESR 0.1 ohm or more, JP1 on 2-3, and R3/R4 fitted. The 4-layer copper itself was not simulated.

## Not proven yet

- No board has been built, so none of this has been tested electrically.
- Q1 passes the 3.4 A peak but has only modest copper for cooling; it dissipates about
  0.6 W at that peak, and far less at the typical 0.4 A. Check its temperature at full LED
  brightness.
- Mic SCK, WS and SD run side by side for about 40 mm over the ground plane. This should be
  fine at about 1 MHz, but listen for noise on the mics.
- BOM prices are rough estimates, not live quotes.
