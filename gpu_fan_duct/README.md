# 120 mm fan -> 2 x Tesla V100 PCIe duct

One-piece duct that pushes air from one 120 mm fan into the tail ends of two
passive Tesla V100 PCIe cards in adjacent slots (40.64 mm pitch). Open-air rig.

- Fan flange: 120 mm, 105 mm hole spacing, 4.5 mm holes. Fits 25 and 38 mm fans.
- Sleeve: slides 20 mm over both card tails with 1 mm clearance per side. Line
  it with ~1.5 mm foam tape so it seals and grips.
- A splitter gives each card half the air. It widens into a 4.84 mm fin
  that fills the 5.64 mm gap between the cards for the full sleeve depth, so
  air can't bypass the heatsinks through the gap.
- Card size defaults (spec): 111.2 mm tall, 35 mm cooler, 40.64 mm pitch.
  Measure your tails and change `CARD_H` / `CARD_T` / `PITCH` at the top of
  `cad/gpu_duct.py` if they differ.

## Print

`cad/stl/duct.stl`: PETG (the card tails get hot), flange down, no supports,
0.2 mm layers, 3 walls. Footprint 120 x 120 mm, 128 mm tall.

Fasten the fan with 4 x M4 x 35 bolts and nuts through the fan and flange, or
use self-tapping fan screws from the duct side.

## Airflow

A standard 120 x 25 fan (about 2 mmH2O) won't keep two 250 W V100s from
throttling under sustained full load. For that, use a 120 x 38 high-pressure
server fan; it uses the same screw holes.

## Build

```
cd cad
PYTHONPATH=../../.pydeps python3 gpu_duct.py   # stl/, preview/, checks
python3 -m http.server 8091                    # then open viewer.html
```
