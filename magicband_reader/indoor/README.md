# MagicBand reader – indoor variants

This is the same 150 mm ball head as the outdoor build ([`../cad/`](../cad/README.md)), printed in PETG or PLA with
**no gaskets**. Every 1.0 mm gasket gap is closed, so parts seat directly on each other. The screw and insert scheme
is unchanged. You pick one option from each of three groups:

| Arm | Mount | Electronics |
|---|---|---|
| **fp**: `arm_base` + `pod_cap_in` with the R503 | **wall**: `wall_bracket_in` | **split**: outdoor `electronics_tray`, indoor controller box |
| **blank**: `arm_base` + `pod_cap_blank` (oval recess, no sensor) | **table**: weighted `table_base` + `table_floor` | **aio**: `electronics_tray_aio` + `aio_deck` with relay + terminal |
| **ball**: no arm, `ball_riser` under the neck | **post**: park-style pedestal on a 1" EMT pipe | |

That gives 9 arm × mount combos, and each one works with either electronics option. Every mount has the same
**arm seat**: 4 × M3 screws from below at (XB ± 19, YC ± 12) into the inserts under `arm_base` or `ball_riser`,
plus the cable hole at the seat centre. So every mount takes the arm or the ball on its own. With ball-only, the
ball sits centred over the seat.

- `cad/indoor.py` holds the geometry and checks. Run `PYTHONPATH=../../../.pydeps python3 indoor.py` from `cad/`. It
  imports `../../cad/magicband.py` and builds the reused parts with the outdoor parameters. It then switches to
  the indoor parameters (gap 0, halo shoulder 1 mm thicker, pod cap 1 mm taller, wall gap +1 so the arm keeps its
  place) and builds the changed and new parts. The outdoor script is not modified.
- `cad/section.py` writes `cad/preview/section_2d.png`: the post cut with the cable down the pipe, the post base
  (pipe stop, cable window, duct, ballast), and two cuts through the tabletop base (bay, duct, ballast pockets).
- `cad/viewer.html` is a three.js viewer; serve `magicband_reader/` over http and open `indoor/cad/viewer.html`.
  It has dropdowns for Arm, Mount and Electronics, and views for iso, front, side and section (y = ball axis). It
  also has an explode slider, toggles for context, hardware and electronics, and the green "granted" light.
  URL parameters work too, e.g. `?arm=ball&mount=post&mode=aio&view=section`.
- `cad/stl/` holds the indoor-new parts in print orientation. `cad/preview/` holds every part in its assembled
  position plus `manifest.json`, where each part is tagged with its arms, mounts, modes and frame.

## Parts

STLs come from `cad/stl/` (new) or `../cad/stl/` (reused). The script checks that each reused part is identical to
the outdoor STL.

| Part | STL | Used by | Material | Print | Size (mm) |
|---|---|---|---|---|---|
| ball_front_in | indoor | all | PETG/PLA silver | face down | 137 × 137 × 25 |
| ball_rear | **outdoor** | all | PETG/PLA silver | rear opening down | 150 × 147 × 63 |
| rear_hatch_in | indoor | all | PETG/PLA | back down | Ø134 × 4 (no nub, flat face closes the tamper switch) |
| face_carrier | **outdoor** | all | PETG/PLA **white** | back down | Ø112 × 14.5 |
| halo_ring_in | indoor | all | **translucent** PETG | shoulder down | Ø111 × 10 (shoulder 4 mm, seats on the collar) |
| face_disc (or face_disc_blank) | **outdoor** | all | PETG/PLA black | back down | Ø92 × 5.4 |
| mickey_inlay | **outdoor** | all | **translucent** PETG | front down | 56 × 48 × 5.4 |
| neck | **outdoor** | all | PETG/PLA | base down | Ø64 × 36 (cup clearance to the ball 0.07–0.1 mm) |
| electronics_tray | **outdoor** | split | PETG/PLA | plate down | 90 × 60 × 22 |
| electronics_tray_aio | indoor | aio | PETG/PLA | plate down | 103 × 60 × 22 (outdoor tray + 2 fins with insert bosses) |
| aio_deck | indoor | aio | PETG/PLA | plate down | 103 × 50 × 5.5 (relay + terminal pockets, 2 wire slots) |
| arm_base | **outdoor** | fp, blank | PETG/PLA | base down | 231 × 80 × 101 |
| pod_cap_in | indoor | fp | PETG/PLA | top face down | 80 × 101 × 21 (15 thick instead of 14) |
| pod_cap_blank | indoor | blank | PETG/PLA | **rim down (top up)** | 80 × 101 × 15, solid (infill) |
| ball_riser | indoor | ball | PETG/PLA | base down | Ø62 × 40 |
| wall_bracket_in | indoor | wall | PETG/PLA | wall side down | 80 × 122 × 71 (plate sits on the wall) |
| table_base | indoor | table | PETG/PLA | top down | 240 × 144 × 26 |
| table_floor | indoor | table | PETG/PLA | inside face down | 233 × 137 × 3 |
| post_base | indoor | post | PETG dark green | top down | Ø248 × 50 |
| post_floor | indoor | post | PETG/PLA | inside face down | Ø241 × 3 |
| post_collar | indoor | post (**3×**) | PETG dark green | upright | octagon AF100 × 35 |
| post_sleeve | indoor | post (**4×**) | PETG dark green | upright | Ø76 × 176.4 |
| post_saddle | indoor | post | PETG dark green | top down | octagon AF78→62 × 45 |

