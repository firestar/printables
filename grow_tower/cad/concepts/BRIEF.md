# Concept tower brief (shared rules)

Rotating outdoor hydroponic grow tower, printed in ASA on a 256 x 256 bed
(Bambu). The classic design is `grow_tower/cad/grow_tower.py`; read it first.
Each concept replaces only the **turning stack and its water distribution**.

## Files
- Your folder: `grow_tower/cad/concepts/<name>/` with `<name>.py`, `stl/`,
  `preview/` (`manifest.json`, assembled STLs, `section_2d.png`), `README.md`.
- Import the base: `sys.path.insert(0, <grow_tower/cad>)`, `import grow_tower as gt`.
- Run: `env PYTHONPATH=/home/infra/printables/.pydeps python3 grow_tower/cad/concepts/<name>/<name>.py`
  (libs: manifold3d, trimesh, numpy, matplotlib).
- Do NOT edit `grow_tower.py`, `viewer.html`, `concepts.json`, `section.py`,
  the firmware or other concept folders. If the base needs to change, say so
  in your report instead.

## Interface to the fixed base (reuse as-is)
- `gt.build_base()` -> (parts, leg): tank, rings, lid, fill plug, drive pod,
  pinion, rotor (ball race + 128T ring gear), pipe foot, float bracket, hub, legs.
- Their assembled STLs already exist in `grow_tower/cad/preview/<name>.stl`. In
  `gt.export_set(...)` pass `preview={"lid": "preview/lid.stl", ...}` (paths
  relative to `grow_tower/cad`) for unchanged base parts, and `meta` from
  `gt.base_meta(name)`. Only export your own parts to your `stl/`; the README
  points to `grow_tower/cad/stl/` for the base parts.
- The turning stack seats in the rotor socket with the same spigot as
  `gt.make_tier`: outer `R_SO`, `SPIG_L` long below the seat, 45 deg shoulder
  to `R_TO`, seat at `z = gt.Z_RT - gt.SEAT_DROP`. Use an adapter part if your
  geometry differs. Prove it with `gt.drop_check` (see `gt.checks`).
- The 1/2" PVC centre pipe (`gt.PIPE_OD/ID`, bottom at `gt.PIPE_Z0`) is fixed;
  you choose its length and the fixed distributor on top (adapt
  `gt.make_spray_head` if you like). Keep a top centring bushing for the
  turning stack on a fixed stub, as `gt.make_cap` does.
- Return water must fall through the rotor bore (inside `gt.R_TI` at the rotor
  top) into the lid drain (`gt.R_DRAIN`). No water may leave the stack outside
  the tank footprint (`gt.RC`), even in light wind.
- Pump: small 12 V submersible, ~800 L/h max, 1.3-1.6 m head, run in 5-15 min
  on/off cycles.

## Targets
- 36 plants (2" net pots: bore `gt.PORT_ID`, lip rests on the mouth), height
  about 1.2 m (+-20 %) on the stand.
- Torque: 28BYJ-48 through 128:15 gives ~0.2 N m at the tower. Report the
  rotating mass (ASA 1.07 g/cm3, estimate infill), water/media held while
  turning, and friction torque on the ball race (rolling coeff 0.005-0.01 on
  6 mm balls at `gt.RACE_R`) plus bushing drag. Must stay well under 0.2 N m
  (aim < 50 %), and comment on wind and imbalance.
- Print: every part fits the bed (`bed_fit` <= 250 mm), watertight mesh,
  print orientation with overhangs <= 45 deg (list any support needed),
  walls >= 2.0 mm. Note sealing for anything that holds water.

## Checks the script must print (OK/FAIL, like `gt.checks`), all OK
1. Stack drop-in seating (path, seated, wiggle) for every stacked joint.
2. Turning vs fixed parts min gap >= 0.8 mm, swept over a full symmetry period.
3. Water path: every plant root zone is wetted; every drip/overflow ends
   inside the drain radius.
4. Bed fit + watertight (`gt.export_set` reports it).
5. Mass/torque budget.
Plus `preview/section_2d.png`: matplotlib cut through the axis (like
`grow_tower/cad/section.py`) with water path arrows.

## Viewer
`gt.export_set` writes `preview/manifest.json`. Turning parts `spin=True`,
explode levels increase upward. The preview server is already running:
`http://127.0.0.1:8766/viewer.html?concept=<name>` (also `&section=1`,
`&explode=60`). Check your concept in the browser with screenshots, look at
them critically and fix what looks wrong. Don't start another server.

## Spirit
Be genuinely original. This is an experimental showpiece, but it has to stay
buildable and printable by a hobbyist.

## Report back (< 400 words)
Design summary, part list (qty, print orientation, est. filament g), check
output (the OK/FAIL lines verbatim), risks, and any base change you'd want.
Do not commit.
