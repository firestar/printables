# Round speaker interface board, 2-layer

The 2-layer version of [`../pcb/`](../pcb/README.md). Circuit, ports, pin map, part positions,
outline, slots and mounting holes are the same, so the ports table, assembly steps, ESP32 fit
test and base all carry over from that README. **JP1 still has to be bridged.**

## What differs from the 4-layer board

| Item | 2-layer |
|---|---|
| GND | Copper fill on top and bottom, joined by 58 stitching vias |
| 5 V | 1 mm trunk on both layers through the gap beside the ESP32 sockets, 1.2 mm to the LED port and C1, 0.5 mm branches to the amp, ESP32 and small parts |
| 3V3 and signals | Routed on top and bottom |

## PCBWay settings

| Field | Value |
|---|---|
| Size | 62.1 x 54.6 mm |
| Layers | 2 |
| Material | FR-4 |
| Thickness | 1.6 mm |
| Min track/spacing | 6/6 mil |
| Min hole size | 0.3 mm |
| Finished copper | 1 oz |
| Via process | Tented |
| Surface finish | HASL lead free |

Upload `interface_board_2l-gerbers.zip`.

## Estimated power loss (LED strip at 2.3 A, 3.4 A total)

Simulated by `check_power.py` through the real copper in the Gerbers, assuming 1 oz, not measured:

- **5 V to the LED port:** 33 mV. **GND return:** 8 mV. **Total:** about 41 mV.
- **Highest current away from pads, averaged over 1 mm of copper:** 2.1 A/mm on 5 V and 0.54 A/mm
  on GND, against the 3 A/mm limit used (about 20 C rise for 1 oz outer copper).

## Q1 temperature

From the AO3401A datasheet (under 60 mOhm at 4.5 V, 125 C/W maximum steady state to ambient, 150 C
maximum junction), allowing for resistance rising with heat. These are estimates for a 40 C bay:

| Load | Q1 loss | Junction |
|---|---|---|
| 2.55 A, firmware LED cap of about 60% with the amp at peak | about 0.5 W | about 100 C |
| 3 A, the supply limit | about 0.7 W | about 125 C |

That is within rating but hot. Typical use is about 0.4 A and stays near ambient. The 2.5 mm drain
trace helps; measure Q1 on a built board at full brightness before trusting these figures.

## Requirements found by simulation

`sim/run_sim.py` runs ngspice with behavioural models for parts with no vendor model here:

- **Supply:** 4.9 V or higher under load, 3 A, with total supply and cable resistance of about 0.15 ohm or
  less. At 4.75 V with the LEDs at the firmware cap, 3V3 sags to about 2.98 V, under the ESP32 minimum.
- **C1:** general purpose, ESR 0.1 ohm or more. Plug-in current peaks at 14 to 22 A; a very low-ESR
  capacitor with short, thick wires reached 28 A, above Q1's 27 A pulse rating.
- **JP1:** use 2-3. Bypassing gives a 3.3 V data high against the strip's 3.5 V threshold.
- **R3, R4:** these 100 ohm resistors bring SCK interference on mic SD inside logic limits.

## Rebuilding and checking

```
PYTHONPATH=../../.pydeps bash export.sh       # needs Docker, run in this folder
python3 check_board.py                        # run in this folder
python3 sim/run_sim.py                        # run in this folder, needs Docker
PYTHONPATH=.pydeps python3 -W ignore smart_speaker/pcb_2layer/trace_circuits.py   # from the repo root
PYTHONPATH=.pydeps python3 -W ignore smart_speaker/pcb_2layer/check_power.py   # from the repo root
PYTHONPATH=.pydeps python3 smart_speaker/pcb_2layer/check_gerbers.py   # run from the repo root
```

## Not proven yet

- No board has been built, so none of this has been tested electrically.
- Mic noise: the ground fill has traces through it, which is weaker than the 4-layer board's
  solid plane. Listen for noise, especially with the LEDs animating.