### What to print per combo

| | wall | table | post |
|---|---|---|---|
| **fp** | head + arm_base + pod_cap_in + wall_bracket_in | head + arm_base + pod_cap_in + table_base + table_floor | head + arm_base + pod_cap_in + post set |
| **blank** | head + arm_base + pod_cap_blank + wall_bracket_in | head + arm_base + pod_cap_blank + table_base + table_floor | head + arm_base + pod_cap_blank + post set |
| **ball** | head + ball_riser + wall_bracket_in | head + ball_riser + table_base + table_floor | head + ball_riser + post set |

- **head** = ball_front_in, ball_rear, rear_hatch_in, face_carrier, halo_ring_in, face_disc + mickey_inlay (or
  face_disc_blank), neck, plus the tray for your mode: split → electronics_tray, aio → electronics_tray_aio +
  aio_deck.
- **post set** = post_base, post_floor, 3 × post_collar, 4 × post_sleeve, post_saddle.

Every part passes the checks: one body, watertight, fits the 250 mm bed, and has no overhang beyond 45° (0.0 mm²;
the trays show 0.1 mm², the same as outdoors). The tabletop and post bases print **top down**: the pockets open
upward, and the 40° top bevel and the 35° pipe-stop cone need no support. The floor plates print **inside face
down**, so the felt recesses and countersinks face up. Suggested settings are 3 walls and 15 % gyroid. The
collars and saddle are thick-walled solids, so infill keeps them light.

## Hardware

| Item | Qty | Where |
|---|---|---|
| M3 heat-set insert (Ø4.0 hole) | as outdoors (ball, neck, arm) + 4 ball_riser + 4 aio fins + 6 table_base + 5 post_base | |
| M3 × 12 socket head | 3 | ball → neck (from inside the ball), as outdoors |
| M3 × 12 socket head | 3 | arm boss or ball_riser → neck (from below) |
| M3 × 16 socket head | 4 | seat: wall bracket shelf → arm/riser |
| M3 × 10 socket head | 4 | seat: table_base top plate (5 mm) → arm/riser, from inside the service bay |
| M3 × 16 socket head | 4 | seat: post_saddle plate (10 mm) → arm/riser, through the Ø7 counterbores from below |
| M3 × 16 pan head | 3 | pod_cap_in → pod columns (as outdoors) |
| M3 × 20 pan head | 3 | pod_cap_blank → pod columns |
| M3 × 6 pan head | 4 | aio_deck → fin bosses |
| M3 × 8 countersunk | 6 / 5 | table_floor / post_floor |
| M4 × 80 bolt + nyloc nut | 1 | post_saddle cross bolt through the pipe |
| **1" EMT conduit (OD 29.5)**, cut to **872 mm** | 1 | post core (alternative: 32 mm PVC, set `PIPE = "pvc"`) |
| Felt pads Ø25 (≤ 3 mm) | 4 / 6 | table_floor / post_floor recesses (1.2 deep) |
| **Ballast: dry sand 0.75 kg** (470 cm³ of pockets) | | table_base. Steel washers / shot ≈ 2.1 kg fit the same pockets |
| **Ballast: dry sand 2.7 kg** (1677 cm³ of pockets) | | post_base. Steel shot ≈ 7.5 kg fits |
| 5 mm floor screws (optional) | 3 | post_base anchor holes (Ø5.2 through, use washers) |
| AIO: 1-ch 5 V relay module (≈ 50 × 26 × 19) | 1 | aio_deck, contacts toward the hatch |
| AIO: 6-way 5.08 mm screw terminal (on a 32 × 10 strip) | 1 | aio_deck rear edge, wire entries face the rear hatch |

