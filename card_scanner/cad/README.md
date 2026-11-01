# Card scanner + penny sleever + 3-bin sorter – CAD

Automated bulk trading-card pipeline: 250-card top-feed hopper → O-ring roller transport → dual
Raspberry Pi Camera Module 3 scan station (cross-polarized, card on AR glass) → automatic penny
sleeving (vacuum platen, lift cup, duck-bill tongues, pawl pusher) → servo diverter → 3 gravity bins.
2020 aluminium frame with printed brackets; everything printed in PETG on a Bambu P1S (256³).

- `card_scanner.py` – all geometry, interference + print checks, STL export (parameters at the top).
  Run: `PYTHONPATH=../../.pydeps python3 card_scanner.py`
- `section.py` – writes `preview/section_2d.png` (side cut along the card path, top view at the track
  plane, sleeve-station zoom, cross cut through the scan station).
- `viewer.html` – three.js viewer for `preview/` (serve this folder over http). Views iso / side / top /
  hopper / scan / sleeve / diverter, section y = 0 or x = camera axis, station filter, frame / hardware /
  hood toggles. URL params: `view=`, `section=`, `station=`, `frame=0`, `comps=0`, `hood=0`, `hideui=1`.
- `stl/` – every machine part in print orientation. **`stl/rig/` – the phase-1 sleeving test rig set.**
- `preview/` – assembled printed parts, hardware stand-ins (motors, servos, shafts, glass, boards …),
  frame extrusions, `manifest.json`.

The script checks every part is one watertight body that fits the bed, and that no two assembled
parts (or a part and a hardware stand-in) intersect in the shown pose (tongues inserted, pusher at
start). Overhang (> 45°) area is reported per part – see the "Support" column.

## Card size switch

`CARD = "standard"` (MTG / Pokémon 63 × 88, Ultra Pro penny sleeve 66.7 × 92.1) or `"small"` (Yu-Gi-Oh 59 × 86, sleeve
62 × 89). Fixed geometry is sized for the larger card; everything that touches the card edges is
**slotted** so one print fits both:

| Adjustable part | How | Range |
|---|---|---|
| `hopper_guide` ×2 | 2 × M3 slots in the foot, inserts at fixed y = ±43.25 | inner face ±30.25 … ±32.25 |
| `guide_rail_40/18` ×6 | 2 × M3 slots, track inserts at ±43.25 | same |
| `sleeve_fence` | 2 × M3 slots on the platen ledges | sleeve edge −31.5 … −33.5 |
| `sleeve_gate` | vertical slots, set the 0.14 mm gap (1.5 × sleeve thickness) with a feeler gauge | gap 0.1 … 0.5 |

Re-running with `CARD = "small"` re-exports the guides/fence already shifted (only for convenience –
the standard prints adjust to small with the slots). Hopper back/front walls and the magazine end
wall are fixed: small cards/sleeves get 2 mm of length slack (harmless – they are aligned on the
feed side / mouth side).

## Key dimensions (world x along the card path, z = 0 = top of the 2020 base frame)

| Station | x (mm) | Notes |
|---|---|---|
| Hopper stack centre | 0 | 250 cards = 80 mm; platform z 42 (full) … 122 (empty); top card held at track z 125 |
| Pick cup | −15 → +15 | 30 mm slide pushes the leading edge to x 74 (8 mm into the feed nip) |
| Feed nip | 66 | |
| Scan entry nip (stub axles) | 146 | lower cross shaft under the glass, upper stubs |
| Scan exit nip (stub axles) | 228 | |
| **Camera axis** | **200** | card on glass x 156 … 244 |
| scan_stop flag (card leading edge) | 244 | |
| Transfer nip | 308 | |
| Sleeve entry nip | 388 | stub upper idlers at y ±26, lower cross shaft |
| **Sleeve mouth** | **406** | platen top z 123.14; sleeve 406 … 497 |
| Exit nip | 526 | at platen level |
| Diverter pivot | 576 | tray 120 mm @ 25°, positions −42° / 0° / +42° |

- All nip spacings 80–82 mm < shortest card (86): a card is always gripped.
- Track plane z 125, deck rails (2020) top z 85, rails at y = ±60.
- **CM3 working distance**: 66° H × 41° V. Framing 92.1 mm along H needs 70.9 mm, framing 66.7 mm along V
  needs 89.2 mm; the CM3 standard lens focuses from 100 mm, so **WD = 100 mm** (field 129.9 × 74.8).
  Lens fronts at z 225.3 (top, looking down) and z 25.0 (bottom, looking up). Sensor long side along x.
