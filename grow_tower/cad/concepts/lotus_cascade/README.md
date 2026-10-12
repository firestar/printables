# Lotus Cascade

A pagoda of six flared, petal-notched bowls (7-7-7-6-5-4 = 36 plants). The bowls
narrow towards the top. They turn on the standard base. Each bowl holds a 15 mm
pool, and the 2" net pots stand in it, tilted 20 deg outward. The pot sleeves
bulge out of the bowl wall as petals.

Run: `env PYTHONPATH=/home/infra/printables/.pydeps python3 grow_tower/cad/concepts/lotus_cascade/lotus_cascade.py`
Viewer: `http://127.0.0.1:8766/viewer.html?concept=lotus_cascade` (`&section=1`, `&explode=60`)

## Water path
Pump -> 1/2" PVC pipe (1234 mm) -> **distributor** (fixed lotus seed pod).
8 jets hit the inside of the bell and rain off the bell rim into bowl 6.
Each bowl's pool is set by 3 **scupper standpipes** (10 mm bore, crest 15 mm).
Their overflow falls as vertical threads beside the stem into the bowl below.
Bowl 1's threads fall into the adapter's 45 deg funnel (lip r=46). From there
the water goes through the rotor bore into the lid drain (r=56).
A 1.8 mm weep at the foot of every standpipe empties the pools in 3-5 min once
the pump stops. This gives ebb and flow, and the stack is light between cycles.

**Why no open spill over the petal lip:** a sheet leaving a lip lands ~40 mm
further out, plus ~40 mm of wind drift over a 130 mm fall. To catch that, the
next bowl would need to be ~85 mm wider, and the 250 mm bed rules that out.
The petal notches sit 17 mm above the scupper crest. The head at 800 L/h with
one scupper blocked is 15.5 mm, so the notches stay dry.

## Parts (base parts: `grow_tower/cad/stl/`)
| part | qty | orientation | est. g (ASA, 80 %) |
|---|---|---|---|
| adapter | 1 | spigot down | 117 |
| bowl_1 .. bowl_6 | 1 each | floor down | 329, 324, 318, 297, 277, 191 |
| distributor | 1 | bell rim up (flipped) | 43 |
| 1/2" PVC pipe 1234 mm, M3x70 screw + nut (cross pin) | | | |

No supports. The only > 45 deg faces are bridges over the weep holes, 1 mm
drip-break grooves, jets and pin holes. Print the bowls with 3+ perimeters and
100 % top/bottom near the floor. They hold water, so seal them inside with a
brush coat of epoxy, or smooth with acetone vapour (ASA). The stem joints
are dry, so they need no seal.

## Assembly
Adapter into the rotor -> bowls 1..6 over the pipe (each stem spigot goes into
the socket above; turn the bowls to stagger the petals) -> distributor onto the
pipe top inside bowl 6's stem bore (that bore is the top bushing) -> cross pin
through the bell, sleeve and pipe.

## Risks
- Plants have ~70 mm of headroom over the pot lip under the next bowl, and lean
  out at 20 deg. Good for herbs, strawberries and compact lettuce, tight for big heads.
- Roots grow into the pools and toward the scuppers. Check the standpipes
  monthly. One blocked scupper is fine, two may make a petal notch spill.
- Algae in the open pools: use opaque or dark ASA.
- The bowl joints carry torque by friction only. Upper bowls only see bushing drag.
