#!/bin/bash
# Fill zones, run DRC, export Gerbers, drill files and pictures.
# Run from smart_speaker/pcb/ on a machine with Docker:  bash export.sh
set -euo pipefail
cd "$(dirname "$0")"
B=interface_board_2l
python3 make_pcb.py
K="docker run --rm -u $(id -u):$(id -g) -e HOME=/tmp -v $PWD:/work -w /work kicad/kicad:9.0"
$K python3 kicad_export.py $B.kicad_pcb
$K kicad-cli pcb drc --severity-all --exit-code-violations --format report -o drc.rpt $B.kicad_pcb || DRC_FAILED=1
rm -rf gerbers && mkdir -p gerbers render
LAYERS=F.Cu,B.Cu,F.SilkS,B.SilkS,F.Mask,B.Mask,F.Paste,Edge.Cuts
$K kicad-cli pcb export gerbers --layers $LAYERS --no-protel-ext -o gerbers/ $B.kicad_pcb
$K kicad-cli pcb export drill --format excellon --excellon-separate-th -o gerbers/ $B.kicad_pcb
for L in F.Cu B.Cu; do
  $K kicad-cli pcb export svg --layers "$L,Edge.Cuts" --mode-single --exclude-drawing-sheet --page-size-mode 2 -o "render/$L.svg" $B.kicad_pcb
done
$K kicad-cli pcb render --side top --width 1400 --height 1400 --quality high -o render/top.png $B.kicad_pcb || echo "3D top render failed"
$K kicad-cli pcb render --side bottom --width 1400 --height 1400 --quality high -o render/bottom.png $B.kicad_pcb || echo "3D bottom render failed"
(cd gerbers && rm -f ../$B-gerbers.zip && python3 -c "import zipfile,glob; z=zipfile.ZipFile('../$B-gerbers.zip','w',zipfile.ZIP_DEFLATED); [z.write(f) for f in sorted(glob.glob('*'))]; z.close()")
echo "== DRC summary =="; tail -n 25 drc.rpt
[ "${DRC_FAILED:-0}" = 0 ] && echo "DRC CLEAN" || { echo "DRC HAS VIOLATIONS (see drc.rpt)"; exit 1; }
