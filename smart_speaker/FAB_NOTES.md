# Fabricator notes for the speaker interface board

Prepared to compare fabricators. Nothing has been ordered. Limits come from each fabricator's
published capability page, read on 2026-11-04; OSH Park's page carries a 2023 copyright, so confirm
it. Prices aren't quoted here except OSH Park's published rates: get live quotes from each site,
since shipping and tariffs can change the total a lot.

## The two boards

| | 2-layer | 4-layer |
|---|---|---|
| Upload | `pcb_2layer/interface_board_2l-gerbers.zip` | `pcb/interface_board-gerbers.zip` |
| Size | 62.1 x 54.6 mm | 62.1 x 54.6 mm |
| Layers | 2 | 4 |
| Material | FR-4 | FR-4 |
| Thickness | 1.6 mm | 1.6 mm |
| Outer copper | 1 oz | 1 oz |
| Inner copper | none | 0.5 oz |
| Finish | HASL lead free | HASL lead free |
| Quantity | 5 | 5 |
| Smallest track / gap | 0.25 mm / 0.2 mm | 0.25 mm / 0.2 mm |
| Via | 0.3 mm drill, 0.7 mm pad | 0.3 mm drill, 0.7 mm pad |
| Ring | 0.2 mm via, 0.3 mm pad | 0.2 mm via, 0.3 mm pad |
| Non-plated | 4 x 2.7 mm holes, 5 x 2.2 mm slots | same |
| Impedance control | not needed | not needed |
| Panelization | none, single pieces | none, single pieces |

## What each fabricator offers against these needs

| | PCBWay | JLCPCB | OSH Park |
|---|---|---|---|
| 2 and 4 layers at 1.6 mm | Yes | Yes | Yes |
| 1 oz outer | Yes | Yes (default) | Yes |
| 0.5 oz inner | Not listed: 1 oz is its lowest published option | Yes (default) | Yes (fixed) |
| Lead-free HASL | Yes | Yes | No: ENIG only, fixed |
| Min track / gap | 0.1 mm | Below ours | 0.15 mm (2-layer), 0.13 mm (4-layer) |
| Min ring | 0.15 mm | Via pad 0.1 to 0.15 mm over drill | 0.13 mm (2-layer), 0.10 mm (4-layer) |
| Non-plated slot minimum | Check at upload | 1.0 mm, ours is 2.2 mm | Check at upload |
| Quantity 5 | Quote | Quote | No: sets of 3, so 6 boards |
| Cost basis | Live quote | Live quote | 2-layer $5/sq in, 4-layer $10/sq in, per set of 3 |
| Solder mask | Green, red, yellow and blue have no extra charge; black isn't on that list | Several colors | Purple only |

For OSH Park, the board's bounding box is about 5.24 sq in, so a set of 3 would be about $26 for 2-layer and
$52 for 4-layer. Its 4-layer boards use FR408 rather than FR-4.

## To settle before ordering

- **Silkscreen size:** PCBWay asks for characters at least 0.8 mm tall and 0.15 mm wide. Our smallest labels
  are 0.7 mm tall with lines of about 0.1 mm, and the part labels are 0.8 mm with lines of about 0.12 mm, so
  they may print blurry or prompt a question. This is cosmetic. Enlarging them means rebuilding both zips.
- **PCBWay colors:** the earlier screenshot had black mask and yellow silkscreen. Its page lists white and black as
  the no-extra-charge silkscreen, and black mask isn't on its no-extra-charge list, so that combination
  may cost more.
- **PCBWay 4-layer inner copper:** it publishes 1 oz as its lowest inner option. That works for this
  design; its form may show a different default.
- **Assembly:** these zips are bare-board only. Fab assembly would also need a parts list and a placement file,
  which aren't generated yet.
- **Test first:** no board has been built. Order the minimum and test one before any larger run.