- LED frames 45 mm from the card (window ±42 × ±26 > field there ±35.7 × ±20.6).
- Glass: lower 118 × 44 × 2 AR glass (x 128 … 246, rests in track ledges), upper 115 × 44 × 2 (x 126 …
  241, bonded with VHB dots under the two track arches) → 1.0 mm card gap. Glass is 44 wide so the
  O-ring wheels at y ±26 run beside it; only 4 small wheel contact spots overlap the card ends.

## Sleeve station (critical) – geometry

Sleeve frame S: x = 0 at the sleeve mouth, z = 0 = platen top.

| Item | Value |
|---|---|
| Lower shim (0.3 stainless) | z 0.06 … 0.36 (lies on the bottom ply) |
| Card in the throat | z 1.86 … 2.16 → **1.5 mm** to each shim |
| Upper shim (0.3, forked 8 mm slot for the pusher post) | z 3.66 … 3.96 |
| Throat side guides | 66 mm = 63 + 2 × 1.5 |
| Shim width / length out of the clamp | 40 mm / 30 mm (fit between entry wheels at ±26) |
| Tongue tips | retracted −3, inserted **+15** (stroke 18) |
| Top-ply lift | 5.5 mm by a 10 mm cup at (22, −12): tongue tips +15 + cup R5 + 2; mouth edge ≥ 4.4 after the ply sag |
| Entry nip | S −18 (card is 70 mm in when it leaves the nip) |
| Pusher pawl | crank-slider, flap −20 → +36: seats the card to +1.5, then pushes the sleeved card on until its closed end is at +127 (7 mm into the exit nip at +120) |
| Platen | 86 × 70, Ø1.2 holes on a 6 mm grid (x 6 … 78, y −18 … +6), plenum + 4 mm barb; Ø2.5 mouth-sensor window at (6, −26); pawl groove 5 × 1.2 deep x −2 … 40 |
| Magazine | +y side, 100 sleeves flat, open ends at x = 0; 0.14 mm gate at the bottom of the −y wall |
| Sleeve pick | N20 + two Ø20 rubber wheels (A in the magazine floor y 52, B in the platen y 24) linked by a 2 mm O-ring; sleeve slides −y against the fence |

### Sleeving sequence (firmware reference)

1. `sleeve_pick` N20 runs: bottom sleeve leaves the magazine through the gate and slides onto the
   platen against the fence (platen vacuum off) until `sleeve_present` sees it. `platen` valve on.
2. `lift_servo` lowers the cup onto the top ply, `lift_cup` valve on, servo raises 5.5 mm.
   `air_pump` pulse → mouth jet inflates the sleeve.
3. `tongue` stepper drives the tongues +18 mm (tips 15 mm into the mouth). `lift_cup` off, cup up.
4. `feed` stepper drives the card through the throat; `sleeve_mouth` sensor sees the leading edge;
   continue until the trailing edge leaves the entry nip (card 70 mm in). The pawl lifts as the card
   passes under it and drops behind the trailing edge.
5. `pusher_servo` moves the pawl −20 → +0.3 (card seated, trailing edge 1.5 mm inside).
6. `tongue` retracts (tips −3). `platen` off (optionally vent).
7. `pusher_servo` continues to +36: sleeved card into the exit nip; `feed` (exit rollers) takes it;
   `pusher_servo` returns. `exit` sensor confirms → `diverter_servo` already at the target bin.

### Tuning notes

- **Gate gap** first: 1.5 × the measured sleeve thickness (Ultra Pro penny 2 × 45 µm = 0.09 → 0.14 mm),
  one sleeve only. Too small → no feed; too big → doubles (two sleeves are only 0.18).
- **Lift height** (`LIFT`): 5.5 at the cup so the mouth edge, 22 mm away, still sits ≥ 4.4 (upper shim
  top 3.96) after the ply sags ≈ 1.1 mm. If the cup tears off early, lower the servo speed and add more
  vacuum time. **Cup position** (`CUP_X` = 22): as close to the mouth as the inserted tongue tips (+15)
  allow with the R5 cup + 2 mm; don't go below 20. If the mouth stays closed at the far corner, pulse
  the air jet while lifting.
