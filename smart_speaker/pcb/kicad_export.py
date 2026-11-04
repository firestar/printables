#!/usr/bin/env python3
"""Run inside the KiCad container: fill the copper zones and save the board.
See export.sh."""
import sys

import pcbnew

path = sys.argv[1]
board = pcbnew.LoadBoard(path)
filler = pcbnew.ZONE_FILLER(board)
filler.Fill(board.Zones())
board.Save(path)
print("zones filled:", len(board.Zones()))
