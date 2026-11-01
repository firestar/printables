# 4U rack case: ROG STRIX B660-G + 4 x Tesla V100 + air cooler + 1600 W

A 19" 4U case printed in ASA on a Bambu P1S (256 bed). It has 48 parts plus 89 snap pins.
- **Structure** clips together with printed snap pins.
- **Removable modules** slide on printed plastic rails.
- No screws, no heat-set inserts, no bearings.

Body 430 W x 176 H x 567 D. With the ears it is 482.6 wide. The front handles add 32 mm and the rear exhaust fans add 25 mm.

```
 REAR   [ D    C  | A    B ][ board I/O ][ 2 x 92 exh (outside) ][ C14 ]
        | GPU D  GPU C | GPU A  GPU B |   CPU + tower cooler      |AC/ |
        | (OCuLink     | (board x4 /  |                           |EPS |
        |  slot boards)|  x16 slots)  |                           |trgh|
        |---- duct sleeve over the 4 card tails ----|  slack + plug zone |
        |  loft     2 x 120x38 push fans (module)   |G| 1600 W PSU sled |
 FRONT  [ GPU fan bay (rail)                         |L|[ PSU bay (rail) ]
```

## GPUs: no ribbon risers
- **GPU A and GPU B** plug straight into the board's two x16 slots. A runs at x4 and B at x16 Gen5.
- **GPU C and GPU D** sit on bought **OCuLink-to-PCIe x16 slot boards** on the printed `gpu_stand`.
  - The stand uses the same snap standoffs as the board, so all four cards line up at the same height.
  - The slot boards are fed from the board's two M.2 slots through M.2-to-OCuLink adapters and **thin, flexible round SFF-8611 cables**. They route along the `gpu_stand` cable guide.
- **Spacing:** the cards sit 57–61 mm apart, leaving 22–26 mm gaps. Gap fins in the duct sleeve force the air through each heatsink.
- **Brackets:** each bracket drops into a slot in the rear panel's tab ledge. The `gpu_clamp` bar presses all four tabs down and is held by 2 pull-out pins.
- **Exhaust:** the cards exhaust through their brackets and the rear panel windows, like a normal PC.
- **Bandwidth:** B gets x16. A, C and D get x4 each. That's fine for compute, but transfers between cards and the host are slower.

## Rails (removable modules)
| Module | Rail | Comes out | Held in by |
|---|---|---|---|
| **GPU fan module** (`fan_plate` + `fan_face` + `fan_duct`, 2 x 120x38 fans, `bezel_gpu`) | dovetail rail on the floor | **front** | 2 flexure latches: a nub in the base drops into the floor. Lift the tabs under the faceplate to release |
| **PSU** on `psu_sled` | dovetail rail | **front** | 2 service pins in the face flange |
| **Lid** (6 puzzle tiles, 5 mm) | 45 deg V-tongues in the wall V-grooves | **rear**, over the lowered rear panel | 2 flexure latches at the rear edge |

The GPUs and the board tray lift out once the lid and the fan module are off. The script checks every slide and lift path against all fixed parts, and all of them are clear.

## Cable management
- **Right trough** (`trough_r_1/2`, along the right wall, beside the board):
  - **AC lead:** from the snap-in C14 inlet through the **strain-relief clip** at the trough's rear end, along the trough, into the **slack bay** behind the PSU, then to the PSU inlet. The 260 mm slack lets the sled slide out with the lead attached.
  - **CPU 8-pin EPS:** from the PSU front, through the GPU lane and the slack bay, along the trough to the board's rear-right corner.
- **GPU lane** (`trough_gpu_1/2`, between the fan module and the PSU):
  - **4 x 8-pin GPU cables:** they run to the back of the lane, up and over the duct, and into the sleeve slots at each card tail. They can stay plugged in when the fan module slides out.
  - **24-pin:** from the PSU front to the board's front edge.
- **Combs** (`comb_r`, `comb_gpu`, 2 each): they clip onto the trough walls and keep the cables separated.
- **Zip-tie slots:** every 50 mm in the trough bases.
- **OCuLink guide:** hooks on the `gpu_stand`.

## Clips (structure)
| Joint | Pins |
|---|---|
| Tile seams (floor, walls, front, rear) | `pin_lock_flat_d5_g9p25` x 31 |
| Walls, panels and troughs to the floor (6 mm flanges) | `pin_lock_flat_d5_g10` x 22 |
| Rails to the floor (countersunk, flush) | `pin_lock_csk_d5_g10` x 8 |
| Front/rear panels to the wall end ribs (countersunk) | `pin_lock_csk_d5_g15` x 8 |
| Fan module parts to each other | `pin_lock_flat_d5_g18` x 4 |
| Handles | `pin_lock_flat_d5_g23` x 4 |
| PSU sled face, board tray, GPU stand | `pin_service_tab_d5_g8` x 10 |
| GPU clamp bar | `pin_service_tab_d5_g13` x 2 |
| Lid tiles | in-plane dovetail puzzle joints |

- **Lock pins** are effectively permanent. To remove one, squeeze the barbs with pliers.
- **Service pins** pull out by their tab.
- **Strain limits:** every pin type stays at 2.6 % arm strain or less, and the latches at 2.2 % or less.

## Service (no tools)
1. **Lid:** lift the 2 latch tabs at the rear edge and slide the lid out the back.
2. **GPU fan module:** lift the 2 latch tabs under the faceplate and slide the module out the front. The GPU cables slide out of the sleeve slots.
3. **GPUs:** pull the 2 clamp pins and lift off the `gpu_clamp`. Unplug the 8-pin (and the OCuLink cable for C/D), then lift the card out.
4. **PSU:** pull the 2 face pins and slide the sled out ~10 cm. Unplug the modular cables, slide it out fully with the AC lead attached, then unplug.
5. **Board:** with the lid, fan module and GPUs out, pull the 4 tray pins, slide the tray 15 mm forward, then lift.

