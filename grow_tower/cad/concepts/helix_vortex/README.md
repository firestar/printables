# Helix Vortex

Concept stack for the rotating grow tower (rules: `../BRIEF.md`). The stand, tank,
lid, drive pod, pinion, rotor, pipe foot and float bracket are the classic parts:
print them from `grow_tower/cad/stl/`. The unchanged spray head comes from there too.

- **Tiers (x6, identical):** a soft hexagon (r 76..84 mm) whose outline twists 12°
  per tier. Each tier sits 12° further round than the one below, so the port
  columns spiral up the tower. The 6 ports sit on the flats.
- **Spiral NFT gutter:** printed into every tier. It is a V-channel made of the
  outer wall plus a 45° flank. It makes one turn (356°) at 3 % fall, 25.5 -> 10.9 mm.
  Each port follows the gutter down, and its window opens 2 mm above the gutter
  floor. The pot drains into the flow, and the pot base sits 15 mm above it.
- **Cascade:** the gutter end pours onto the tier's inner shoulder. The water runs
  down the spigot and drips 12° further round. Because of the twist, that spot is
  ψ = 8° on the gutter below: just after its start and clear of the pots. The
  result is 3.4 m of NFT path in 7 turns.
- **Header + cap:** the header is a port-less ring with the same gutter. The fixed
  spray head squirts at its wall, the header gutter collects the water and feeds
  tier 6. Pump pressure only has to throw about 65 mm. The cap is the classic cap
  plus a petal plate, with the bushing riding on the spray-head stub.
- **Keys:** every socket has a tooth and every spigot has a slot, which fixes the
  12° indexing. The rotor has no tooth, so tier 1 can go in at any angle.
- **Clog / overflow:** water spills over the lip (r ≤ 62 mm, inside every spigot
  bore). It falls into a lower gutter or onto the rotor funnel, then into the lid drain.

## Print

| part | qty | orientation | ASA est. |
|---|---|---|---|
| tier | 6 | spigot down | ~277 g |
| header | 1 | spigot down | ~187 g |
| cap | 1 | top face down | ~103 g |

No supports are needed: the script measures 0 mm² of overhang over 45°. Use 4 or
more perimeters (walls 2.4-3.4 mm). The gutter floor lies against the outer wall,
so make that wall watertight: 4 walls, or brush the gutter corner with ASA/acetone
slurry. A leak there would weep outside.

## Run

`env PYTHONPATH=/home/infra/printables/.pydeps python3 grow_tower/cad/concepts/helix_vortex/helix_vortex.py`

This writes `stl/`, `preview/` (manifest, assembled STLs, `section_2d.png`) and
prints the checks. Viewer: `viewer.html?concept=helix_vortex`.
