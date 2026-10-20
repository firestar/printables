# MagicBand reader – enclosure CAD

Park-entry-touchpoint look: 150 mm brushed-metal-look ball with a flat face (Mickey outline inside a
glowing halo, 7 speaker holes), short neck with a cup, horizontal arm to an 80 mm pod with a sloped
top and an oval finger funnel holding an R503 fingerprint sensor. Wall mounted outdoors beside the
front door, with an indoor controller box.

- `magicband.py` – all geometry and checks (parameters at the top). Run:
  `PYTHONPATH=../../.pydeps python3 magicband.py`
- `section.py` – writes `preview/section_2d.png` (cut through ball/neck/arm/pod, cut through the ball, face-stack zoom with the antenna distance).
- `viewer.html` – three.js viewer for `preview/` (serve this folder over http). Views: iso / face / pod / side, section x or y, explode, context on/off, electronics on/off, “light” (granted-green halo + inlay).
- `stl/` – every part in print orientation. `preview/` – assembled parts, dummies, context, `manifest.json`.

Every part prints **without supports**: the script checks per part that faces overhanging more than
45° (excluding the bed face) add up to 0 mm², that each part is one watertight body, and that it fits
the 250 mm bed.

## Parts

| Part | Qty | Material | Print orientation | Notes |
|---|---|---|---|---|
| ball_front | 1 | ASA (silver) | face down | Face opening D104. 4 seam bosses with M3 inserts. Spigot drops into ball_rear. |
| ball_rear | 1 | ASA (silver) | rear opening down | Hidden flat rear service opening (faces the wall). Seam lugs, hatch lugs, tamper-switch pocket, neck pad with cable hole + 3 screw holes. |
| rear_hatch | 1 | ASA | back down | D134 disc, 4 × M3, nub presses the tamper switch. |
| face_carrier | 1 | ASA **white** (it lines the light box) | back down | WS2812B ring channel, PN532 standoffs, speaker duct + speaker screws, tray bosses. Its tabs are clamped by the seam screws. |
| electronics_tray | 1 | ASA | plate down | Pockets for ESP32-S3-Zero, MAX98357A, MAX3485, mini buck. Screws to the carrier. |
| halo_ring | 1 | translucent PETG/ASA (natural/white) | shoulder down | Visible glowing ring r 44.3–51.7. |
| face_disc | 1 | ASA black | back down | Mickey outline cut through (4 small bridges at the back) + 7 × D2 speaker holes. |
| face_disc_blank | (1) | ASA black | back down | Same face without the logo – use this one if you share the model (Mickey is a Disney trademark). |
| mickey_inlay | 1 | translucent PETG/ASA | front down | Press-fit (0.08 mm/side) + a drop of CA. For AMS: load face_disc + mickey_inlay together as one multi-part object. Swap `LOGO` in `magicband.py` for your own icon. |
| neck | 1 | ASA (dark) | base down | Flared cup hugs the ball. 3 inserts top, 3 inserts bottom. |
| arm_base | 1 | ASA (dark) | base down | Neck boss + bar + pod in one piece (231 mm). Cable channel 16 × 10 + 50° roof. |
| pod_cap | 1 | ASA (dark) | top face down | 30° sloped top, oval funnel 32 × 46 → R503 (M25 nut from inside). |
| wall_bracket | 1 | ASA (dark) | wall side down | Plate 80 × 122, shelf under the arm, 30° cable bore into the wall + V-groove for a surface-run cable, drip slope on top. |
| controller_box | 1 | PETG | floor down | Indoor. ESP32 DevKit, relay, MAX3485, buck, 12 V terminals. 2 × PG7 gland holes, DC-jack hole, 2 countersunk wall holes. |
| controller_lid | 1 | PETG | top down | 4 × M3. |
| face_gasket | 1 | TPU 95A | flat | halo ↔ ball_front collar |
| seam_gasket | 1 | TPU 95A | flat | ball_front ↔ ball_rear |
| hatch_gasket | 1 | TPU 95A | flat | Full face, also seals the hatch screw holes |
| neck_gasket | 1 | TPU 95A | flat | ball flat ↔ neck |
| neck_base_gasket | 1 | TPU 95A | flat | neck ↔ arm boss |
| pod_gasket | 1 | TPU 95A | flat | pod rim ↔ pod_cap (pads seal the screw holes) |
| r503_washer | 1 | TPU 95A | flat | Under the R503 nut, seals the sensor thread |
| bracket_gasket | 1 | TPU 95A | flat | bracket ↔ wall |

