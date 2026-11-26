# Speaker interface board: silkscreen labels and parts

The boards show references only. This document gives each label's value, what the part does and which
way it goes. It applies to both the 2-layer and 4-layer boards, which share the same parts, positions and
labels. All silkscreen text is at least 0.8 mm tall with 0.15 mm lines, to meet PCBWay's published
minimum. Ordering details are in `pcb/BOM.csv` and `pcb_2layer/BOM.csv`.
**Assembly drawing:** [`assembly.png`](assembly.png) (print [`assembly.pdf`](assembly.pdf)) shows where every part goes on
the real layout, which way round, and the marking on each part. Regenerate it with
`PYTHONPATH=.pydeps python3 smart_speaker/pcb_2layer/assembly_drawing.py` from the repo root.

## Telling the small parts apart

| Part | Marking on the part | How to check |
|---|---|---|
| R1, 330 ohm | `331` (5%) or `3300` (1%) | Meter: 330 ohm |
| R2, 100 kohm | `104` (5%) or `1003` (1%) | Meter: 100 kohm |
| R3, R4, 100 ohm | `101` (5%) or `1000` (1%) | Meter: 100 ohm |
| C2, 10 uF | None: ceramic capacitors are not marked | Keep it in its labelled tape; fit it first, alone; a capacitance meter reads about 10 uF |
| C3 to C6, 100 nF | None | Same tape-strip rule; reads about 0.1 uF |

Resistor codes: with 3 digits, the first two are the value and the third is the number of zeros; with 4 digits,
the first three are the value and the fourth is the number of zeros. All resistors and ceramic capacitors fit
either way round.

## Parts to solder

| Label | Value | Part | Package | What it does | Orientation |
|---|---|---|---|---|---|
| C1 | 1000 uF, 10 V | General-purpose electrolytic, ESR 0.1 ohm or more | Radial, 10 x 12.5 mm, 5 mm lead spacing, 13.5 mm tall at most | Bulk supply for the LED strip | **Polarized:** positive lead in the square pad marked `+` |
| C2 | 10 uF, 10 V or higher | X5R ceramic | 0805 | Amp port decoupling | Either way |
| C3 | 100 nF | Ceramic | 0805 | Amp port decoupling | Either way |
| C4 | 100 nF | Ceramic | 0805 | MIC L port decoupling | Either way |
| C5 | 100 nF | Ceramic | 0805 | MIC R port decoupling | Either way |
| C6 | 100 nF | Ceramic | 0805 | Level shifter decoupling | Either way |
| R1 | 330 ohm | Resistor | 0805 | Series resistor on LED data | Either way |
| R2 | 100 kohm | Resistor | 0805 | Mic SD pull-down | Either way |
| R3 | 100 ohm | Resistor | 0805 | Damps mic WS | Either way |
| R4 | 100 ohm | Resistor | 0805 | Damps mic SCK | Either way |
| Q1 | AO3401A | P-channel MOSFET | SOT-23 | Reverse-polarity protection on the 5 V input | Fits one way: drain alone on the right |
| U1 | SN74AHCT1G125DBVR | Level shifter | SOT-23-5 | Lifts LED data from 3.3 V to 5 V | **Match the chip's pin 1 dot to the `1` on the board**, top left of the part |
| JP1 | Solder bridge | No part | 3 pads, numbered 1, 2, 3 | Selects the LED data path | **Must be bridged:** 2-3 uses the shifter (use this); 1-2 bypasses it |

## Connectors and modules

| Label | Ref in files | Connects | Pins, from the square pad | Notes |
|---|---|---|---|---|
| 5V IN | J7 | 2 wires from the barrel connector, up to 18 AWG | GND, +5V | Supply must hold at least 4.9 V under load, 3 A |
| AMP (5 V) | J5 | 5-pin JST SM pigtail to the MAX98357A | GND, 5V, LRC, BCK, DIN | Leave GAIN and SD on the amp unconnected |
| LED (5 V) | J6 | 5-pin JST SM pigtail to the LED strip | GND, 5V, DIN, NC, NC | Cut off the strip's 3-pin plug; NC pins are unused |
| MIC L (mic only: 3.3 V) | J3 | 5-pin JST SM pigtail | GND, 3V3, SCK, WS, SD | Jumper the mic's L/R pin to GND at the mic |
| MIC R (mic only: 3.3 V) | J4 | 5-pin JST SM pigtail | GND, 3V3, SCK, WS, SD | Jumper the mic's L/R pin to VDD at the mic |
| VIN / 3V3 rows | J1, J2 | 2 x 15-pin 2.54 mm female sockets, 8.5 mm tall, for the ESP32 | From the USB end, see below | Socket height sets how the board fits |

**The 5-pin ports are interchangeable.** A mic plugged into AMP or LED gets 5 V on its 3.3 V pin and will
probably die, so mark every cable.

**The speaker** wires straight to the amp's screw terminal and isn't on this board.

## ESP32 sockets

Fit the ESP32 module side up, with its USB connector at the `USB END >>` side. **It also fits turned 180
degrees, which would misconnect power.**

| Row | Pins, from the USB end |
|---|---|
| J1, marked VIN | **VIN**, **GND**, 13, 12, 14, **27**, **26**, **25**, **33**, **32**, **35**, 34, 39, 36, EN |
| J2, marked 3V3 | **3V3**, **GND**, 15, 2, 4, 16, 17, 5, 18, 19, 21, 3, 1, **22**, 23 |

Bold pins are used. GPIO32 and GPIO33 go through R4 and R3 to the mics, GPIO35 is mic data, GPIO25, GPIO26
and GPIO22 go to the amp, and GPIO27 is LED data.

## Other board markings

| Marking | Meaning |
|---|---|
| `USB END >>` | The ESP32's USB connector points this way |
| `ESP32 faces up` | Module side up, away from the board |
| `1 2 3` by JP1 | JP1's pad numbers |
| `1` by U1 | U1's pin 1 corner |
| `+` by C1 | C1's positive lead |
| `Speaker interface`, `2-layer v1` or `4-layer v1` | Board name and which version it is |

Screw holes take 4 x M2.5 x 6 self-tapping screws into the base bosses.
