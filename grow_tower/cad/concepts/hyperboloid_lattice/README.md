# Hyperboloid Lattice

9 straight grow tubes, tilted 44 deg, run between a bottom ring and a top
crown and form a ruled hyperboloid: waist r=106 at z=920, ends r=211, so
the ends are **2x the waist** (120 deg twist). Each tube is a 40 mm NFT
channel with 4 net-pot ports, so 36 plants. Height on the stand is 1357 mm.
Inside the cage, 9 aluminium rods run the other way (opposite twist), as in a
Shukhov or cooling-tower lattice. One family of straight bars alone is a
mechanism: the script shows stiffness rank 3/6 for the tubes alone and 6/6
with the rods.

Why 9 tubes and not 12: neighbouring tubes come closest at the waist. With
12 tubes, the waist could not drop below r~126 (neighbour clearance), and the
flare stopped at 1.66x. With 9 tubes, the waist pinches to r=106 and the
middle ports sit just above and below the waist, so the waist stays slim.

Only the turning stack is new. Tank, lid, drive, rotor and stand are the
classic base parts (`grow_tower/cad/stl/`).

## Water path
pump -> 1/2" pipe -> classic spray head (fixed) -> jets hit the wall of the
**crown pan**. The pan is flat and level, with an inner lip 1 mm clear of the
spray-head sleeve. Water crosses from fixed to turning with no seal ->
9 x 9.2 mm outlets with drip grooves -> cup + 46 deg duct in each **head
shoe** -> film on the floor (low side) of the tilted tube -> **foot shoe**
funnel (straight below the tube end) + 46 deg duct -> drip spout inside the
**bowl** wall -> 45 deg bowl funnel -> rotor bore -> lid drain.

The crown and foot reach r~235, wider than the tank (r=122). Out there the
water is always inside a tube or a closed duct. Only the port mouths are open,
and they face up, so rain can get in but no water leaks out. If outlets clog,
the pan overflows over the lip and runs down the pipe into the bowl.

## Joints
The segment joints are all the same socket/spigot pair:
- The upper spigot sits *inside* the lower socket, so the film runs over
  every joint downhill.
- The 40 mm bore is continuous through the joint.
- Each joint has a 3 mm O-ring gland and a bayonet lug: insert, twist
  15 deg, locked.
- The lug/slot offset rolls each segment +5 deg relative to the one below.
  This puts the ports at -20/-15/-10/-5 deg, on the upper side, while all 36
  segments are **identical prints**.

The head shoe is a plain O-ring push-fit with no lug. Its long inlet duct
would swing into the neighbour during a bayonet twist. The pan screws hold
it down.

## Parts (ASA, ~85 % fill)

| part | qty | orientation | g each | support |
|---|---|---|---|---|
| segment | 36 | spigot down | 60 | none (2 cm2 local >45 deg at port bulb, 0.2 cm2 pocket bridge) |
| foot_shoe | 9 | pad down | 47 | none (drip-groove bridge) |
| head_shoe | 9 | pad down (flipped) | 58 | ~3 cm2 on cup block sides: paint-on support |
| rod_bracket | 9 | pad down (flipped) | 4 | none |
| bowl | 1 | spigot down | 191 | none |
| crown_pan | 1 | floor down | 232 | none (drip-groove bridges) |
| crown_lid | 1 | roof down | 131 | none |

That is 66 printed parts (round 1: 69) and about 3.7 kg of filament (round 1:
4.0 kg). There are 45 sealed joints (round 1: 48). Two segments per tube
would not fit: a half tube is 262 mm plus the socket, and the bed is 256 mm.

Hardware:
- 9 x d6 mm aluminium rod (6061), cut to 728 mm, 55 g each. Glue them in, or
  pin with M3 grub screws (pilots provided). Steel also works but is 3x
  heavier.
- 45 x O-ring (3 mm cord, ~150 mm).
- 18 + 18 + 18 x M4 self-tapping screws.
- 1/2" PVC pipe, cut to 1278 mm.

## Mass / torque
- Turning stack: 4.20 kg.
- Total, with plants: 10.6 kg.
- Worst-case friction torque: 0.099 N m, which is 49 % of 0.2 N m (bushing
  side load now uses half the real 10 m/s drag).

