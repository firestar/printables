# Card scanner + penny-sleever – physical feasibility audit

Audit date 2026-11-01. Checks the CAD parameters (`cad/card_scanner.py`), the firmware defaults
(`firmware/lib/cs_motion/src/cs_settings.h`, `firmware/include/config.h`) and the wiring
(`electronics/WIRING.md`) against datasheet numbers. Nothing has been tested on hardware.

Verdicts: **OK** = works as designed. **FIXED** = an error, corrected in this audit. **RISK** = works on
paper but has small margin, or needs a redesign that is too big for this audit (a fix is recommended).

## Summary

| # | Item | Verdict | One line |
|---|---|---|---|
| 1.1 | CM3 focus / FOV | OK | 66° × 41°, 10 cm min focus; WD 100 mm frames 129.9 × 74.8 mm |
| 1.2 | Resolution | OK | 35.5 px/mm; 1.5 mm text ≈ 53 px tall; pHash needs < 1 px/mm |
| 1.3 | Cross-polarization | OK / FIXED (doc) | Needed: glass glare lands at ±18 mm in the image. Both rings are on together, so both LED films must share one orientation (assembly note added). Foils go dark under crossed polarizers |
| 1.4 | 2 mm glass at 100 mm | OK | Focus shift 0.68 mm < DoF ±2.2 mm |
| 2.1 | Sleeve thickness / gate | **FIXED** | Penny ply 45 µm (0.09 total). Old 0.25 mm gate passed 2 sleeves (0.18). Now 0.14 mm |
| 2.1b | Sleeve outline | **FIXED** | Ultra Pro penny is 66.7 × 92.1; the magazine (91.5 inner) was 0.6 mm short. `SL_MAX` 92.1, `SW_MAX` 66.7 |
| 2.2 | Platen hold vs. peel | OK | 59 holes, 66.7 mm² → 2.7–4.0 N at 40–60 kPa vs. ≈ 3 mN ply load |
| 2.3 | 10 mm cup on 45 µm PP | OK | ≈ 1.5 N at 40 kPa; PP film is airtight |
| 2.4 | Top-ply lift clears shims | **FIXED** | Cup was 42.5 mm from the mouth (≈ 14 mm free-ply sag). Now `CUP_X` 22 (tips +15 + R5 + 2), `LIFT` 5.5 → mouth edge ≥ 4.4 mm |
| 2.5 | Card vs. 1.5 mm/side throat | OK | 0.30–0.33 mm card + 0.5 mm curl ≪ 3.3 mm throat |
| 2.6 | Insertion friction vs. nip | OK | ≈ 5–100 mN vs. ≈ 1.8–3.5 N traction; card buckles at ≈ 4.3 N |
| 2.7 | Pawl seat (MG90S) | OK | ≈ 7.6 N at the crank pin; seat needs < 0.1 N; offset crank gives 56.8 mm stroke |
| 2.8 | `sleeve_present` placement | **FIXED** | At (6, +26) it tripped ~11 mm after the sleeve left the magazine, 60 mm short of the fence. Moved to (30, −30) + new `sleeve_push_ms` |
| 3.1 | Nip pitch | OK | 80–82 mm < 86 mm shortest card |
| 3.2 | O-ring pinch / slip | OK / RISK | Keep the spring preload ≤ 1 mm (≈ 2.2 N pinch) so traction stays under the 4.3 N buckling load |
| 3.3 | 1 mm glass gap | OK / RISK | 0.3 + 0.5 curl = 0.8 mm fits; foils with > 0.7 mm curl will jam |
| 3.4 | Diverter tray 25° | OK / RISK | tan 25° = 0.47 > μs ≈ 0.25–0.35 (PP / PETG); static can stick |
| 3.5 | Diverter angles | **FIXED** | Firmware drove the tray to ±60° (30/150); bins are at ±42° → 48/90/132 |
| 3.6 | Bins stack flat | RISK | 64 mm first drop at ≈ 0.6 m/s; 5 mm length slack; cards may lean |
| 3.7 | `eject_reject` distance | **FIXED** | 140 mm left the card in front of the pawl; needs 232 mm → 240 |
| 3.8 | Feed steps/mm | **FIXED** | Roller is Ø28 (D26 hub + 2 mm cord), not Ø22: 36.4 steps/mm, not 46.3 |
| 3.9 | `insert_max_mm` | **FIXED** | Scan stop → mouth sensor is 168 mm > 160 default (hidden by the steps/mm error) → 200 |
| 4.1 | Elevator T8 + NEMA17 | OK / FIXED (doc) | 11 mN·m needed vs. ≈ 190 mN·m; lead 8 is not self-locking (doc corrected) but detent holds |
| 4.2 | 20 mm pick cup | OK | ≈ 8 N vs. 18 mN card; coated card stock does not let a second card be sucked |
| 4.3 | Stack puff | RISK | ≈ 47 m/s jet, but the pump starts with the valve: only ~100 of 150 ms is useful |
| 4.4 | Pick stroke / tongue stroke | **FIXED** | Firmware 45 / 22 mm vs. CAD 30 / 18 mm |
| 5.1 | Pump vs. dead volume | OK | ≈ 0.35 s to 25 kPa on the platen path (30 cm³) |
| 5.2 | Valve release | **FIXED** (BOM) | 2-way NC valves trap the cup vacuum: card/sleeve never released. Vacuum valves must be 3/2-way |
| 5.3 | Valve response | OK | ≤ 20 ms |
| 5.4 | 12 V current | OK | ≈ 2.2 A worst sleeve phase + 2 A pump start; 8 A buck |
| 5.5 | Vacuum sensor + divider | OK | 0.33–3.0 V at GPIO1, inside the ESP32-S3 12 dB range (0–3.1 V) |
| 6.1 | Power budget / PSU | OK / FIXED | Peak ≈ 5.7 A of 6.5 A (LRS-150-24). CAD BOM said LRS-100-24 (4.5 A, too small) – corrected, plate B re-laid for 159 mm |
| 6.2 | Bucks / fuses | OK | Pi 1.2 A, servos 0.64 A at 24 V peak |
| 6.3 | ESP32-S3 pins | OK | No strapping, USB, flash/PSRAM or UART0 pins used; ADC on ADC1 |
| 6.4 | TMC2209 UART | OK | 1 kΩ TX + direct RX, MS1/MS2 = AD0/AD1, `mstep_reg_select` set |
| 6.5 | MCP23017 timing | OK | ≈ 125 µs per read, 1 ms poll; `scan_stop`, `sleeve_mouth` on native GPIO |
| 6.6 | 3.3 V TCRT5000 | OK | LM393 runs at 3.3 V; IR LED current drops to ~20 mA (shorter range) |
| 7.1 | STLs fit 256 | OK | Largest 240 × 150 (plates), 221 × 220 (deck), 187 tall (pick bridge) |
| 7.2 | PETG creep | OK | Spring stress < 1 MPa; motors < 50 °C vs. Tg 80 °C |
| 7.3 | Belt lengths | RISK | Belt paths are not modelled; buy 2 m open belt for the feed loop |
| 7.4 | 2020 lengths | OK | 925 / 390 / 576 / 65 / 510 all match the frame |
| 7.5 | Throughput 6–10/min | **FIXED** (doc) / RISK | Defaults sum to ≈ 10.7 s → 5.6 cards/min |

