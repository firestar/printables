# Bed air duct

6" flex hose -> flat 320 x 70 mm duct along the middle of a king mattress,
under the covers, ending in a louvred diffuser toward the head. Room / cooled
air only. Printable on a Bambu P1S (256 mm bed).

```
floor hose -> adapter (hangs at the foot face) -> elbow (wraps the foot edge)
           -> 3 x segment + 4 x segment_vented (on the mattress) -> diffuser
```

Flow area of the duct is 183 cm², the same as a 6" round pipe (182 cm²).

## Parts (`cad/stl/`, already in print orientation)

| part | qty | orientation | notes |
|---|---|---|---|
| adapter | 1 | spigot down | 150 mm OD spigot with a clamp bead for 6" flex duct |
| elbow_half | 2 | cut face down | bolt together with 5 x M3 x 12 + nuts, glue the seam |
| segment | 3 | socket down | goes at the foot end |
| segment_vented | 4 | socket down | slotted flanks with a dovetail track |
| slider | 8 | apex down | 2 per vented segment, slide in from the plain end |
| diffuser | 1 | socket down | top + flank louvres aim air toward the feet |

PETG, 0.2 mm layers, 3 walls, 15 % infill. Use a brim on the standing parts.
Segments sit diagonally on the bed (footprint 236 mm), so turn off auto-arrange
rotation.

## Assembly

1. Bolt the two elbow halves together (gluing the seam is optional). Push the
   elbow's lower end into the adapter socket.
2. Clamp the hose over the adapter spigot, above the bead.
3. Lay the elbow over the foot edge of the mattress. Push segment 1's socket
   onto the elbow's mattress-side end, then chain the rest: each socket faces
   the foot.
4. Slide the sliders into the vented segments from the plain (head) end before
   joining the next segment. The next socket locks them in.
5. Finish with the diffuser. Tape the joints if they whistle.

Vents: push a slider toward the head to close it, toward the feet to open it
(10 mm travel).

## Known compromises

- The duct is a 70 mm ridge down the middle of the bed.
- The inner elbow flange sits 7 mm into the mattress corner (foam takes it).
- Use an inline duct fan. A desk fan won't push enough through 2 m of flat duct.

## Build

```
cd cad
PYTHONPATH=../../.pydeps python3 bed_air.py   # STLs, preview/, checks
PYTHONPATH=../../.pydeps python3 section.py   # preview/section_2d.png
python3 -m http.server 8090                   # then open viewer.html
```

All dimensions are parameters at the top of `bed_air.py` (mattress length,
profile, segment counts, clearances).