All gaskets are 1.5 mm thick and sit in 1.0 mm gaps (0.5 mm = 33 % compression).

Print notes: ASA at 4 walls / 25 % gyroid for the outdoor parts; the ball halves with 3 mm shell
are printed solid by the walls. Sand / prime / paint the ball silver (or use silk-silver ASA) for
the brushed-metal look. The teardrop/diamond tops on horizontal holes are deliberate (no supports).

## Hardware

| Item | Qty | Where |
|---|---|---|
| M3 heat-set insert (Ø4.0 hole, e.g. M3 × 5.7 × 4.6) | 4 + 4 + 6 + 4 + 3 + 4 = 25 | ball_front seam bosses, ball_rear hatch lugs, neck (3 top + 3 bottom), arm bar underside, pod columns, controller box |
| M3 × 12 socket head | 4 | seam: ball_rear lug → carrier tab → ball_front boss |
| M3 × 10 pan head (stainless) | 4 | rear_hatch |
| M3 × 12 socket head | 3 | ball pad → neck (from inside the ball) |
| M3 × 12 socket head | 3 | arm boss → neck (from below) |
| M3 × 16 socket head | 4 | wall_bracket shelf → arm_base (from below) |
| M3 × 16 pan head (stainless) | 3 | pod_cap → pod columns |
| M3 × 8 pan head | 2 | electronics_tray → face_carrier (self-tapping into the carrier bosses) |
| M2.5 × 6 self-tapping | 4 | PN532 on the standoffs |
| M2.5 × 6 self-tapping + washer | 3 | speaker frame clamp |
| 4 × 40 countersunk wood/plug screw | 4 | wall plate (+ plugs) |
| M3 × 8 pan head | 4 | controller lid |
| PG7 cable gland | 2 | controller box |
| Micro switch ~12.8 × 5.8 × 6.5 (plunger Ø2.4) | 1 | tamper switch in ball_rear |
| WS2812B 144/m, **42 LEDs** (292 mm), IP65 silicone-coated recommended | 1 | carrier ring |
| GROW R503 + its M25 nut | 1 | pod_cap |

## Assembly order

1. Press the inserts (ball_front, ball_rear, neck, arm_base underside + pod columns, controller box).
2. Face: press the inlay into face_disc (or print AMS). Put the halo ring face-down on the bench, drop the
   disc in from behind, run a thin bead of clear silicone on the disc/halo cone.
3. Ball_front face-down: lay the face_gasket on the collar seat, put the halo/disc stack in from behind.
4. face_carrier: stick the LED ring in the channel (feed wire through the hole at the bottom), screw
   the PN532 (antenna side toward the face) on the standoffs, clamp the speaker on the back of the
   carrier (seal its rim to the carrier with foam tape). Lay the carrier onto the halo – the 4 tabs sit
   under the ball_front bosses.
5. Screw the electronics_tray to the carrier, fit the boards, wire them.
6. Lay the seam_gasket on the ball_rear rim, fit ball_rear (lugs over the carrier tabs), drive the 4
   seam screws through the rear opening. This also clamps the carrier onto the halo/face gasket.
7. Fit the tamper switch into its pocket in ball_rear (plunger through the hole toward the hatch).
8. Arm: pull the R503 cable and the 4-core cable through the arm channel, neck bore and ball bottom
   hole. Mount the neck on the arm boss (neck_base_gasket, 3 screws from below), then the ball on the
   neck (neck_gasket, 3 screws from inside the ball through the rear opening).
9. Pod: R503 through the pod_cap funnel, r503_washer + nut from inside; pod_gasket, cap screws.
10. Hatch: hatch_gasket, rear_hatch (4 pan heads) – the nub closes the tamper switch.
11. Wall: drill the cable hole (exits the plate back at the bore, ~30 mm below the shelf top),
    bracket_gasket, screw the plate. Feed the 4-core cable through the bore (or down the V-groove),
    then fix the head assembly onto the shelf with 4 screws from below.
    Service = remove those 4 screws and take the whole head to the bench (the hatch faces the wall).

## Layout numbers (from the script)

- Ball D150, centre 53 mm from the wall, hatch back 15 mm off the wall; face plane 103 mm from the wall.
- PN532 antenna face → outer face surface: **9.0 mm**.
- Pod axis 165 mm from the neck axis; pod top centre 95 mm above the arm bottom, tilted 30°.
- Cable path: min section 113 mm² (D12 arm floor hole / bracket bore); arm channel 236 mm²,
  ball bottom hole 169 mm², neck bore 201 mm². A 6 mm probe passes pod → ball and ball → wall.
