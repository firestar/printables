# Gyroid Mist Shell (fogponic concept)

Four different pebble segments make the turning stack: fattest at the bottom,
slimmer and more domed toward the top (240 / 236 / 225 / 216 mm footprints).
The joints keep the classic spigot and socket, so the drop-in fit and the cap
are unchanged. Each joint pinches to a deep notch, so the stack reads as
stacked stones, not as a column.

Between the joints the closed 3.4 mm chamber wall bulges out by 7-14 mm in a
gently lobed plan. A log-polar gyroid sheet skin swells over it to the pebble
envelope:
- it rises at 44 deg or less off the notch,
- then forms a 3-lobed, twisting, slightly lopsided belly (up to r 121),
- then rounds off in a dome.

The cells grow with the radius (coarser coral outside), and the sheets thin from
2.6 to 2.1 mm. Each segment has nine 2" net-pot pockets (3 rows x 3) in the
lobe valleys. The valleys twist 40 deg per row, so the pockets form a
three-start helix (each segment twists the other way from the one below). Each
pocket's tube flares into the gyroid with a smooth blend, and its mouth sits
2 mm inside the local envelope as a cup. 4 x 9 = 36 plants. Height is 1260 mm
on the stand. The lattice is relief **outside** the solid wall, so fog and drip
stay in the chamber. The check script proves the wall is open only at the 36
bores.

Roots get **fog**. A 24 mm fogger sits in a printed float on the centre pipe.
An 80 mm 12 V fan in a box under the lid pulls air from the tank headspace and
blows it up a riser, between the lid spokes, then up a DN50 PVC duct round
the centre pipe to the mist head. There the fog leaves through 6 windows under
a hood and sinks past every root zone. It then falls back through the rotor
bore into the headspace. It is a closed loop, so little fog is lost.
**Hybrid:** the pump, the pipe and the jets in the mist head stay. Run a short
flush cycle (for example 1 min every 30-60 min) so the roots don't dry out if
the fogger fails.

Run: `env PYTHONPATH=/home/infra/printables/.pydeps python3 grow_tower/cad/concepts/gyroid_mist/gyroid_mist.py`
Viewer: `http://127.0.0.1:8766/viewer.html?concept=gyroid_mist`

## Parts (this folder `stl/`; base parts and the classic `cap.stl` come from `grow_tower/cad/stl/`)
| part | qty | print orientation | ~ASA g | notes |
|---|---|---|---|---|
| seg_1 .. seg_4 | 1 each | spigot down | 920 / 845 / 756 / 643 | different shapes, no supports, 10-14 MB STL |
| mist_head | 1 | stub down, **brim** | 65 | jets, stub for the classic cap, fog hood, duct socket |
| duct_foot | 1 | skirt down | 22 | sits on the lid spokes (gable notches) |
| fan_box | 1 | floor down | 54 | fan below the floor on 4 x M3x35 + nuts, M3 pipe clamp |
| fan_roof | 1 | plate down | 32 | riser + centring ribs; seal the groove with silicone |
| fog_float | 1 | base down | 120 | sealed hollow, 45 deg gabled cavity |
| fog_cradle | 1 | lip down | 35 | holds the fogger puck (50 x 24 mm) |
| cap | 1 | classic | 113 | unchanged classic part |

Bought parts: DN50 PVC drain pipe cut to 668 mm, an 80 mm 12 V fan (IP67, low
rpm, ~1500), a 24 mm single-disc fogger with a **built-in low-water
cut-off** (12 V or 24 V), and the 1/2" pipe at the classic length.

- **Gyroid saddles.** 7-9 % of the segment area is steeper than 45 deg. The largest
  patch steeper than 60 deg is 51-95 mm², and these patches print like gyroid infill.
  60 deg is 7.5 mm², and these patches print like gyroid infill.
- **fan_roof groove.** Its ceiling is a 3.2 mm bridge.
- **Small horizontal holes.** These are the jets, the pins and the M3 holes.

None of these need supports.

## Electronics (firmware NOT changed)
Two extra low-side outputs are needed:
- **Fogger MOSFET.** Switches the fogger supply: 12/24 V, about 1 A. For a 24 V
  fogger, add a 24 V supply.
- **Fan MOSFET.** Switches the 12 V fan, about 0.2 A. Add a flyback diode.

GPIO 26 and 27 are free and suit a future firmware (`PIN_FOGGER` and `PIN_FAN`).
Until then, run the fogger and fan from a plug-in cycle timer. One example is
10 min on / 5 min off, with the fan running together with the fogger. The
existing pump schedule then does the flush.

Route both cables through the lid gland, which needs an upgrade (see the risks).
All electronics stay inside the dry headspace above the 365 mm max fill mark.
The fan intake is at 402 mm, and rain can't reach it.

## Cleaning
Algae grow on the wet, lit lattice. The segments only sit in their sockets:
lift each one off and scrub it with a soft brush. You can also soak it in 3 %
H2O2. The skin is now up to 40 mm deep, so a bottle brush helps. The inside
wall bulges with the pebble but stays smooth. The duct slides off
the pipe after the mist head is removed (one M3 pin). Then the fan box and
float come off the pipe.

## Risks
- The fogger warms the water by about 1-2 °C. The tank also stays humid, so watch the root temperature in summer.
- The float can rotate on the pipe. If the cradle lands on the float-switch arm at low water, the fogger stops sooner. The fogger's own low-water cut-off covers this.
- The fan and the plenum run wet. Condensate drains through 2 holes outside the fan's inlet lip.
- The fog windows are 37 mm below the jets, so the top row of roots gets fog from the side.
- The rotating ASA is 3.5 kg (torque 43 % planted, 66 % mature, under the 50 / 75 % limits). Don't make the bellies any fatter without dropping the infill.
- Each segment is a long print, roughly 0.65-0.9 kg and 194 mm tall, and the bottom one fills 239 mm of the bed. Print it on a clean, level plate with a brim.
- The lobes are near-symmetric (the stack's COM is 0.2 mm off the axis, a 0.5 g m imbalance), so they don't add wobble.
- The outer gyroid sheets are only 2.1 mm, so the belly edges can chip. Lift the segments by the solid joint rims, not by the lattice.

## Base changes wanted
- Make the lid gland bigger (PG9/M16) or add a second gland for the fogger and fan cables.
- Add two more MOSFET outputs and schedules in the firmware.