## 1. Optics

Sources: Raspberry Pi Camera Module 3 product brief
(<https://datasheets.raspberrypi.com/camera/camera-module-3-product-brief.pdf>): Sony IMX708,
4608 × 2592, 1.4 µm pixels, standard lens f = 4.74 mm, F1.8, FoV 66° H × 41° V (75° diagonal), focus
10 cm – ∞. (The raspberrypi.com doc pages were Cloudflare-blocked during the audit; the numbers are the
published product-brief values.)

**Field at WD = 100 mm:** 2 · 100 · tan 33° = **129.9 mm** (H) × 2 · 100 · tan 20.5° = **74.8 mm** (V).
The card (88 × 63) has 21 mm / 5.9 mm margin per side. The CAD takes WD = max(70.1, 88.3, 100) = 100,
so it is limited by the minimum focus, not the framing. **OK.**

**Resolution:** 4608 / 129.9 = **35.5 px/mm** (H), 2592 / 74.8 = 34.7 px/mm (V), ≈ 900 dpi.
- pHash works on a 32 × 32 (or 64 × 64) downscale of the art box. Any value > 1 px/mm is enough.
- Set symbol / collector number text ≈ 1.5 mm tall → 53 px tall. Tesseract-class OCR wants ≥ 20–30 px
  cap height. ≈ 2× margin. **OK.**

**Depth of field:** c = 2 px = 2.8 µm. H = f²/(N·c) + f = 4.74² / (1.8 × 0.0028) ≈ 4.46 m.
Near / far at 100 mm: 100 · H / (H ± 100) = **97.8 / 102.3 mm** → ±2.2 mm.

**Glass:** a plane plate of thickness t moves the image by t(1 − 1/n) = 2 × (1 − 1/1.52) = **0.68 mm**
(both cameras see the card through one 2 mm plate). That is inside the ±2.2 mm DoF, and AF can take it
out. The apparent distance (99.3 mm) is right at the 10 cm spec; if AF hunts, use a fixed
`LensPosition` ≈ 10 dioptres. **OK.**

**Reflections / cross-polarization.** LED frames are 45 mm from the card, their window edge is ≥ 26 mm
off-axis, the lens is 100 mm away. The mirror image of the LED in the glass is 45 mm below the surface,
so the specular ray from the lens hits the glass 26 × 100 / (100 + 45) = **17.9 mm** off-axis. That is
inside the card image: without polarizers, each of the 4 glass surfaces (≈ 0.5 % each with AR, 4 %
without) plus the card gloss puts a hot spot on the card. Specular reflection keeps the polarization,
diffuse reflection off the print scrambles it, so crossed polarizers (light film ⟂ lens film) remove
the glare. **The layout is valid.**
- `machine.py` turns both rings on and captures front + back together. The glass (118 mm) is longer
  than the card (88 mm), so each ring shines straight through the open glass at the card ends into the
  opposite camera. If both LED films have the same world orientation, each lens is crossed to both
  rings. **FIXED (doc):** added to the `cad/README.md` assembly step 6.
- Metallic foil reflects specularly and also goes dark under crossed polarizers. Foil cards will image
  darker; pHash still works on the art, but foil detection from the image would not (the host sets foil
  per batch anyway).

## 2. Sleeves

Sources: Ultra PRO support, "How thick are the materials used to make sleeves?"
(<https://support.ultrapro.com/en-US/how-thick-are-the-materials-used-to-make-sleeves-380650>):
**Penny Sleeves 45 µm, front and back.** Size 2-5/8 × 3-5/8 in = **66.7 × 92.1 mm**
(<https://ultrapro.com/products/100ct-penny-sleeves-2-5-x-3-5-soft-trading-card-protectors>,
<https://cardfitlab.com/sleeves/ultra-pro-penny-sleeve>). Other brands are 40–60 µm per ply.

**Gate.** One sleeve = 2 × 0.045 = 0.09 mm, two = 0.18 mm, three = 0.27 mm. The old 0.25 mm gate
passes two sleeves, and the code comment assumed 0.12 per sleeve. A one-sleeve gate needs
0.09 < gap < 0.18; take 1.5× → **0.14 mm** (for 60 µm sleeves 0.12 mm per sleeve: 1.17×, still a
one-sleeve gate). **FIXED:** `GATE_GAP` 0.14, `PLY` 0.045. The gate slots have ±3 mm of travel, so the
printed parts adjust either way. Measure your sleeve brand with a micrometer and set 1.5×.

**Outline.** The magazine inner length was `SL_MAX + 0.5` = 91.5 mm < 92.1 mm sleeve. **FIXED:**
standard sleeve 66.7 × 92.1, `SW_MAX`/`SL_MAX` 66.7/92.1 (magazine inner 92.6 × 70.3).
`MAG_SENS_X` now follows `SL_MAX`. The small (Yu-Gi-Oh) sleeve size was not verified.

**Platen hold.** Holes Ø1.2 on a 6 mm grid, x 6…78 (13) × y −18…6 (5) = 65, minus 6 at the pawl
groove = **59 holes**, 59 × π × 0.6² = **66.7 mm²**. Pump vacuum −40 / −60 kPa → **2.7 / 4.0 N** holding
the bottom ply down. The lift cup only has to carry the top ply: 66.7 × 92.1 × 0.045 mm × 0.905 g/cm³ =
0.25 g → **2.5 mN**, plus bending (D = E t³/12 = 1.5 GPa × (45 µm)³ / 12 = 1.1 × 10⁻⁵ N·m, negligible).
The platen does not see a meaningful peel load. **OK.**

**10 mm lift cup.** Effective sealing Ø ≈ 7 mm → 38 mm² × 40 kPa = **1.5 N** ≫ 2.5 mN. PP film is
gas-tight at this scale, so the cup seals on one ply and does not pull the bottom ply through. **OK.**

**Lift height (FIXED).** Upper shim top = 0.045 + 0.3 + 1.5 + 0.3 + 1.5 + 0.3 = 3.95 mm. The old cup
at x = 42.5 (S) lifted 4.5 mm, but the tongues enter at x 0…15: as a free cantilever a 45 µm PP ply
sags q L⁴ / 8D = 0.40 N/m² × 0.0425⁴ / (8 × 1.1 × 10⁻⁵) ≈ 14 mm over 42.5 mm, so the cup alone could not
hold the mouth edge up.
*Fix:* the cup moves as close to the mouth as the tongues allow: tips at +15, cup lip R5, 2 mm margin →
**`CUP_X` = 22** (y −12, beside the pusher post/fork at y ±4, over the platen holes at x 18/24 so the
bottom ply is held right under it; clear of the mouth sensor (6, −26) and `sleeve_present` (30, −30)).
The lift arm keeps its hub on the MG90S horn (x 41…44) and gets a 9 × 6 mm finger along −x to the cup;
the finger is parallel to the servo axis, so the lever (48 mm) and the servo load do not change.
Sag to the mouth, conservatively from the cup centre (L = 22 mm): 0.40 × 0.022⁴ / 8.8 × 10⁻⁵ =
**1.1 mm** (0.4 mm from the cup lip, L = 17). With `LIFT` 4.5 the edge would be 3.4 mm (< 4), so
**`LIFT` → 5.5**: mouth edge ≥ **4.4 mm** at x = 0, 0.45 mm over the upper shim top (MG90S: 6.5° at
48 mm). The sleeve perimeter (≈ 133 mm) is far more than the shim stack needs (2 × 40 + 2 × 3.9 = 88 mm).
Residual: this is the strip under the cup (y ≈ −12); the far +y corner of the mouth still relies on
the rounded shim tips and the mouth jet (rig check).

**Card in the throat.** MTG ≈ 0.30–0.31 mm, Pokémon ≈ 0.31–0.33 mm; with 0.5 mm curl ≤ 0.83 mm vs. a
3.3 mm gap between the shims (1.5 per side). **OK.**

**Insertion friction vs. nip.** The card (1.8 g) slides on the bottom ply under the top ply:
μ ≈ 0.3 × 18 mN ≈ 5 mN, plus edge drag, < 0.1 N total. Nip traction (see 3.2) ≈ 1.8–3.5 N → ≥ 18×.
Euler buckling of the 18 mm free length between the entry nip and the mouth, as a cantilever:
P = π² E I / (4 L²), E ≈ 4 GPa, I = 63 × 0.3³ / 12 = 0.14 mm⁴ → **4.3 N**. The nip slips before the
card buckles as long as traction < 4.3 N. **OK** (keep the spring preload low, see 3.2).

**Pawl seat (MG90S).** TowerPro MG90S: 1.8 kgf·cm at 4.8 V, 2.2 kgf·cm at 6 V
(<https://www.towerpro.com.tw/product/mg90s-3/>) → ≈ 0.18 N·m at 5 V. Crank r 24 → **7.6 N** at the crank
pin. Offset slider-crank (offset e = 40, L 80, r 24): stroke = √((L+r)² − e²) − √((L−r)² − e²) =
96.0 − 39.2 = **56.8 mm** ≥ 56 needed; the crank sweeps 180° − (asin(e/(L−r)) − asin(e/(L+r))) ≈ 157°
between the extremes, within the servo's ~180°. Seating the card the last 12 mm needs < 0.1 N. **OK.**
Tune `pusher_out_deg` on the rig: the last mm of stroke sits near a dead centre.

**`sleeve_present` (FIXED, firmware + CAD).** The sleeve slides −y from the magazine (leading edge at
y ≈ +37) to the fence (y −33.85). A sensor at (6, +26) is covered after only ~11 mm of travel and stays
covered to the end, so the firmware braked the N20 with the sleeve ~60 mm short of the fence; the
platen holes (y −18…6) stay uncovered and every pick fails with `sleeve_open_fail`.
Fix: sensor moved to **(30, −30)** (the M3 insert at (20, −30) and the fence ledges at x 6…14 are clear).
It trips 1.5 mm (62 mm sleeve) to 3.4 mm (66.7 mm sleeve) before the fence. New setting
**`sleeve_push_ms` = 60** keeps the wheels running after the trip: the N20 at 5 V moves the sleeve at
≈ π × 20 × 250 rpm / 60 ≈ 260 mm/s, so 60 ms ≈ 16 mm, then the wheels slip on the sleeve at the fence
(N20 stall ≈ 0.5 A for ≤ 60 ms). Without this the sleeve stops off-centre in y and the card hits the side
seam.

## 3. Card path

**Nip pitch:** feed 66 → scan-in 146 → scan-out 228 → xfer 308 → entry 388 = 80 / 82 / 80 / 80 mm,
all < 86 mm. At `scan_stop` (edge 244) the card spans 156…244 (158…244 small) and is held by the 228
nip. Pick hand-off: edge 44 + 30 stroke = 74, 8 mm past the 66 nip. **OK.**

**O-ring pinch / slip.** Ø5 × 10 spring, 0.5 mm wire, 6 active turns:
k = G d⁴ / (8 D³ n) = 79 GPa × 0.5⁴ / (8 × 4.5³ × 6) ≈ **1.1 N/mm**. Two blocks per nip:
- 2 mm preload → 4.4 N pinch, traction μ 0.8 → 3.5 N, close to the 4.3 N buckling load;
- 1 mm preload → 2.2 N pinch, 1.8 N traction.
**RISK (tuning):** set ≤ 1 mm preload; the slip margin over the ≤ 0.1 N insertion drag is still ≥ 18×.

**Glass gap.** 1.0 mm gap; 0.30 card + 0.5 mm curl = 0.80 mm passes. Heavily curled foils (> 0.7 mm)
jam at the glass lead-in. A 1.5 mm gap would still keep the card inside the ±2.2 mm DoF if foils
jam. Sleeved cards never enter the glass (sleeving is after the scan). **OK / RISK for curled foils.**

**Diverter tray 25°.** Sliding needs tan θ > μs: tan 25° = **0.47**. Plastic-on-plastic static friction
for PP film on PETG ≈ 0.25–0.35 (no published pair value; the CAD comment assumes 17°, i.e. μ 0.31).
Margin ≈ 1.3–1.9×. Bare (rejected) cards, paper on PETG μs ≈ 0.3–0.4, are marginal. Triboelectric
charge (PP vs. PETG) adds adhesion. **OK / RISK:** ground the tray or add PTFE tape if cards hang.

**Diverter angles (FIXED).** The tray sits directly on the servo spline and the bins are at
`DIV_ANGS` = −42 / 0 / +42°. The defaults 30 / 90 / 150 swing ±60° and miss the outer bins.
Now **48 / 90 / 132**. (The stale `DIV_ANG = ±30` / `BIN_R` constants at the top of the CAD file are
unused.)

**Bins.** Tray end z ≈ 70, bin floor z 6 → 64 mm first drop. Slide speed off the 120 mm tray:
a = g (sin 25° − 0.3 cos 25°) = 1.5 m/s² → v ≈ 0.6 m/s; fall time 0.11 s → ≈ 70 mm forward. The card
tips over the tray end and lands against the far wall; with 97 mm inner length vs. 92.1 mm, it ends
roughly flat but may lean on the first few cards. **RISK:** a bin floor sloped 10° back toward the
tray, or a foam pad, would help.

**`eject_reject` (FIXED).** The card must leave the sleeve entry nip (S −18, world 388) with its
trailing edge, so the gravity pawl (rest S −20) drops behind it: trailing edge 156 → 388 = **232 mm**.
140 mm left the card in front of the pawl, which then cannot push it into the exit nip
(exit_timeout every time). Now `reject_mm` = 240 (the card stops by itself once it leaves the nip).
A bare card pushed to S +36 has its leading edge at +124, 4 mm into the exit nip at +120 (small card
2 mm). OK.

**Feed steps/mm (FIXED).** Hub D26 + 2 mm cord in a 1 mm groove → Ø28 (`R_ROLL` = 14); GT2 20T:20T
1:1. 3200 / (π × 28) = **36.4 steps/mm**, not 46.3 (that assumed Ø22: every feed distance was 27 %
long). Calibrate on the machine (cord compression makes it slightly smaller).

**`insert_max_mm` (FIXED).** Scan stop (leading edge 244) → `sleeve_mouth` window (S 6 = world 412) =
**168 mm** > 160 default; the old steps/mm error made it travel 204 mm and hid this. Now 200. With
`insert_mm` = 70 the leading edge stops at S 76, trailing edge S −12, past the nip (−18) and past the
pawl (−20). OK.

## 4. Hopper

**Elevator.** 250 cards × 1.8 g + platform ≈ 0.5 kg → F = 4.9 N. T8 lead 8 (4-start, d₂ ≈ 7 mm, lead
angle λ = atan(8 / (π·7.6)) ≈ 18.6°), brass nut μ ≈ 0.2 (φ ≈ 11.3°): η = tan λ / tan(λ + φ) ≈ 0.58.
Raise torque T = F L / (2π η) = 4.9 × 0.008 / (2π × 0.58) = **11 mN·m**. 17HS4401: 0.40 N·m at 1.7 A
→ ≈ 0.19 N·m at 0.8 A, and at 6 mm/s (45 rpm) the torque is still near holding → ≥ 15×. **OK.**
λ > φ, so lead 8 is **not** self-locking (WIRING.md said it was): back-drive torque
F L η' / 2π ≈ 4.9 × 0.008 × 0.38 / 2π = 2.4 mN·m, below the motor detent (≈ 15–20 mN·m for this
class). When K1 drops VM the stack still does not sink. **FIXED (doc).**

**20 mm pick cup.** Effective Ø ≈ 16 → 200 mm² × 40 kPa = **8 N** ≫ 18 mN card. Card faces are coated;
the leak through one card is far below the pump flow, so the cup cannot pull a second card through the
first. Doubles come from friction/static/burrs: that is what the puff and the double-feed gauge are for.
A bellows cup lifts the card 2–4 mm on grip, which clears the front wall (top 1 mm under the track
plane); stack-top sensing (TCRT5000, ±1 mm) alone would not. **OK.**

**Stack puff.** Ø1.5 nozzle, 370-type pump ≈ 3 L/min (5 × 10⁻⁵ m³/s): v = Q / (Cd A) =
5 × 10⁻⁵ / (0.6 × 1.77 × 10⁻⁶) ≈ **47 m/s**, ≈ 1.3 kPa dynamic pressure, jet core ≈ 6 d = 9 mm. Enough to
fan the top cards at the edge if the nozzle is within ~10 mm. The pump starts together with the valve
(`startPuff`) and needs ~50–100 ms to spin up, so only ~50–100 of the 150 ms are useful.
**RISK:** raise `puff_ms` to ≈ 250 or start the pump earlier.

**Pick / tongue strokes (FIXED).** CAD: pick stroke 30 mm, tongue stroke 18 mm (tips −3 → +15).
Firmware defaults were 45 / 22. Now 30 / 18. The sim's `nipAt` was 40 (a 30 mm stroke dropped the card);
now 22 = the real 66 − 44.

## 5. Pneumatics

**Dead volume / flow.** Platen path: plenum 74 × 30 × 6 = 13.3 cm³ + ~3 m of Ø2.5 mm ID tube 14.7 cm³ +
manifold ≈ **30 cm³**. Pump (12 V 370-type, ≥ 60 kPa) ≈ 3 L/min free, ≈ 25 cm³/s average while pulling
down. t = V/Q · ln(p₀/p): to 25 kPa (grip) 30/25 × ln(101/76) = **0.34 s**; to 50 kPa 0.83 s. The pick
cup path (no plenum) is about half. Inside `vac_timeout_ms` 1500 and close to `cup_dwell_ms` 250.
**OK.**

**Valve release (FIXED, BOM spec).** With a 2-port NC valve, closing it traps the vacuum between the
valve and the cup: the pick cup keeps the card (the arm then drags it back out of the nip), and the
platen keeps the sleeve (sort cannot push it). The diaphragm pump's check valves do not vent it either.
The 3 vacuum valves must be **3/2-way NC** (common → cup, NC → manifold, NO → atmosphere), so the cup
vents when the coil drops. The 2 air valves stay 2-way. (Alternative: a Ø0.3 mm bleed per cup, which
costs pump flow and grip.)

**Valve response.** 0520-class mini solenoid valves: ≤ 20 ms open/close. Small next to the 250 ms dwell.
**OK.**

**12 V current.** Pump 0.4–0.8 A (2 A start), air pump 0.3–0.6 A, valves 0.15–0.25 A each, LED rings
0.3–0.5 A each. Worst overlap is the sleeve job (lights are off by then): vac pump + platen + lift cup
+ air pump + mouth jet ≈ 0.8 + 0.25 + 0.25 + 0.6 + 0.25 = **2.2 A**, + 2 A pump start transient. During
capture: LEDs 1.0 A + nothing else. 8 A buck (realistic 5 A for an XL4016). **OK.**

**Vacuum sensor + divider.** XGZP6847A100KPGN (CFSensor, <https://cfsensor.com/product/xgzp6847a/>):
−100…0 kPa, 5 V supply, 0.5 V at −100 kPa, 4.5 V at 0 kPa. 10 k / 20 k divider (× 2/3): **3.0 V** ambient,
0.33 V at −100 kPa; the working range (−25…−60 kPa) is 1.4–2.4 V at the pin. ESP32-S3 ADC at 12 dB
(`ADC_11db`) measures ≈ 0–3.1 V
(<https://docs.espressif.com/projects/esp-idf/en/latest/esp32s3/api-reference/peripherals/adc_oneshot.html>);
ambient sits near the top (non-linear zone), which only affects the "0 kPa" reading. A sensor output
over 4.65 V (≥ 3.1 V at the pin) still stays far below the 3.6 V pin limit. Source impedance 6.7 kΩ
with 100 nF is fine for a 2 ms sample. **OK.**

## 6. Electrical

Sources: Mean Well LRS-150 spec (<https://www.meanwell.com/Upload/PDF/LRS-150/LRS-150-SPEC.PDF>:
24 V 6.5 A, 159 × 97 × 30 mm), LRS-100 (<https://www.meanwell.com/Upload/PDF/LRS-100/LRS-100-SPEC.PDF>:
24 V 4.5 A, 129 × 97 × 30 mm), Raspberry Pi 5 power (5 V 5 A max with USB peripherals).

**Budget at 24 V (peak, all at once):**

| Load | At its rail | 24 V draw |
|---|---|---|
| Pi 5 + 2 × CM3 + ESP32 (via USB) + vac sensor | 5 V × 5 A = 25 W (typ. 10–12 W) | 25 / 0.9 = 27.8 W → **1.16 A** |
| 4 steppers (copper loss 2 I² R: 1.9 + 1.7 + 1.7 + 1.8 W, + mechanics) | ≈ 11 W typ. | conservatively **2.0 A** peak, 0.5–1.0 A typ. |
| 12 V branch (pumps, valves, LEDs, start surge) | 12 V × 3.5 A = 42 W | 42 / 0.9 = 47 W → **1.94 A** |
| 3 × MG90S stall (≈ 0.7 A each) + N20 stall 0.5 A | 5 V × 2.6 A = 13 W | 13 / 0.85 = 15.3 W → **0.64 A** |
| **Total** | | **≈ 5.7 A (138 W) peak, ≈ 2.6 A typical** |

The LRS-150-24 (6.5 A) covers the peak with 12 % margin; the peak needs simultaneous servo stall, pump
start and full Pi load, which the sequence never does. **OK.** The CAD BOM and plate B listed an
**LRS-100-24 (4.5 A) footprint**, which would not cover the peak. **FIXED:** CAD BOM →
LRS-150-24, plate B stand-in 159 × 97 × 30, pumps / manifold / sensor moved to the right column and the
plate-B wire slot moved to local (195…235, 100…107) so no standoff floats in it.

**Bucks / fuses.** Pi buck 5 A (D36V50F5), 1.16 A in → F1 3 A (use slow-blow for the input-cap inrush).
12 V buck in 1.94 A → F3 4 A. Servo buck 3 A out (2.6 A stall peak), 0.64 A in → F4 1 A. F0 8 A > PSU
max. Set `PSU_MAX_CURRENT=5000` on the Pi (no USB-PD from a buck). **OK.**

**ESP32-S3-DevKitC-1 pins** (ESP32-S3 datasheet
<https://www.espressif.com/sites/default/files/documentation/esp32-s3_datasheet_en.pdf>, DevKitC-1 guide
<https://docs.espressif.com/projects/esp-dev-kits/en/latest/esp32s3/esp32-s3-devkitc-1/user_guide.html>):
- Strapping 0 / 3 / 45 / 46: unused. GPIO8 (EN pull-up) is not a strapping pin.
- USB 19 / 20: the host link only. UART0 43 / 44: unused.
- SPI flash 26–32 and octal PSRAM 33–37 (N8R8): unused.
- GPIO 39–42 are the JTAG pins; with the default USB-Serial-JTAG they are free GPIOs.
- GPIO47: 3.3 V on N8 / N8R8 / N16R8 (1.8 V only on the R8V octal-flash parts – WIRING.md says so).
- GPIO1 = ADC1_CH0. ADC2 (GPIO 11–20) conflicts with Wi-Fi, ADC1 does not, and no ADC2 pin is used as
  analog. GPIO2 (ADC1_CH1) is a digital input.
- 23 pins used = 45 GPIOs − 4 strapping − 2 USB − 2 UART0 − 12 flash/PSRAM − 1 RGB LED − 1 spare
  (38 or 48, whichever has no LED). **OK.**

**TMC2209 UART** (<https://www.analog.com/media/en/technical-documentation/data-sheets/TMC2209_datasheet_rev1.09.pdf>):
single-wire PDN_UART, TX through 1 kΩ, RX direct; MS1 = AD0, MS2 = AD1 → addresses 0–3 as wired
(#1 pick = MS1 H = 1, #2 feed = MS2 H = 2). `hal_esp32.cpp` sets `pdn_disable`, `mstep_reg_select`
(so MS1/MS2 are only the address) and `I_scale_analog(false)`. **OK.**

**MCP23017 timing** (<https://ww1.microchip.com/downloads/aemDocuments/documents/APID/ProductDocuments/DataSheets/MCP23017-Data-Sheet-DS20001952.pdf>):
a 2-byte GPIO read is ≈ 50 bit times = **125 µs** at 400 kHz; polled every 1 ms → ≤ 1.1 ms latency.
Fast sensors are native: `scan_stop` GPIO41, `sleeve_mouth` GPIO42, `double_feed` GPIO2, e-stop GPIO47.
On the expander: `stack_top` (elevator at 6 mm/s → 7 µm per ms), `exit` (trip / clear only),
`sleeve_present` (N20 260 mm/s → 0.3 mm per ms, now followed by `sleeve_push_ms`). GPA7/GPB7 are
output-only on current silicon and are not used as inputs. **OK.**

**3.3 V TCRT5000 modules.** LM393 works from 2 V; the open-collector `DO` with its pull-up to the module
VCC (3.3 V) is ESP-safe. The IR LED current drops from ≈ 35 mA (5 V) to ≈ 20 mA → shorter range; the
under-platen windows (2–5 mm) are fine, re-tune the pots at 3.3 V. **OK.**

## 7. Mechanics

**Bed fit.** `card_scanner.py` exports every part in print orientation and checks it against
256 − 2 × 3 mm. Largest: `elec_plate_a/b` 240 × 150 × 10, `sleeve_deck` 221 × 220 × 8, `pick_bridge`
151 × 94 × 187, `hood` 146 × 150 × 143. All single watertight bodies. **OK** (see test results).

**PETG creep.** Roller pinch ≈ 1–2 N per spring on an M3 set screw in a heat-set insert: printed-part
stress < 1 MPa, far under PETG's creep threshold (~10 MPa at room temperature). Steppers at 0.5–0.8 A
run < 50 °C, below PETG's Tg ≈ 80 °C. Re-check the pinch after the first week. **OK.**

**Belt lengths.** Feed loop: lower shafts at x 66…526 on −y + the motor at x 322, z 55 (≈ 56 mm below
the shafts): a straight loop is 2 × 460 + 2 × 56 + wraps ≈ 1.1 m; with the 3 F623 idlers for wrap angle
≈ 1.3–1.5 m. Pick ≈ 0.3 m and tongue ≈ 0.15 m are consistent with 30 / 18 mm strokes. The belt paths are
not modelled. **RISK:** buy a 2 m open GT2 belt and clamp the loop.

**2020 lengths.** Base rails 925 = 800 − (−125); cross members 390 = (175 − 20) − (−255 + 20); deck
rails 576 = 612 − 36; posts 65 = 85 − 20; electronics rails 510 = 500 − (−10). All match the BOM. **OK.**

**Throughput (firmware defaults, with this audit's fixes):**

| Step | Time |
|---|---|
| `feed`: elevator nudge 0.1, puff 0.15, grip 0.3, pick 30 mm @ 120 0.33, feed 170 mm @ 150 1.13 | 2.0 s |
| capture (lights, 2 stills, USB round trips) | ≈ 0.4 s |
| `sleeve`: pick 0.33, platen 0.4, lift down 0.35, grip 0.3, up 0.35, jet 0.12, tongue in 0.34, feed 238 mm @ 80 3.03, seat 0.75, tongue out 0.34, release 0.25 | 6.6 s |
| `sort`: divert 0.35, push + exit trip / clear ≈ 1.05, park 0.35 | 1.75 s |
| **Total** (recognition runs in parallel with `sleeve`) | **≈ 10.7 s → 5.6 cards/min** |

`feed` is refused while a sleeved card waits, so the steps cannot overlap. The 6–10 cards/min claim
does not hold at the defaults. **FIXED (doc):** top README now says 5–6/min. **RISK / recommendation:**
- run the scan → mouth part of the insert (≈ 158 mm) at `feed_speed`: −0.9 s;
- `servo_ms` 350 → 200 after tuning: −0.75 s;
- that gives ≈ 9 s → **6.7 cards/min**. 10/min would need the next card fed while the previous one
  sleeves, which the shared roller loop does not allow.

## Changes made in this audit

| File | Change |
|---|---|
| `cad/card_scanner.py` | `PLY` 0.06 → 0.045; `GATE_GAP` 0.25 → 0.14; standard sleeve 66 × 91 → 66.7 × 92.1, `SW_MAX`/`SL_MAX` → 66.7/92.1; `MAG_SENS_X` = `SL_MAX` + 3.6; `CUP_X` defined once (dead 28 removed), 42.5 → 22 with a finger on `lift_arm` (printed hub face down); `LIFT` 4.5 → 5.5; `SLEEVE_SENSOR` (6, 26) → (30, −30); plate B: PSU 159 × 97 (LRS-150-24), vac pump / air pump / manifold / sensor moved, wire slot moved |
| `firmware/include/config.h` | `STEPS_PER_MM_FEED` 46.3 → 36.4; `sleeve_present` comment |
| `firmware/lib/cs_motion/src/cs_settings.h/.cpp` | `pick_travel_mm` 45 → 30, `tongue_depth_mm` 22 → 18, `insert_max_mm` 160 → 200, `reject_mm` 140 → 240, `div0/2_deg` 30/150 → 48/132, new `sleeve_push_ms` = 60 (0–2000) |
| `firmware/lib/cs_motion/src/cs_scanner.cpp` | new phase `P_SLV_PICK_PUSH`: wheels run `sleeve_push_ms` after `sleeve_present`, then brake |
| `firmware/lib/cs_sim/src/cs_sim.h` | `nipAt` 40 → 22 (real hand-off distance) |
| `firmware/test/test_scanner/test_scanner.cpp` | `test_sleeve_pick_stops_at_sleeve_present` expects the push-on time |
| `firmware/PROTOCOL.md` | defaults table, `sleeve_push_ms` row, step 0 text |
| `electronics/WIRING.md` | `sleeve_present` position, 0.14 mm gate, 3/2-way vacuum valves (table + BOM), leadscrew self-lock note, feed steps/mm |
| `cad/README.md` | sleeve size, gate, `sleeve_present`, 3/2-way valves, LRS-150-24, polarizer orientation note; cup (22, −12), lift 5.5, `CUP_X` tuning note |
| `cad/anim/animate.html`, `cad/anim/README.md` | 0.14 mm gate text, `LIFT` 5.5 (video not re-rendered) |
| `README.md` | throughput 5–6 cards/min |

## Open risks (not fixed – redesign or rig tuning)

1. **Lift cup** – fixed (x 22, lift 5.5); verify on the rig that the far +y mouth corner opens.
2. **Throughput** – two-speed insert in firmware (fast to the mouth, slow inside the sleeve).
3. **`sleeve_mouth` empty-sleeve vs. card** (already in README) – a break-beam across the throat is
   more robust.
4. **Curled foils vs. the 1.0 mm glass gap** – go to 1.5 mm if they jam.
5. **Bin landing / tray static** – sloped bin floor, grounded tray / PTFE tape.
6. **Puff timing** – pump spin-up eats most of `puff_ms`.
7. **Belt paths** not modelled.