- **Shim tips**: round them (R3) and deburr; fold the last 2 mm of the lower shim down 5° so it slides
  on the bottom ply instead of catching it. Shim template = 40 × 42 mm; cut the 8 × 35 mm fork into the
  upper one.
- **Insertion depth** (`TIP_IN`): 15 mm. Deeper helps wide sleeves stay open but rubs the card.
- Platen vacuum: tape off unused holes for 62 mm sleeves; the vacuum must hold the bottom ply right at
  the mouth (first hole row x = 6).
- Pawl: gravity flap, lifts for the incoming card, can only push forward (rests against the post).
  If it rides over the card edge, add a 1 g weight or a light torsion spring.
- Card speed into the sleeve: ≤ 60 mm/s; the O-ring nips slip before the card buckles.
- Static: PETG + PP sleeves charge up. Ground the shims and use an ionizer if sleeves cling.

## Printed parts (PETG, 0.2 mm layers, 4 walls, 25 % gyroid unless noted)

| Part | Qty | Set | Orientation (in STL) | Support | Notes |
|---|---|---|---|---|---|
| hopper_base | 1 | M | flat | – | NEMA17 + T8 underneath, 8 mm rod sockets, M5 to the frame |
| hopper_guide | 2 | M | inner face down | – | slotted foot (adjustable) |
| hopper_back | 1 | M | inner face down | – | rod yoke, arm slot |
| hopper_front | 1 | M | inner face down | – | puff nozzle Ø1.5 + 4 mm barb, double-feed sensor ear |
| elevator_platform | 1 | M | top down | – | 2 × LM8UU, T8 flange nut, trip tab for the elevator switches |
| elev_switch_post | 1 | M | −y face down | – | on hopper_base (+y of the platform arm), KW11 `elev_home` (low) + `elev_limit` (high) on M2; foot slotted ±3 mm in y to set the lever overtravel |
| pick_bridge | 1 | M | beam top down | yes (hangers) | 6 mm rods, pick NEMA17 plate, stack-top IR pocket, 2 × M2 for the `pick_home` KW-mini on the −x hanger |
| pick_carriage | 1 | M | flat | light | 2 × LM6UU, M5 cup stem, belt clamp |
| roller_block | 10 | M | foot down | light | 608 fixed (lower) + floating 608 (upper, spring pinch) |
| roller_block_s | 2 | M | foot down | light | sleeve-entry variant (on the sleeve deck) |
| roller_hub | 24 | M | flat | – | D26 × 8, two 2 mm O-rings (Ø22 ID), M3 grub; 100 % infill |
| track_feed, track_scan_out | 1 + 1 | M | top down | yes (glass arch) | lower-glass ledge + upper-glass arch, stop-flag mount |
| track_xfer | 1 | M | top down | – | |
| guide_rail_40 / guide_rail_18 | 4 / 2 | M | flat | – | slotted |
| hood | 1 | M | top down | light | black PETG, light tight; card slits, lower-shaft holes |
| lower_shroud | 1 | M | flat | yes (rail tabs) | black PETG; hangs on the inner rail slots |
| led_frame_top / led_frame_bot | 1 + 1 | M | flat | – | **white** PETG; LED channel, 1.5 mm diffuser recess, 0.6 mm side-loading polarizer slot |
| cam_mount | 2 | M | flat | – | CM3 on M2 + 2 mm spacers, lens tube with Ø18 polarizer disc pocket |
| stop_mount / stop_flag | 1 + 1 | M | flat / on side | – | KW-mini microswitch from the top, flag on a Ø1.8 pin |
| sleeve_deck | 1 | M R | flat | – | 221 × 220; tongue NEMA17 underneath |
| platen | 1 | M R | top down | – | 100 % top layers; vacuum plenum; TCRT5000 pockets for `sleeve_mouth` (6, −26) and `sleeve_present` (30, −30, by the fence) |
| sleeve_fence | 1 | M R | flat | – | slotted |
| sleeve_magazine | 1 | M R | flat | yes (under the floor) | 2 sensor windows in the end wall |
| mag_sensor_mount | 1 | M R | flat | – | outside the magazine end wall, TCRT5000 `mag_empty` (z 2.8) + `mag_low` (z 6.5) look at the closed ends of the sleeve stack; 2 × M3 to the deck |
| sleeve_gate | 1 | M R | on side | – | slotted, 0.14 mm gap |
| tongue_carriage | 1 | M R | flat | yes | C-frame: both shim clamps, 2 × LM6UU, GT2 clamp |
| tongue_keeper_lo / tongue_keeper_hi | 1 / 2 | M R | flat | – | clamp the shims (M2 × 6) |
| tongue_rod_block | 3 | M R | flat | – | 6 mm rods |
| tongue_rod_block_sw | 1 | M R | flat | – | −x / +y rod block stretched to y 55, `tongue_home` KW-mini on top (2 × M2), trips on the carriage side frame when retracted |
| air_jet | 1 | M R | flat | – | Ø1.2 nozzle aimed into the mouth, 4 mm barb |
| lift_mount / lift_arm | 1 + 1 | M R | flat / hub face down (finger up) | – | MG90S, M4 cup stem at the end of the 9 × 6 finger (x 22) |
| pusher_bracket | 1 | M R | flat | yes | 6 × 6 guide bar + servo arm |
| pusher_slider / pusher_flap / pusher_crank / pusher_link | 1 each | M R | as exported | – | crank r 24, link 80, Ø3 pins |
| rig_foot | 4 | R | flat | – | 60 mm legs (clear the NEMA17) |
| rig_push_slot / rig_push_stick | 1 + 1 | R | flat | – | manual card push channel + 1.6 mm push stick |
| diverter_base | 1 | M | flat | yes (lead-in) | MG90S tower, exit-sensor pocket |
| diverter_tray | 1 | M | plate down | yes (hub) | |
| bin | 3 | M | flat | – | 97 × 71 × 60 inner (100 sleeved cards ≈ 45 mm) |
| feed_motor_mount | 1 | M | rail face down | yes | NEMA17 'feed' |
| corner_bracket | 12 | M | flat | – | 2020 L brackets |
| frame_foot | 6 | M | flat | – | 40 mm |
| elec_plate_a / elec_plate_b | 1 + 1 | M | flat | – | 240 × 150, see electronics |
| estop_panel | 1 | M | panel face down | – | on the −y base rail at x −40: 22.3 mm hole + anti-rotation notch, 2 × M5 |
| lid_switch_mount | 1 | M | flat | – | L bracket on the +y base rail at x 350 for the lid interlock, 2 × M5, 4 × M4 |

