#!/usr/bin/env python
"""List units and whether they already have a photo/art skin. `roster.py --unskinned` shows only bare ones."""
import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
src = (ROOT / "src" / "game" / "data" / "units.ts").read_text()
ap = argparse.ArgumentParser()
ap.add_argument("--unskinned", action="store_true")
args = ap.parse_args()
for m in re.finditer(r'  def\(\n    "(\w+)",\n    "([^"]+)",\n    "([^"]+)",\n    (\d),\n    "(\w+)",\n    "(\w+)",(.*?)\n  \),', src, re.S):
    uid, name, emoji, cost, origin, role, rest = m.groups()
    skinned = "/units/" in rest
    if args.unskinned and skinned:
        continue
    print(f"{cost}-cost  {uid:10} {name:22} {origin}/{role:9} {'skinned' if skinned else 'bare'}")
