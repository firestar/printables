# Bulk card scanner + penny-sleever

Feeds up to 250 trading cards, photographs both sides, identifies each card
and looks up its price. It then slides the card into a penny sleeve and sorts
it into one of 3 bins. One print handles standard 63x88 cards (MTG, Pokémon)
and small 59x86 cards (Yu-Gi-Oh): set `CARD` in the CAD and move the slotted
guides.

```
hopper (250, top-feed vacuum pick) -> scan station (glass sandwich, CM3 above + below)
  -> sleeve station (sleeve_pick -> platen vacuum -> lift cup opens mouth
     -> tongues in -> rollers insert -> pawl seats -> tongues out)
  -> servo diverter -> bin 0 / 1 / 2

Pi 5 (cameras, recognition, prices, rules, web UI)
  -- USB serial, newline JSON --> ESP32-S3 (4x TMC2209, servos, N20, pumps/valves, sensors)
```

| Folder | What's in it |
|---|---|
| [`cad/`](cad/README.md) | Parametric CadQuery model with 50 machine parts and a standalone 22-part sleeving test rig (`stl/rig/`), plus viewer, section and BOM |
| [`firmware/`](firmware/README.md) | ESP32-S3 motion controller, native tests, and a simulator for host development, plus the [`PROTOCOL.md`](firmware/PROTOCOL.md) contract |
| [`electronics/WIRING.md`](electronics/WIRING.md) | Pin map (ESP32 + 2x MCP23017), power tree, fusing, e-stop relay, TMC2209 currents, BOM, `wiring.svg` |
| [`host/`](host/README.md) | Pi 5 software for capture, crop/deskew, pHash recognition (Scryfall / Pokémon TCG / YGOPRODeck), OCR fallback, prices, bin rules, inventory DB + Moxfield/TCGplayer CSV, and a web UI with a review queue. It also has a mock MCU + fake camera |

## Build order

1. **Sleeving test rig first** (`cad/stl/rig/`). Penny sleeves stick together
   and vary between brands. Get the rig to about 95% success before building
   the rest. Tuning notes are in `cad/README.md`, and the settings are in
   `firmware/PROTOCOL.md`.
2. Build the feeder + scan station and run `host` in scan-only mode.
3. Add the full frame, the diverter and the bins.

## Known limits

- Throughput is about 5–6 cards/min with the firmware defaults (≈ 10.5 s/card, limited by the
  sleeve insert at 80 mm/s over 238 mm). See [`FEASIBILITY.md`](FEASIBILITY.md) for the cycle sum and
  how to reach ~7–8/min.
- The ESP32 build has never been compiled (PlatformIO was not available).
  Tests ran on the native sequencer + simulator via g++. Pin
  `FastAccelStepper` may need a version bump.
- `sleeve_mouth` is a TCRT5000 under the platen, inside the sleeve's
  footprint. It may not tell "empty sleeve" from "card in sleeve" reliably. If
  it doesn't, move it or swap to a break-beam.
- Placeholders:
  - There is no lid/enclosure yet, so the lid interlock bracket sits on the
    base rail.
  - The 24→12 V buck, 5 V servo buck and MOSFET board are in the BOM but not
    placed in the CAD.
- Switch trip points, `pusher_seat_deg` and `sleeve_pick_ms` are estimates.
  Tune them on the rig.
- If a sleeve trips `sleeve_present` but fails the platen vacuum check, clear
  it by hand before retrying.
- Foil is set per batch, not detected from the image.
- Nothing has been tested on real hardware yet.
