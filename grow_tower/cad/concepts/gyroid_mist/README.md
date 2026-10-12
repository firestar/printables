# Gyroid Mist Shell (fogponic concept)

Four identical pebble-shaped segments make the turning stack. Each one is the
classic closed 3.4 mm tier wall wrapped in a cylindrical gyroid sheet lattice
(2.4 mm sheet, 30 cells round, 3 to 13 mm thick). Each segment carries nine 2"
net-pot pockets in a three-start helix (3 rows x 3, rows 40 deg apart), so
4 x 9 = 36 plants. Height is 1260 mm on the stand. The lattice is relief
**outside** the solid wall, so fog and drip stay in the chamber. The check
script proves the wall is open only at the 36 bores.

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
| segment | 4 | spigot down | 545 | 241 mm footprint, no supports |
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

Overhangs: all parts stay at 45 deg or less except these:
- **Gyroid saddles.** 2.7 % of the segment area. The largest patch steeper than
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
H2O2. The inside wall is smooth, like the classic wall. The duct slides off
the pipe after the mist head is removed (one M3 pin). Then the fan box and
float come off the pipe.

## Risks
- The fogger warms the water by about 1-2 °C. The tank also stays humid, so watch the root temperature in summer.
- The float can rotate on the pipe. If the cradle lands on the float-switch arm at low water, the fogger stops sooner. The fogger's own low-water cut-off covers this.
- The fan and the plenum run wet. Condensate drains through 2 holes outside the fan's inlet lip.
- The fog windows are 37 mm below the jets, so the top row of roots gets fog from the side.

## Base changes wanted
- Make the lid gland bigger (PG9/M16) or add a second gland for the fogger and fan cables.
- Add two more MOSFET outputs and schedules in the firmware.