## Hardware BOM

| Item | Qty | Where |
|---|---|---|
| 2020 extrusion | 2 × 925, 6 × 390, 2 × 576 (deck rails), 6 × 65 (posts), 2 × 510 | base, cross members, deck rails, posts, electronics rails |
| M5 × 10 + T-nut | ~60 | everything on the 2020 |
| NEMA17 42 × 40 + T8 × 150 integrated lead screw (+ brass flange nut) | 1 | `elevator` |
| NEMA17 42 × 40 | 3 | `pick` (GT2 belt), `feed` (GT2 loop to all lower roller shafts), `tongue` (GT2) |
| GT2 20T pulley 5 mm bore / 20T idler F623 | 3 / 3 | pick, feed, tongue |
| GT2 6 mm belt | ~0.3 m pick, ~1.5 m feed loop, ~0.15 m tongue | |
| GT2 20T pulley 8 mm bore | 7 | lower roller shafts (6 on −y, 1 sync belt +y scan) |
| 8 mm rod | 2 × 125 (elevator), 6 × 140 + 3 × 160 cross shafts, 6 × 35 stub axles | |
| 6 mm rod | 2 × 100 (pick), 2 × 55 (tongue) | |
| LM8UU / LM6UU | 2 / 4 | elevator / pick + tongue |
| 608-2RS bearing | 24 | roller blocks |
| O-ring 2 mm cord, 22 mm ID (NBR 70) | 48 | roller hubs |
| Compression spring Ø5 × 10 + M3 set screw | 12 | upper roller pinch |
| 20 mm bellows suction cup + M5 stem | 1 | `pick_cup` |
| 10 mm suction cup + M4 stem | 1 | `lift_cup` |
| MG90S servo | 3 | `lift_servo`, `pusher_servo`, `diverter_servo` |
| N20 6 V gearmotor (~300 rpm) + 2 × Ø20 rubber wheels + 2 mm O-ring belt | 1 | `sleeve_pick` |
| 12 V diaphragm vacuum pump (~70 × 40 × 30) | 1 | vacuum |
| 12 V 3/2-way solenoid valve (NC, de-energised = cup vented) | 3 | `valve_pick_cup`, `valve_platen`, `valve_lift_cup` (vacuum: a 2-way valve would trap the vacuum and never release) |
| 12 V 2-way solenoid valve (NC) | 2 | `valve_stack_puff`, `valve_mouth_jet` (air) |
| 12 V mini air pump | 1 | `air_pump` → `valve_stack_puff` (hopper puff) + `valve_mouth_jet` (sleeve mouth jet) |
| Vacuum manifold block (1 in, 3 cup valves + sensor port) | 1 | `vac_manifold`, elec_plate_b |
| Vacuum sensor XGZP6847A100KPGN (−100…0 kPa, 5 V) | 1 | `vac_sensor`, teed into the manifold (grip detection) |
| 4 mm silicone tube, barbs, tees | ~3 m | |
| 0.3 mm stainless shim | 2 × 40 × 42 | tongues |
| AR glass 2 mm | 118 × 44, 115 × 44 | scan station |
| Raspberry Pi Camera Module 3 + 300 mm ribbon | 2 | top + bottom |
| Linear polarizer film | 2 × LED ring + 2 × Ø18 discs | cross-polarized: lens film at 90° to the light film |
| Opal diffuser 1.5 mm | 2 rings | LED frames |
| 12 V white LED strip (non-addressable, 2835 60/m, PWM via MOSFET Q8/Q9) | 2 × ~0.45 m | LED frames |
| TCRT5000 reflective sensor module | 6 | `stack_top`, `sleeve_mouth`, `sleeve_present`, `exit`, `mag_low`, `mag_empty` |
| Slot interrupter (TCST2103 class) + 1.8 mm pin lever | 1 | `double_feed` |
| KW-mini microswitch (12.8 × 5.8 × 6.5, roller lever) | 3 | `scan_stop` (NO), `pick_home`, `tongue_home` (NC) |
| KW11-3Z microswitch (20 × 10 × 6.4, roller lever) | 2 | `elev_home`, `elev_limit` (NC) |
| Lid interlock, 2 NC contacts (Omron D4NS class) + actuator key | 1 | `lid` – one NC in the K1 coil chain, one to MCP23017 #2 GPA6 |
| E-stop mushroom 22 mm, twist release, 2 NC blocks | 1 | NC1 in the K1 coil chain, NC2 → GPIO47 |
| Relay 24 V coil, ≥ 10 A 30 V DC (Omron G7L-1A-TUB or automotive) + 1N4007 | 1 | `relay_k1`, elec_plate_a |
| MCP23017 module (CJMCU-2317) | 2 | `mcp23017_out` 0x20, `mcp23017_in` 0x21, elec_plate_a |
| Raspberry Pi 5 + active cooler | 1 | |
| ESP32-S3 DevKitC-1 | 1 | |
| TMC2209 ×4 on a carrier board | 1 | elevator, pick, feed, tongue |
| 24 V PSU (Mean Well LRS-150-24, 6.5 A, 159 × 97 × 30) | 1 | |
| 5 V 5 A buck | 1 | Pi 5 (`buck_5v`) |
| 24 → 12 V 8 A buck + 9-ch MOSFET board, 24 → 5 V 3 A servo buck | 1 + 1 + 1 | per ../electronics/WIRING.md (not yet placed on the plates) |
| DRV8833 module | 1 | `drv8833` – N20 `sleeve_pick`, elec_plate_a |
| M3 heat-set inserts (Ø4.0) | ~85 | |
| M2 × 10 screws | 8 | KW11 / KW-mini switches |
| M3 × 8 / 12 / 16, M2 × 6, M4 nuts | assorted | |