## Assembly
Assemble in this order:
1. Seat the bowl in the rotor.
2. Screw the foot shoes to the bowl rim.
3. Glue the rods into the bowl bosses.
4. Fit the segments layer by layer (all 9 bottom segments first, and so on
   up, 4 layers).
5. Push the head shoes on.
6. Slide the rod brackets onto the rod tops.
7. Drop the pan on and screw it down.
8. Fit the lid.

The checks prove this order (the drop paths include the neighbouring tubes).

## Risks
- Clearances are tight: tube to neighbour is 4.0 mm and rod to lattice is
  3.0 mm. Print tolerances and plant stems will eat into that.
- Pots tilt 50-57 deg from vertical. Use a coarse medium (clay pebbles)
  that stays in the basket.
- The ends overhang the tank by about 110 mm, which makes the tower more
  sensitive to imbalance (the budget assumes 1 kg off-balance at r=220).
- The ends overhang the tank by about 110 mm, which makes the tower more
  sensitive to imbalance (the budget assumes 1 kg off-balance at r=220).
- Wind area (check 5): projected silhouette of the real turning stack (tubes,
  pots, shoes, bowl, crown; worst azimuth) is 0.239 m2. Mature foliage is
  modelled as every pot shadow grown by 80 mm (a ~d210 lettuce head), 50 %
  porous, counted only where it sticks out past the stack: +0.052 m2. Total
  0.291 m2 (was 0.18), centroid 947 mm above the ground. Drag (Cd 1.1) is
  19 N at 10 m/s and 43 N at 15 m/s.
- Yaw: the 9-fold lattice alone gives no net yaw (the chiral cross-flow terms
  cancel round the ring; lee-side shielding would break that a little). The
  real source is lopsided foliage: one half harvested leaves 0.025 m2 at
  x=196 mm, so 0.08 N m at 5 m/s, 0.32 N m at 10 m/s, 0.72 N m at 15 m/s.
  **Above about 6 m/s the drive stalls** (the 0.2 N m drive minus 0.1 N m of
  friction leaves 0.1 N m for wind). With the coils off, the
  28BYJ-48's 64:1 gearbox resists back-driving; we assume ~0.05 N m at its
  shaft (not measured), which is ~0.46 N m at the rotor. **So at 15 m/s the wind
  can back-drive the stack**: the step count goes wrong, and the plastic
  gearbox is loaded backwards. Mitigation:
  - Firmware already de-energises the coils between moves. Also skip moves
    while gusting (step-loss check or a cheap anemometer), and re-home on a
    hall sensor + magnet on the rotor.
  - Harvest evenly round the ring.
  - For exposed sites, use a stronger motor (NEMA17 on the same pinion is ~3 N m
    at the rotor) or a spring/felt drag pad on the rotor. The pad must stay
    under the 0.1 N m headroom.
- Tip-over (check 6): the weak edge is between two feet, 237 mm from the
  axis. Base 3.6 kg (+ pump + pipe), stack 5.2 kg, tank 17.8 L full / 2 L
  near-empty. Plants are 36 x 150 g, also tested all on one side and 2x on
  one side. Wind is on the real area at its centroid, plus the tank/stand
  (0.126 m2, Cd 0.8). Safety factor, unstaked:
  - Full tank: >= 3.3 at 10 m/s and >= 1.47 at 15 m/s.
  - Near-empty, plants on one side: 1.44 at 10 m/s (FAIL < 1.5) and 0.64 at
    15 m/s, so it tips.
  **Stakes are required outdoors.** With 2 far stakes x 150 N pull-out
  (30 cm stake in soil, assumed) at 460 mm, the worst case is 3.77 at
  15 m/s -> OK. Unstaked at 10 m/s, keep >= 3 L in the tank.
Run: `env PYTHONPATH=/home/infra/printables/.pydeps python3 grow_tower/cad/concepts/hyperboloid_lattice/hyperboloid_lattice.py`
Viewer: `http://127.0.0.1:8766/viewer.html?concept=hyperboloid_lattice`