The head needs 6 cores in AIO mode (12 V, GND, strike +/−, exit button, door contact). Use a 6 mm cable; every
cable path passes a 6 mm probe.

## Assembly notes

1. **Head:** follow the outdoor order (`../cad/README.md`) without any gaskets. The halo shoulder seats on the
   ball_front collar, and the seam screws clamp the carrier tabs. The hatch screws onto the lugs directly, and its
   face closes the tamper switch.
2. **AIO tray:** screw electronics_tray_aio to the carrier and fit the boards. Then put the aio_deck on the fins
   (4 screws) **before** fitting ball_rear, because the deck covers the tray screws. The cable comes up through the
   Ø10 tray hole next to the terminal. Wire the terminal through the rear hatch.
3. **Arm / riser:** screw the neck to the arm boss or ball_riser from below (3 screws). Then fix the arm or riser to
   the mount seat (4 screws from below).
4. **Wall:** same as outdoors. The plate sits directly on the wall. The cable goes through the 30° bore into the
   wall, or down the V-groove.
5. **Table:** fix the arm or riser through the top plate from inside the service bay. Route the cable down the bay
   and along the duct to the notch at the back. Fill the pockets with sand (or glued washers). Screw on table_floor
   and stick the felt pads into the recesses.
6. **Post:**
   1. Cut the EMT to 872 mm, deburr it, and drop it into post_base, where it rests on the stop cone.
   2. Stack collar, 2 sleeves, collar, 2 sleeves, collar over the pipe.
   3. Pull the cable down the pipe. It leaves through the tube window, runs along the duct and exits at the
      notch at the back.
   4. Screw the head to the saddle on the bench, then push the saddle onto the pipe.
   5. Drill Ø4.5 through the pipe using the saddle's cross hole as a jig. The hole is 18 mm below the pipe top.
      Fit the M4 bolt.
   6. Fill the base pockets with ballast and screw on post_floor.

## Layout numbers (from the script)

- Ball centre 144.3 mm above the arm seat (outdoors 146.3), face plane at the same place relative to the arm.
- Post: face centre 1050 mm (`FACE_H`) → seat at 905.7. Base 50, collars 3 × 35, sleeves 4 × 176.4, saddle 45.
  The pipe runs from z 23.6 on the stop cone to 895.7 under the saddle plate, which is the 872 mm cut length.
- Tip-over: the contact is the felt pad centres. The CoM uses printed parts at 1.25 g/cm³ (1.2 mm skins + 15 %
  infill), EMT at 7.85 g/cm³, electronics ≈ 180 g and the ballast at its pocket centroid.

| Mount | Arm | Total mass | CoM height | Tip angle (sand) | Steel ballast | No ballast |
|---|---|---|---|---|---|---|
| table | fp | 1.81 kg | 64 | **36.6°** | 49.2° | 24.8° |
| table | blank | 1.80 kg | 63 | **36.8°** | 49.4° | 24.7° |
| table | ball | 1.64 kg | 63 | **36.6°** | 50.1° | 23.0° |
| post | fp | 6.06 kg | 299 | **16.0°** | 26.4° | 9.0° |
| post | blank | 6.04 kg | 297 | **16.0°** | 26.6° | 9.0° |
| post | ball | 5.89 kg | 280 | **17.8°** | 28.6° | 10.4° |

The nearest tipping edge for the table is the long side (47 mm from the CoM). For the post it is the hexagon of
felt pads (85–90 mm). **The post needs its ballast**: without it, it would tip at 9°.

## Split vs all-in-one

- **Split** is the outdoor architecture. The reader has no authority, and the indoor controller box
  (`../cad/stl/controller_box.stl` + lid) holds the relay. Use it whenever the reader sits on the unsecured side.
- **All-in-one** puts the strike relay in the head. Use it **only when the reader is on the secure side of the
  door**: indoors, at an inner door, or on a tabletop / post inside. Anyone who can open the head or reach its
  cable can short the strike wires.