## Assembly order

1. **Phase-1 rig first** (stl/rig/): sleeve_deck on 4 rig_feet; tongue NEMA17 under the deck; platen,
   magazine (+ gate), fence; rod blocks + rods + LM6UU + tongue_carriage + shims/keepers; GT2 loop and
   idler; air_jet; lift_mount + MG90S + lift_arm + cup; pusher_bracket + MG90S + crank + link + slider +
   flap; N20 + pick wheels; rig_push_slot. Tune per the notes above with hand-pushed cards (push stick).
2. Base frame: 2020 rectangle + cross members on frame_feet; posts + corner brackets; deck rails.
3. Hopper: base on the cross members (motor below), rods, platform, back/front walls, guides, pick
   bridge with rods/carriage/motor/belt.
4. Roller blocks on the deck rails (feed, scan in/out, xfer), shafts + hubs + O-rings, springs; feed
   motor mount + GT2 loop under the −y rail; +y sync belt between the scan shafts.
5. Tracks + guide rails; lower glass into the ledges; upper glass bonded under the arches (1 mm
   gap, check with a 1 mm feeler); stop mount + flag + microswitch.
6. Lower shroud (LED frame bot, polarizer, diffuser, cam_mount + CM3), hood (LED frame top, cam_mount +
   CM3). Rotate the lens polarizer discs for maximum glare kill (crossed). Lay both LED films with
   the same world orientation, so each lens is also crossed to the *other* ring: both rings are on
   during capture, and the open glass beyond the card ends lets each ring shine into the far camera.
