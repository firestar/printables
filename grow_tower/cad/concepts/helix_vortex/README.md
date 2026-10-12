# Helix Vortex

Concept stack for the rotating grow tower (rules: `../BRIEF.md`). The stand, tank,
lid, drive pod, pinion, rotor, pipe foot and float bracket are the classic parts:
print them from `grow_tower/cad/stl/`. The unchanged spray head comes from there too.

- **Tiers (x6, identical):** a 6-lobe star (r 76..100 mm) with 24 mm deep, sharp
  V valleys. The outline twists continuously at 25° per tier, and each tier sits
  25° further round than the one below. The lobes and valleys therefore run as
  unbroken helices up the whole stack (150° over 6 tiers). 25° is used rather
  than 30°: at 30° (half the 60° lobe pitch) every second tier lines up and the
  eye reads a stagger, not a spiral.
- **Collars:** each tier top carries its lobes 24 mm up over the 45° neck of the
  tier above, leaving a 1 mm seam. The joints no longer break the spiral. The
  collar's inside is a cone that opens upward, so it prints without support, and
  the tier still drops in straight.
- **Ports on the lobes:** 6 per tier, mouth at r 102 as in the classic design. A
  scoop is cut into the lobe above each mouth so the pot lip drops in along the
  axis.
- **Spiral NFT gutter:** printed into every tier. It is a 45° flank that falls at
  3 % over 343°, 20.1 -> 4.8 mm. In the valleys the outer side of the V is the
  wall. Where a lobe bulges further out, the corner rides the 45° bottom funnel
  instead. Each pot base hangs 5-15 mm over the flow.
- **Cascade:** the gutter end pours onto the tier's inner shoulder. The water runs
  down the spigot and drips 25° further round. Because of the twist, that spot is
  ψ = 8.5° on the gutter below, 29 mm clear of the first pot. The result is 3.6 m
  of NFT path in 7 turns.
- **Header + cap:** the header is a port-less star ring with the same gutter. The
  fixed spray head squirts at its wall, and the sheet runs down the twisted lobe
  walls into the gutter. The cap is the classic cap plus a star plate.
- **Keys:** every socket has a tooth (on a lobe flank, clear of the pots) and every
  spigot has a slot, which fixes the 25° indexing. The rotor has no tooth.
- **Clog / overflow:** water spills over the lip (r ≤ 62 mm, inside every spigot
  bore). It falls into a lower gutter or onto the rotor funnel, then into the lid drain.

## Print

| part | qty | orientation | ASA est. |
|---|---|---|---|
| tier | 6 | spigot down, 241 x 235 x 152 | ~434 g |
| header | 1 | spigot down | ~355 g |
| cap | 1 | top face down | ~124 g |

No supports are needed: the script measures ≤ 0.1 mm² of overhang over 45°. The
twisted lobe flanks lean ≤ 11°. Walls are ≥ 2.5 mm measured normal to the lobe
flanks, so use 4 or more perimeters. The gutter floor lies against the outer wall
and the funnel, so make that wall watertight: 4 walls, or brush the gutter corner
with ASA/acetone slurry. A leak there would weep outside. Rain that collects in
the collar seams runs into the tier joint and down to the tank, which is harmless.

## Run

`env PYTHONPATH=/home/infra/printables/.pydeps python3 grow_tower/cad/concepts/helix_vortex/helix_vortex.py`

This writes `stl/`, `preview/` (manifest, assembled STLs, `section_2d.png`) and
prints the checks. Viewer: `viewer.html?concept=helix_vortex`.
