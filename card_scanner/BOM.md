# Card scanner + penny-sleever — consolidated BOM

Prices checked **2026-11-01**. Buyer is US-based; AliExpress is the default source, with
official-reseller exceptions for the Raspberry Pi 5 and Camera Module 3, and a few
Amazon exceptions noted below for counterfeit-prone parts (microSD, Mean Well PSU, 3M VHB
tape). Full line-by-line detail, including a `spec_source` column naming the doc each spec
came from (so a later spec change is a one-line edit, not a re-derivation) and `phase1`
/ `scan_only` flags (1 = included in that subtotal), is in [`BOM.csv`](BOM.csv).

Only **3 of 75 lines are a live, confirmed price** (PiShop.us — fetched today): Raspberry
Pi 5 ($175.00), Camera Module 3 ($29.25 ea), Raspberry Pi Active Cooler ($12.95). Web
search was rate-limited for this entire session (DuckDuckGo HTTP 202) and AliExpress
listing pages render their prices client-side (not present in the static HTML a headless
fetch gets), so **the other 72 lines are typical/market-price estimates ("est"), not
verified live listings.** They're flagged individually in `BOM.csv`'s `confidence` column
and should be re-checked against live AliExpress listings before ordering.

## Filament

Computed from the actual exported STLs (`card_scanner/filament_estimate.py` — a small
pure-numpy binary-STL volume parser, since neither `numpy-stl` nor `trimesh` nor a
`.pydeps` dir exist in this repo/environment; numpy itself is available system-wide),
using PETG density 1.27 g/cm³, 100% infill for `roller_hub` (per the cad README), and
45% effective density for everything else (4 walls / 25% gyroid, per the task's own
approximation):

| | grams | kg |
|---|---|---|
| Black PETG (everything except LED frames) | 1928.8 g | 1.93 kg |
| White PETG (`led_frame_top` + `led_frame_bot`) | 74.7 g | 0.07 kg |
| **Grand total** | **2003.5 g** | **2.00 kg** |
| Phase-1 rig filament (rig-only extras + shared sleeve-station parts) | 420.0 g | 0.42 kg |

Buy margin for failed prints/purge/support waste: 3× 1kg black spools (full build), 1×
1kg white spool (75g needed, one spool vastly overcovers it — same spool is handy for any
other white part). A scan-only build (no sleeve station) needs ~1.56 kg black — 2 spools
instead of 3, saving one ~$14.90 spool (not reflected in the scan-only subtotal below,
which conservatively keeps all 3).

## Category subtotals (full build)

| Category | Subtotal |
|---|---|
| Compute/host | $280.23 |
| Motion (steppers, drivers, belts, rods, bearings) | $117.00 |
| Power (PSU, bucks, MOSFETs, fusing, passives) | $92.09 |
| Structural (2020 extrusion) | $90.00 |
| Pneumatics (pumps, valves, manifold, tubing) | $74.00 |
| Filament | $60.60 |
| Consumables (wire, connectors, heat-shrink, sleeves, VHB) | $55.39 |
| Mechanical (bearings, O-rings, springs, fasteners) | $51.60 |
| Optics (glass, polarizer, diffuser, LED strip, shim) | $44.50 |
| Sensors & switches | $30.70 |
| Actuators (servos, N20, DRV8833) | $20.50 |

## Totals

| | Total |
|---|---|
| **GRAND TOTAL (full build: scanner + sleever + sorter)** | **$916.61** |
| **PHASE 1 (sleeving-rig-only bench test)** | **$304.59** |
| **SCAN-ONLY (no sleever)** | **$873.11** |