7. Move the phase-1 sleeve deck onto the deck rails (remove rig feet/push slot), add entry + exit
   roller blocks.
8. Diverter base + MG90S + tray; bins on a 3 mm board.
9. Electronics plates on the −y rails; e-stop panel and lid interlock bracket on the base rails; wire per
   ../electronics/WIRING.md.

## Motors, actuators, sensors (names used by firmware / wiring)

| Name | Hardware | Where |
|---|---|---|
| `elevator` | NEMA17 + T8 (TMC2209) | under hopper_base |
| `pick` | NEMA17 + GT2 (TMC2209) | pick_bridge leg |
| `feed` | NEMA17 + GT2 loop (TMC2209) – drives all lower rollers (feed, scan, xfer, entry, exit) | feed_motor_mount |
| `tongue` | NEMA17 + GT2 (TMC2209) | under sleeve_deck |
| `lift_servo` | MG90S | lift_mount |
| `pusher_servo` | MG90S | pusher_bracket |
| `diverter_servo` | MG90S | diverter_base |
| `sleeve_pick` | N20 gearmotor (DRV8833) | magazine / platen |
| `vacuum_pump` | 12 V diaphragm | elec_plate_b |
| `valve_pick_cup`, `valve_platen`, `valve_lift_cup` | 12 V NC 3/2-way solenoids (vent on release) | elec_plate_b |
| `air_pump` (puff) | 12 V mini pump | elec_plate_b |
| `stack_puff`, `mouth_jet` | 12 V NC solenoids after the air pump | elec_plate_b |
| `vac_sense` | XGZP6847A on the vacuum manifold | elec_plate_b |
| `stack_top` | TCRT5000 | pick_bridge |
| `double_feed` | slot interrupter + lever | hopper_front ear |
| `scan_stop` | microswitch + flag | stop_mount |
| `sleeve_mouth` | TCRT5000 under the platen (6, −26) | platen |
| `sleeve_present` | TCRT5000 under the platen (30, −30), 1.5–3.4 mm short of the fence: sleeve delivered by `sleeve_pick` (wheels run `sleeve_push_ms` more) | platen |
| `mag_low`, `mag_empty` | TCRT5000 × 2 through the magazine end wall | mag_sensor_mount |
| `elev_home`, `elev_limit` | KW11 NC, tripped by the platform tab (full-stack bottom / 1 mm past empty) | elev_switch_post |
| `pick_home` | KW-mini NC, carriage at x −15 | pick_bridge −x hanger |
| `tongue_home` | KW-mini NC, tongues retracted (tips −3) | tongue_rod_block_sw |
| `lid` | interlock, 2 NC | lid_switch_mount |
| `estop` | 22 mm mushroom, 2 NC + K1 relay | estop_panel / elec_plate_a |
| `exit` | TCRT5000 | diverter_base lead-in |
| `cam_top`, `cam_bottom` | CM3 (Pi 5 CSI 0/1) | hood / lower shroud |
| `led_top`, `led_bottom` | LED strips | LED frames |

Switch and sensor placement follows `../firmware/include/config.h` (MCP23017 #2 inputs, `PIN_ESTOP`,
`PIN_VAC_SENSE`). The lid / enclosure itself is not modelled: `lid_switch_mount` sits on the +y base
rail; move it to the enclosure rim so the lid carries the actuator key. The KW11 / KW-mini levers are
shown 0.25–0.5 mm off their trip faces; set the final overtravel with the slotted post foot (elevator)
or by bending the lever (pick, tongue).