## Hardware you buy
| Qty | Part |
|---|---|
| 1 | 1600 W ATX PSU (150 x 86 x 200; set `PSU_L` if yours differs) |
| 1 | tower CPU cooler, **140 mm tall or less**, LGA1700, 120 mm fan blowing front to rear |
| 2 | 120x38 high-static fan (~200 CFM; about 1000 W of passive cards behind them) |
| 2 | 92x25 fan + finger guards (rear, outside) |
| 16 | silicone fan rivets for 4.5 mm holes |
| 2 | M.2-to-OCuLink adapter (2280) |
| 2 | OCuLink (SFF-8611) to PCIe x16 slot board with mounting holes (default footprint 40 x 110 mm, `ADAPTER`) |
| 2 | OCuLink SFF-8611 cable, 50 cm |
| 14 | nylon snap-in PCB standoffs 6.35 mm for 4 mm holes in 1.6 mm panels (6 board + 8 slot boards) |
| 4 | 8-pin EPS (CPU-type) cables for the V100s |
| 1 | snap-in C14 inlet (cutout 27.2 x 19.6) + **0.8 m** C13 lead, 1.5 mm² / 14 AWG |
| 2 | 12 mm momentary switches, 1 panel-mount USB-C extension, LED strip for the light pipe |
| 12 | 6x3 mm magnets (GPU bezel 4 + top bezel 2, plus the same number in the faceplate/panel) |
| 4 | 15 mm stick-on rubber feet |
| – | zip ties, 1.5 mm foam tape for the duct sleeve |

**Rack: use a shelf.** The loaded case is ~13 kg.

## Printing (Bambu P1S)
- **Material:** ASA with the door closed, 0.4 nozzle, 0.2 mm layers. Use 4 walls and 25 % gyroid infill. Print the **pins, rails and latches at 100 %** infill.
- **Orientation:** `cad/stl/` is already in print orientation, and **no supports** are needed.
  - Horizontal holes have a teardrop shape so they print without supports.
  - V-tongues, V-grooves and the rail flanks are 45 deg.
  - The remaining down-facing areas are bridges: rail channels (23 mm), windows and pockets.
- **Bed size:** every part fits within 250 mm. The two combs share one STL each; print 2.
- **ASA shrink:** scale to 100.5 % or set `SHRINK = 1.005`. Print the `tolerance_coupon_a/b` first.

| Constant | Default | Used for |
|---|---|---|
| `CLR_SLIDE` | 0.4 / side | rails, grooves, bays |
| `CLR_PUZZLE` | 0.12 / side | lid puzzle joints |
| `PIN_HOLE` / `PIN_LIP` / `SPIN_LIP` | 5.3 / 0.7 / 0.5 | pins |
| `RAIL_W0` / `RAIL_W1` / `RAIL_H` | 10 / 22 / 6 | dovetail rails |

## Assembly
1. Pin the floor tiles together. Countersink-pin the rails to the floor, then pin the troughs down.
2. Pin the walls together and lock-pin them to the floor.
3. Assemble the front panel and pin it to the floor and the wall end ribs. Do the same with the rear panel.
4. Board: snap the standoffs into the tray, fit the board, cooler and I/O shield, then pin the tray (service pins). Fit the M.2-to-OCuLink adapters.
5. GPU stand: snap in the standoffs and the two OCuLink slot boards, then pin the stand. Run the OCuLink cables under the guide hooks.
6. Fit GPUs A–D, dropping the brackets into the ledge slots. Lay the `gpu_clamp` on the tabs and fit its 2 pins.
7. PSU: slide the PSU sideways into the sled, then slide the sled in. Route the cables:
   - AC: trough → strain relief → slack bay.
   - EPS: GPU lane → slack bay → right trough.
   - 24-pin and the 4 x 8-pin: GPU lane.

   Fit the combs.
8. Fan module: rivet the fans to `fan_face`. Lock-pin `fan_plate` + `fan_face` + `fan_duct` together, line the sleeve with foam, then slide it in until the latches click. Plug the 8-pins into the card tails through the sleeve slots.
9. Press the lid tiles together and slide the lid in from the rear until it latches. Fit the bezels, light pipe and handles.

## Measure / verify before printing (constants in `case.py`)
- **Board slots:** `SLOT_FROM_EDGE` (A = x16 at x4, B = x16 Gen5; defaults 14 / 75 mm from the slot edge), the M.2 positions, `MATX_HOLES`, and the I/O aperture.
- **V100:** `CARD_L/H/T`, `FINGER_Y_OFF`, and where the 8-pin sits (`PWR_NOTCH_W`). The bracket tab is assumed to sit 9 mm above the card top.
- **OCuLink slot board:** footprint and mounting holes (`ADAPTER`, `adapter_holes`).
- **PSU:** length (`PSU_L`) and AC inlet position (`PSU_AC`).
- **Cooler:** height (`COOLER`).
- **C14 cutout:** `IEC_SNAP`.

## Build
```
cd cad
PYTHONPATH=../../.pydeps python3 case.py      # stl/, preview/, fit + pin + slide/lift checks
python3 -m http.server 8093                   # then open viewer.html
```
`viewer.html` URL params: `view=`, `section=z|x`, `lid=0`, `shell=0`, `ctx=0`,
`cassette=0` (fan module), `cables=0`, `pins=0`, `explode=0..100`.
