# Hyperboloid Lattice

12 straight grow tubes, tilted 20 deg, run between a bottom ring and a top
crown and form a ruled hyperboloid (waist r=120 at z=896, ends r=145, 69 deg
twist). Each tube is a 40 mm NFT channel with 3 net-pot ports, so 36 plants.
Height on the stand is 1296 mm. Inside the cage, 6 steel rods run the other
way (opposite twist), as in a Shukhov or cooling-tower lattice. One family
of straight bars alone is a mechanism: the script shows stiffness rank 3/6
for the tubes alone and 6/6 with the rods.

Only the turning stack is new. Tank, lid, drive, rotor and stand are the
classic base parts (`grow_tower/cad/stl/`).

## Water path
pump -> 1/2" pipe -> classic spray head (fixed) -> jets hit the wall of the
**crown pan**. The pan is flat and level, with an inner lip 1 mm clear of the
spray-head sleeve. Water crosses from fixed to turning with no seal ->
12 x 8 mm outlets with drip grooves -> cup + 46 deg duct in each **head
shoe** -> film on the floor (low side) of the tilted tube -> **foot shoe**
funnel + 48 deg duct -> drip spout inside the **bowl** wall -> 45 deg bowl
funnel -> rotor bore -> lid drain. Water outside r=122 is always inside a
closed duct. If outlets clog, the pan overflows over the lip and runs down
the pipe into the bowl.

## Joints
All joints are the same socket/spigot pair:
- The upper spigot sits *inside* the lower socket, so the film runs over
  every joint downhill.
- The 40 mm bore is continuous through the joint.
- Each joint has a 3 mm O-ring gland and a bayonet lug: insert, twist
  15 deg, locked.
- The lug/slot offset rolls each segment +10 deg relative to the one below.
  This puts the ports at -25/-15/-5 deg, on the upper side, while all 36
  segments are **identical prints**.

## Parts (ASA, ~85 % fill)

| part | qty | orientation | g each | support |
|---|---|---|---|---|
| segment | 36 | spigot down | 69 | none (2 cm2 local >45 deg at port bulb, 0.2 cm2 pocket bridge) |
| foot_shoe | 12 | pad down | 40 | none (drip-groove bridge) |
| head_shoe | 12 | pad down (flipped) | 37 | ~5 cm2 on cup block sides: paint-on support |
| rod_bracket | 6 | pad down (flipped) | 4 | none |
| bowl | 1 | spigot down | 178 | none |
| crown_pan | 1 | floor down | 232 | none (drip-groove bridges) |
| crown_lid | 1 | roof down | 131 | none |

That is about 4.0 kg of filament in total.

Hardware:
- 6 x d6 mm steel rod, cut to 665 mm. Glue them in, or pin with M3 grub
  screws (pilots provided).
- 48 x O-ring (3 mm cord, ~150 mm).
- 24 + 24 + 12 x M4 self-tapping screws.
- 1/2" PVC pipe, cut to 1217 mm.

## Assembly
Assemble in this order:
1. Seat the bowl in the rotor.
2. Screw the foot shoes to the bowl rim.
3. Glue the rods into the bowl bosses.
4. Fit the segments layer by layer: all 12 bottom segments, then the middle
   ones, then the top ones.
5. Fit the head shoes.
6. Slide the rod brackets onto the rod tops.
7. Drop the pan on and screw it down.
8. Fit the lid.

The checks prove this order (the drop paths include the neighbouring tubes).

Run: `env PYTHONPATH=/home/infra/printables/.pydeps python3 grow_tower/cad/concepts/hyperboloid_lattice/hyperboloid_lattice.py`
Viewer: `http://127.0.0.1:8766/viewer.html?concept=hyperboloid_lattice`
