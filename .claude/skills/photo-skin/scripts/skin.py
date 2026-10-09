#!/usr/bin/env python
"""
Skin a unit with a real photo: face-aware crops + units.ts patch.

  skin.py <photo> --unit <existing-unit-id> --name "Display Name" [--ability "Name"] [--emoji "🎤"] [--folder slug]
  skin.py <photo> --unit crab --name "David Bowie" --ability Heroes --emoji ⚡ --dry-run   # crops only, no code change

Writes public/units/<folder>/photo.png (256² thumb) and splash.png (600×400 card art), both framed on the
largest detected face, then rewrites the unit's name, emoji, ability name and picture fields in
src/game/data/units.ts. Stats, id, traits and cost are untouched so pools, saves and balance stay the same.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
UNITS_TS = ROOT / "src" / "game" / "data" / "units.ts"
MODEL = HERE / "face_detection_yunet_2023mar.onnx"


def load_image(path: Path) -> Image.Image:
    """Pillow can't read AVIF/HEIC; convert through macOS sips first."""
    if path.suffix.lower() in (".avif", ".heic", ".heif"):
        tmp = Path(tempfile.mkdtemp()) / "in.png"
        subprocess.run(["sips", "-s", "format", "png", str(path), "--out", str(tmp)], check=True, capture_output=True)
        path = tmp
    return Image.open(path).convert("RGB")


def detect_face(img: Image.Image):
    """Largest face as (cx, cy, w, h) in image pixels, or None."""
    arr = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    h, w = arr.shape[:2]
    # YuNet likes inputs under ~1500px; scale down for detection and map back.
    s = min(1.0, 1200 / max(w, h))
    small = cv2.resize(arr, (int(w * s), int(h * s))) if s < 1 else arr
    det = cv2.FaceDetectorYN.create(str(MODEL), "", (small.shape[1], small.shape[0]), 0.6, 0.3, 5000)
    _, faces = det.detect(small)
    if faces is None or len(faces) == 0:
        return None
    x, y, fw, fh = max(faces, key=lambda f: f[2] * f[3])[:4] / s
    return (x + fw / 2, y + fh / 2, fw, fh)


def crop_around(img: Image.Image, cx: float, cy: float, w: int, h: int) -> Image.Image:
    """Crop a w×h box centred on (cx, cy), shifted inside the image bounds; pad if the image is too small."""
    W, H = img.size
    w, h = min(w, W), min(h, H)
    x0 = int(min(max(0, cx - w / 2), W - w))
    y0 = int(min(max(0, cy - h / 2), H - h))
    return img.crop((x0, y0, x0 + w, y0 + h))


def make_crops(img: Image.Image, face):
    W, H = img.size
    if face:
        cx, cy, fw, fh = face
        # Thumb: square, 2.6 face-heights tall, face sitting a little above centre.
        side = int(min(max(W, H), fh * 2.6))
        thumb = crop_around(img, cx, cy + fh * 0.15, side, side)
        # Splash: 3:2, as wide as fits, face in the upper middle.
        sw = int(min(W, max(fh * 4.2, side * 1.5)))
        sh = int(sw / 1.5)
        if sh > H:
            sh, sw = H, int(H * 1.5)
        splash = crop_around(img, cx, cy + fh * 0.25, sw, sh)
    else:
        side = min(W, H)
        thumb = crop_around(img, W / 2, side / 2, side, side)
        sw = min(W, int(H * 1.5))
        splash = crop_around(img, W / 2, sw / 3, sw, int(sw / 1.5))
    return thumb.resize((256, 256), Image.LANCZOS), splash.resize((600, 400), Image.LANCZOS)


def patch_units(unit: str, name: str, emoji: str | None, ability: str | None, folder: str) -> str:
    src = UNITS_TS.read_text()
    m = re.search(r'  def\(\n    "%s",\n    "([^"]+)",\n    "([^"]+)",(.*?)\n  \),' % re.escape(unit), src, re.S)
    if not m:
        sys.exit(f"unit id {unit!r} not found in {UNITS_TS}")
    block = m.group(0)
    old_name, old_emoji = m.group(1), m.group(2)
    new = block.replace(f'    "{unit}",\n    "{old_name}",\n    "{old_emoji}",', f'    "{unit}",\n    "{name}",\n    "{emoji or old_emoji}",', 1)
    # strip any existing art/photo/splash trailing args, then append photo + splash
    new = re.sub(r'(ability\("\w+", "[^"]+", [\d.]+\),)\n(?:    (?:undefined|"[^"]*"),\n)*  \),', r"\1\n  ),", new)
    if ability:
        new = re.sub(r'ability\("(\w+)", "[^"]+", ([\d.]+)\)', r'ability("\1", "%s", \2)' % ability.replace("\\", "\\\\"), new)
    new = new.replace("  ),", f'    undefined,\n    "/units/{folder}/photo.png",\n    "/units/{folder}/splash.png",\n  ),', 1) if new.rstrip().endswith("),") else new
    UNITS_TS.write_text(src.replace(block, new))
    return new


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("photo")
    ap.add_argument("--unit", required=True, help="existing unit id to re-skin (see roster.py)")
    ap.add_argument("--name", required=True)
    ap.add_argument("--ability", help="new ability name (keeps kind and power)")
    ap.add_argument("--emoji", help="fallback icon")
    ap.add_argument("--folder", help="public/units/<folder>; defaults to a slug of --name")
    ap.add_argument("--dry-run", action="store_true", help="write crops only, don't touch units.ts")
    args = ap.parse_args()

    photo = Path(args.photo)
    folder = args.folder or re.sub(r"[^a-z0-9]+", "-", args.name.lower()).strip("-")
    img = load_image(photo)
    face = detect_face(img)
    thumb, splash = make_crops(img, face)
    out = ROOT / "public" / "units" / folder
    out.mkdir(parents=True, exist_ok=True)
    thumb.save(out / "photo.png")
    splash.save(out / "splash.png")

    info = {
        "photo": str(photo),
        "size": img.size,
        "face": None if face is None else [round(v) for v in face],
        "out": f"public/units/{folder}/",
    }
    if not args.dry_run:
        info["units_ts"] = patch_units(args.unit, args.name, args.emoji, args.ability, folder).strip()
    print(json.dumps(info, indent=2, ensure_ascii=False))
    if face is None:
        print("WARNING: no face detected; used a centre-top crop. Check the thumb.", file=sys.stderr)


if __name__ == "__main__":
    main()
