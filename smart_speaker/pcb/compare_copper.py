#!/usr/bin/env python3
"""Compare the copper and drill files in a board's Gerber zip with a committed version,
ignoring creation dates.  Run from the repo root with: zip path, then git revision."""
import io
import subprocess
import sys
import zipfile


def clean(data):
    keep = [ln for ln in data.decode().splitlines()
            if "CreationDate" not in ln and not ln.startswith(("G04", ";"))]
    return keep


path, rev = sys.argv[1], sys.argv[2]
old = zipfile.ZipFile(io.BytesIO(subprocess.check_output(["git", "show", f"{rev}:{path}"])))
new = zipfile.ZipFile(path)
same = True
for name in sorted(new.namelist()):
    if not any(k in name for k in ("_Cu", "PTH", "Edge_Cuts", "Mask")):
        continue
    ok = clean(old.read(name)) == clean(new.read(name))
    same &= ok
    print(f"  {'same   ' if ok else 'CHANGED'} {name}")
print("COPPER, DRILLS, OUTLINE AND MASK UNCHANGED" if same else "SOMETHING OTHER THAN SILKSCREEN CHANGED")
sys.exit(0 if same else 1)
