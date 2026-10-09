#!/usr/bin/env python
"""Close-up of the head for judging faces: facecam.py specs/x.json [--size 768] → public/assets/characters/<id>/face.png"""
import argparse, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from figure import Figure
from render import render
ap = argparse.ArgumentParser(); ap.add_argument("spec"); ap.add_argument("--size", type=int, default=768); ap.add_argument("--angle", default="front")
a = ap.parse_args()
spec = json.loads(Path(a.spec).read_text())
fig = Figure(spec); parts = fig.build()
head = fig.J("head") + [0, 0.1, 0]
# parts were grounded after posing; recompute the head position from the posed eye meshes instead
eyes = [p[1] for p in parts if p[0].startswith("eye_")]
c = sum(m.vertices.mean(0) for m in eyes) / len(eyes)
cam = {"front": (0, 0, 1), "three_quarter": (0.6, 0.15, 0.8), "side": (-1, 0, 0)}[a.angle]
img = render(parts, cam, a.size, model_height=0.95, shadow=False, recenter=False, center=c + [0, 0.02, 0])
out = Path(__file__).resolve().parents[4] / "public" / "assets" / "characters" / spec["id"] / f"face_{a.angle}.png"
img.save(out); print(out)