**Phase 1** = every part in `cad/stl/rig/` (filament) + the actuators/sensors/drivers the
rig actually needs (tongue stepper + its TMC2209, lift + pusher servos, N20 sleeve-pick
motor + DRV8833, vacuum pump, air pump, 3 of 5 solenoid valves, vacuum manifold + pressure
sensor, lift-cup suction cup, tubing/fittings, both MCP23017s, the tongue-home switch, 4
of 6 TCRT5000 modules) + an ESP32-S3 + the main 24V PSU + its 12V/5V-servo bucks + MOSFET
board passives + basic wiring consumables + heat-set inserts. It deliberately excludes the
Pi 5/cameras/microSD (not needed for a bare motion-sequencer bench test per the task spec),
the frame extrusion (the rig stands on printed `rig_foot` legs, no 2020 needed), and the
mains-safety chain (IEC inlet, relay, e-stop, lid interlock — a bench test runs off a lab
supply, not the full enclosure). Some shared packs (e.g. the TMC2209 4-pack, the MG90S
4-pack, all 5 solenoid valves) are costed at full pack price even though the rig only uses
part of the pack — this is conservative (slightly overstates phase 1) since those packs
get reused in the full build anyway.

**Scan-only** = full build minus the sleeve-station-specific lines (tongue motor, N20 +
wheels + DRV8833, 10mm lift-cup suction cup, 0.3mm stainless shim, penny sleeves) — i.e.
scan + recognize + sort into bins, without sleeving. This is a conservative upper-bound
estimate: it still counts full packs/costs for systems shared with sleeving (all 5
solenoid valves, the vacuum manifold/sensor, the full TMC2209 and MG90S packs, all 3
filament spools) even though a scan-only build could trim a couple of those line items
further (e.g. 2 valves instead of 5, 2 filament spools instead of 3).

## Top 5 cost drivers

1. Raspberry Pi 5 (8GB) — $175.00 — PiShop.us, confirmed
2. 2020 aluminium extrusion, cut to length (6.75m, 18 pieces) — $90.00 — AliExpress, est
3. Raspberry Pi Camera Module 3 ×2 — $58.50 — PiShop.us, confirmed
4. PETG filament, black, 3×1kg — $44.70 — AliExpress, est
5. Mean Well LRS-150-24 PSU — $32.99 — Amazon, est (counterfeit risk on AliExpress for this part)

## Tariff / shipping caveats — US, late 2026

- **De minimis is gone.** The blanket duty-free treatment for low-value (<$800) parcels
  from China was eliminated in 2025 under the IEEPA tariff orders; as of this writing,
  essentially every direct-from-China AliExpress parcel into the US is subject to duty —
  either an ad-valorem tariff on the declared value or a flat per-item/per-pound fee for
  postal shipments, depending on the carrier and how the shipment is routed. This BOM's
  AliExpress line prices are **sale prices only** and do **not** include duty, which can
  realistically add another 20–50%+ on top depending on HTS classification and whatever
  the US/China tariff schedule looks like by the time of ordering.
- Some AliExpress "Choice"-tagged listings pre-collect/pre-pay estimated import charges at
  checkout and ship from a US-bonded warehouse — those are worth preferring over
  direct-from-China listings for this project, even at a slightly higher sticker price,
  since the all-in cost is often lower and more predictable.
- Consolidating the ~45 AliExpress lines into as few seller orders/shipments as possible
  (most AliExpress sellers carry several of these generic modules) reduces the number of
  separate dutiable parcels and per-parcel handling fees.
- Budget an extra **$150–300** on top of the $916.61 grand total for duties/fees given the
  above — treated as a range because the actual amount depends on the HTS codes assigned
  and the tariff schedule in effect when each parcel clears customs.
- PiShop.us/Amazon orders ship domestically (already in the US) and aren't affected by any
  of this.

## Spec reconciliation (after FEASIBILITY.md)

- Scan lights: plain 12 V white LED strip (non-addressable) on PWM MOSFETs (Q8/Q9). It fits the
  rectangular LED-frame channel. `cad/README.md` and `WIRING.md` now both say this.
- Valves: 5 total. 3x **3/2-way** NC for the vacuum cups (a 2-way NC valve traps vacuum and
  the cup never releases) + 2x 2-way NC for the air branches (stack_puff, mouth_jet).
- PSU: Mean Well LRS-150-24 (6.5 A, 159x97x30), not LRS-100-24 (peak load 5.7 A).
- Sleeves: Ultra Pro-class penny, 66.7x92.1 mm, 45 µm per ply (gate set to 0.14 mm).
