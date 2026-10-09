#!/usr/bin/env python
"""
Procedural 7×6 arena background in the painted, top-down style of the bundled maps.

  mapgen.py --id meadow --name "Sunlit Meadow" --theme forest --seed 3
  mapgen.py --id ashlands --name "Ashlands" --theme ember --seed 7 --no-register

Themes: forest, autumn, darkwoods, ember, tide, storm, void, iron, snow, desert.
Writes public/assets/maps/map_<id>_7x6.png (1344×1152, one 192px tile per cell) and, unless
--no-register, appends an entry with a matching page palette to src/game/data/maps.ts.
"""
from __future__ import annotations

import argparse
import math
import random
import re
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[4]
W, H, TILE = 1344, 1152, 192

# ground, ground2, bush, bush_dark, bush_light, rock, rock_dark, path, water, accent, page bg, glow, panel
THEMES = {
    "forest":    dict(ground=("#6f8f47", "#5c7a3a"), bush=("#4f7a34", "#2f4d1f", "#8fc25a"), rock=("#8b93a1", "#3b4150"), path="#8a7147", water="#3f7fa5", accent="#d9534f", bg="#08160d", glow="rgba(74, 222, 128, 0.16)", panel="rgba(16, 48, 28, 0.55)"),
    "autumn":    dict(ground=("#9a7c3d", "#7f6531"), bush=("#b8662a", "#6b3a16", "#e6a04a"), rock=("#8f8a96", "#3f3948"), path="#6e5433", water="#4b7d94", accent="#e04b2b", bg="#190c06", glow="rgba(251, 146, 60, 0.18)", panel="rgba(66, 30, 14, 0.55)"),
    "darkwoods": dict(ground=("#4b3f4f", "#3a3040"), bush=("#5a3a6a", "#2a1a33", "#9a5ab0"), rock=("#6a6472", "#2a2630"), path="#5c4a52", water="#3a4f7a", accent="#c94a8a", bg="#10081a", glow="rgba(168, 85, 247, 0.16)", panel="rgba(44, 22, 64, 0.55)"),
    "ember":     dict(ground=("#5a3a2e", "#47291f"), bush=("#7a3a1e", "#3a1a0c", "#e0742a"), rock=("#3f3336", "#1c1416"), path="#8a5a3a", water="#e05a1e", accent="#ffb347", bg="#1a0806", glow="rgba(249, 115, 22, 0.2)", panel="rgba(70, 24, 12, 0.55)"),
    "tide":      dict(ground=("#c9b57e", "#b5a06a"), bush=("#4f9a7a", "#2a5a45", "#8fdcb8"), rock=("#7f8a90", "#3a4448"), path="#d8c99a", water="#3f9ac9", accent="#ff8a65", bg="#061627", glow="rgba(56, 189, 248, 0.18)", panel="rgba(12, 40, 64, 0.55)"),
    "storm":     dict(ground=("#5a6a7a", "#48586a"), bush=("#3f5a6a", "#22323f", "#8ab0c8"), rock=("#7a8494", "#2e3540"), path="#6f7f8f", water="#2f5f8f", accent="#ffe86b", bg="#0e1020", glow="rgba(129, 140, 248, 0.18)", panel="rgba(30, 32, 70, 0.55)"),
    "void":      dict(ground=("#2e2440", "#241b33"), bush=("#4a2f6a", "#1e1230", "#b27cff"), rock=("#4f4a62", "#1c1826"), path="#3a2e4e", water="#5b2a8a", accent="#ff5ad9", bg="#07060f", glow="rgba(192, 132, 252, 0.16)", panel="rgba(40, 20, 60, 0.55)"),
    "iron":      dict(ground=("#5f6266", "#4c4f54"), bush=("#5a6a4a", "#2f3a28", "#9fb08a"), rock=("#8a8f96", "#33373d"), path="#7a7d82", water="#4a6a7a", accent="#e0b25a", bg="#15171b", glow="rgba(203, 213, 225, 0.14)", panel="rgba(40, 44, 52, 0.55)"),
    "snow":      dict(ground=("#dfe6ec", "#c8d2da"), bush=("#3f6a5a", "#22403a", "#dff5ff"), rock=("#9aa4ad", "#4a545c"), path="#b8c4cc", water="#7fbfe0", accent="#ff6b6b", bg="#0b1420", glow="rgba(186, 230, 253, 0.18)", panel="rgba(30, 50, 70, 0.55)"),
    "neon":      dict(ground=("#17121f", "#0d0a13"), bush=("#3a1e4e", "#1a0d24", "#ff5ad9"), rock=("#2a2733", "#100e14"), path="#2a2136", water="#7a2bd6", accent="#ff3fbf", bg="#0a0611", glow="rgba(255, 63, 191, 0.2)", panel="rgba(52, 16, 60, 0.6)"),
    "desert":    dict(ground=("#d9b86c", "#c4a35a"), bush=("#7a8a3a", "#4a5a22", "#c8d86a"), rock=("#b08a5a", "#5a4228"), path="#e6cc8a", water="#3fa0b8", accent="#e05a3a", bg="#1c1206", glow="rgba(251, 191, 36, 0.16)", panel="rgba(70, 48, 16, 0.55)"),
}


def hexrgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))


def noise(w, h, rnd, octaves=4, base=6):
    """Cheap value noise in [0,1]."""
    acc = np.zeros((h, w), np.float32)
    amp, total = 1.0, 0.0
    for o in range(octaves):
        n = base * 2**o
        grid = rnd.random((n + 1, n + 1)).astype(np.float32)
        img = Image.fromarray((grid * 255).astype(np.uint8)).resize((w, h), Image.BICUBIC)
        acc += np.asarray(img, np.float32) / 255 * amp
        total += amp
        amp *= 0.5
    return acc / total


def bush(d, cx, cy, r, cols, rnd):
    dark, mid, light = cols[1], cols[0], cols[2]
    pts = [(cx + rnd.uniform(-r * 0.5, r * 0.5), cy + rnd.uniform(-r * 0.5, r * 0.5), rnd.uniform(r * 0.45, r * 0.75)) for _ in range(6)]
    for x, y, rr in pts:
        d.ellipse((x - rr - 5, y - rr - 5, x + rr + 5, y + rr + 5), fill=dark)
    for x, y, rr in pts:
        d.ellipse((x - rr, y - rr, x + rr, y + rr), fill=mid)
    for x, y, rr in pts:
        for _ in range(4):
            px, py = x + rnd.uniform(-rr * 0.6, rr * 0.6), y + rnd.uniform(-rr * 0.6, rr * 0.6)
            d.ellipse((px - 3, py - 3, px + 3, py + 3), fill=light)


def rock(d, cx, cy, r, cols, rnd):
    light, dark = cols
    n = rnd.randint(6, 8)
    pts = [(cx + math.cos(a) * r * rnd.uniform(0.7, 1.1), cy + math.sin(a) * r * rnd.uniform(0.55, 0.9)) for a in np.linspace(0, 2 * math.pi, n, endpoint=False)]
    d.polygon(pts, fill=light, outline=dark, width=6)
    inner = [(cx + (x - cx) * 0.55 + r * 0.1, cy + (y - cy) * 0.5 - r * 0.15) for x, y in pts]
    d.polygon(inner, fill=tuple(min(255, c + 22) for c in light))
    for _ in range(3):
        x, y = cx + rnd.uniform(-r * 0.4, r * 0.4), cy + rnd.uniform(-r * 0.3, r * 0.3)
        d.line((x, y, x + rnd.uniform(-r * 0.3, r * 0.3), y + rnd.uniform(-r * 0.2, r * 0.2)), fill=dark, width=3)


def path(d, rnd, col, width=70):
    x = rnd.uniform(W * 0.3, W * 0.7)
    pts = [(x, -50)]
    y = -50
    while y < H + 50:
        y += rnd.uniform(90, 150)
        x += rnd.uniform(-160, 160)
        x = min(max(x, W * 0.15), W * 0.85)
        pts.append((x, y))
    # Smooth the waypoints with Catmull-Rom so the trail bends instead of zig-zagging.
    P = [pts[0]] + pts + [pts[-1]]
    smooth = []
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        for t in np.linspace(0, 1, 12, endpoint=False):
            t2, t3 = t * t, t * t * t
            smooth.append(tuple(0.5 * ((2 * p1[k]) + (-p0[k] + p2[k]) * t + (2 * p0[k] - 5 * p1[k] + 4 * p2[k] - p3[k]) * t2 + (-p0[k] + 3 * p1[k] - 3 * p2[k] + p3[k]) * t3) for k in (0, 1)))
    smooth.append(pts[-1])
    dark = tuple(max(0, c - 30) for c in col)
    d.line(smooth, fill=dark, width=width + 14, joint="curve")
    d.line(smooth, fill=col, width=width, joint="curve")
    for x, y in pts[1:-1]:
        for _ in range(3):
            px, py = x + rnd.uniform(-width * 0.4, width * 0.4), y + rnd.uniform(-40, 40)
            d.ellipse((px - 4, py - 3, px + 4, py + 3), fill=dark)


def pond(d, rnd, col):
    cx, cy = rnd.uniform(W * 0.2, W * 0.8), rnd.uniform(H * 0.25, H * 0.75)
    rx, ry = rnd.uniform(90, 150), rnd.uniform(60, 100)
    dark = tuple(max(0, c - 40) for c in col)
    d.ellipse((cx - rx - 10, cy - ry - 10, cx + rx + 10, cy + ry + 10), fill=dark)
    d.ellipse((cx - rx, cy - ry, cx + rx, cy + ry), fill=col)
    d.ellipse((cx - rx * 0.5, cy - ry * 0.5, cx + rx * 0.3, cy - ry * 0.1), fill=tuple(min(255, c + 40) for c in col))
    for a in np.linspace(0, 2 * math.pi, 9, endpoint=False):
        x, y = cx + math.cos(a) * (rx + 14), cy + math.sin(a) * (ry + 12)
        d.ellipse((x - 9, y - 7, x + 9, y + 7), fill=(120, 124, 132), outline=(60, 62, 70), width=2)


def hexa(h):
    return hexrgb(h)


def glow_ellipse(base: Image.Image, cx, cy, rx, ry, col, alpha=140, blur=40):
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).ellipse((cx - rx, cy - ry, cx + rx, cy + ry), fill=col + (alpha,))
    layer = layer.filter(ImageFilter.GaussianBlur(blur))
    return Image.alpha_composite(base.convert("RGBA"), layer)


def generate_stage(theme: str, seed: int, features: dict) -> Image.Image:
    """Concert floor: LED dance tiles, neon edge strips, a raised stage across the far end,
    speaker stacks, spotlights and confetti. Grid cells stay readable: tiles are subtle, lights sit at the edges."""
    t = THEMES[theme]
    rnd = random.Random(seed)
    g1, g2 = hexrgb(t["ground"][0]), hexrgb(t["ground"][1])
    acc, acc2 = hexrgb(t["accent"]), hexrgb(t["water"])
    img = Image.new("RGBA", (W, H), g2 + (255,))
    d = ImageDraw.Draw(img)
    # dance floor: 96px LED tiles with a faint random glow per tile
    tile = TILE // 2
    for y in range(0, H, tile):
        for x in range(0, W, tile):
            k = rnd.random()
            col = g1 if k < 0.75 else tuple(int(a * 0.55 + b * 0.45) for a, b in zip(g1, acc if k < 0.9 else acc2))
            d.rectangle((x + 3, y + 3, x + tile - 3, y + tile - 3), fill=col)
    # stage: raised platform across the top row, with a front edge and steps
    stage_h = int(TILE * 1.15)
    d.rectangle((0, 0, W, stage_h), fill=hexrgb(t["path"]))
    d.rectangle((0, stage_h - 22, W, stage_h), fill=tuple(max(0, c - 18) for c in hexrgb(t["path"])))
    d.rectangle((0, stage_h, W, stage_h + 10), fill=(8, 6, 12))
    for x in range(0, W, 48):
        d.line((x, 0, x, stage_h - 22), fill=tuple(max(0, c - 10) for c in hexrgb(t["path"])), width=2)
    # truss + par lights on the stage back
    d.rectangle((0, 0, W, 26), fill=(30, 28, 36))
    for i in range(9):
        x = int(W * (i + 0.5) / 9)
        d.rectangle((x - 14, 4, x + 14, 26), fill=(50, 48, 58))
        img = glow_ellipse(img, x, 34, 22, 14, acc if i % 2 else acc2, 200, 10)
        d = ImageDraw.Draw(img)
    # spotlight cones from the truss onto the floor
    for i in range(int(features.get("spots", 4))):
        x0 = rnd.uniform(W * 0.1, W * 0.9)
        x1 = x0 + rnd.uniform(-260, 260)
        y1 = rnd.uniform(H * 0.45, H * 0.95)
        cone = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(cone).polygon([(x0 - 8, 26), (x0 + 8, 26), (x1 + 150, y1), (x1 - 150, y1)], fill=(acc if i % 2 else acc2) + (46,))
        cone = cone.filter(ImageFilter.GaussianBlur(26))
        img = Image.alpha_composite(img, cone)
        img = glow_ellipse(img, x1, y1, 170, 60, acc if i % 2 else acc2, 90, 50)
    d = ImageDraw.Draw(img)
    # neon edge strips down both sides and along the bottom
    for (x0, y0, x1, y1) in ((0, stage_h + 10, 10, H), (W - 10, stage_h + 10, W, H), (0, H - 10, W, H)):
        img = glow_ellipse(img, (x0 + x1) / 2, (y0 + y1) / 2, max(24, (x1 - x0) / 2 + 20), max(24, (y1 - y0) / 2 + 20), acc, 110, 30)
        ImageDraw.Draw(img).rectangle((x0, y0, x1, y1), fill=acc)
    d = ImageDraw.Draw(img)
    # speaker stacks in the two stage corners and the two floor corners
    def speaker(x, y, w=110, h=150):
        d.rectangle((x, y, x + w, y + h), fill=(24, 22, 28), outline=(60, 58, 68), width=4)
        for cy, r in ((y + h * 0.32, w * 0.3), (y + h * 0.74, w * 0.2)):
            d.ellipse((x + w / 2 - r, cy - r, x + w / 2 + r, cy + r), fill=(14, 12, 18), outline=(80, 78, 90), width=3)
            d.ellipse((x + w / 2 - r * 0.3, cy - r * 0.3, x + w / 2 + r * 0.3, cy + r * 0.3), fill=(70, 66, 80))
    speaker(24, 30); speaker(W - 134, 30)
    speaker(28, H - 190, 96, 150); speaker(W - 124, H - 190, 96, 150)
    # confetti
    cols = [acc, acc2, (255, 235, 120), (120, 230, 255), (255, 255, 255)]
    for _ in range(int(features.get("sprinkles", 140))):
        x, y = rnd.uniform(0, W), rnd.uniform(stage_h, H)
        c = rnd.choice(cols)
        a = rnd.uniform(0, math.pi)
        dx, dy = math.cos(a) * 7, math.sin(a) * 7
        d.line((x - dx, y - dy, x + dx, y + dy), fill=c, width=4)
    # haze + vignette
    vig = Image.new("L", (W, H), 0)
    ImageDraw.Draw(vig).ellipse((-W * 0.15, -H * 0.25, W * 1.15, H * 1.25), fill=255)
    vig = vig.filter(ImageFilter.GaussianBlur(200))
    dark = Image.new("RGBA", (W, H), tuple(int(c * 0.5) for c in g2) + (255,))
    img = Image.composite(img, dark, vig)
    return img.convert("RGB")


def generate(theme: str, seed: int, features: dict) -> Image.Image:
    t = THEMES[theme]
    rnd = random.Random(seed)
    nrnd = np.random.default_rng(seed)
    g1, g2 = hexrgb(t["ground"][0]), hexrgb(t["ground"][1])
    n = noise(W, H, nrnd)[..., None]
    ground = (np.array(g1) * n + np.array(g2) * (1 - n)).astype(np.uint8)
    # fine speckle
    spk = (nrnd.random((H, W, 1)) * 18 - 9).astype(np.int16)
    ground = np.clip(ground.astype(np.int16) + spk, 0, 255).astype(np.uint8)
    img = Image.fromarray(ground, "RGB")
    d = ImageDraw.Draw(img)

    if features.get("path", True):
        path(d, rnd, hexrgb(t["path"]))
    if features.get("pond", True) and rnd.random() < 0.7:
        pond(d, rnd, hexrgb(t["water"]))

    bush_cols = tuple(hexrgb(c) for c in t["bush"])
    rock_cols = tuple(hexrgb(c) for c in t["rock"])
    # Border foliage so the arena reads as a clearing, then scattered mid-field props.
    for i in range(int(features.get("bushes", 26))):
        edge = rnd.random() < 0.6
        if edge:
            side = rnd.choice("tblr")
            cx = rnd.uniform(0, W) if side in "tb" else (rnd.uniform(-20, 80) if side == "l" else rnd.uniform(W - 80, W + 20))
            cy = rnd.uniform(0, H) if side in "lr" else (rnd.uniform(-20, 80) if side == "t" else rnd.uniform(H - 80, H + 20))
        else:
            cx, cy = rnd.uniform(60, W - 60), rnd.uniform(60, H - 60)
        bush(d, cx, cy, rnd.uniform(55, 95), bush_cols, rnd)
    for i in range(int(features.get("rocks", 7))):
        rock(d, rnd.uniform(80, W - 80), rnd.uniform(80, H - 80), rnd.uniform(45, 90), rock_cols, rnd)
    # accent sprinkles (flowers / embers / crystals)
    acc = hexrgb(t["accent"])
    for _ in range(int(features.get("sprinkles", 18))):
        x, y = rnd.uniform(0, W), rnd.uniform(0, H)
        d.ellipse((x - 5, y - 5, x + 5, y + 5), fill=acc)
        d.ellipse((x - 2, y - 2, x + 2, y + 2), fill=(255, 255, 255))

    # painterly softening + vignette
    img = img.filter(ImageFilter.GaussianBlur(0.6))
    vig = Image.new("L", (W, H), 0)
    ImageDraw.Draw(vig).ellipse((-W * 0.2, -H * 0.2, W * 1.2, H * 1.2), fill=255)
    vig = vig.filter(ImageFilter.GaussianBlur(220))
    dark = Image.new("RGB", (W, H), tuple(int(c * 0.6) for c in g2))
    img = Image.composite(img, dark, vig)
    return img


def register(mid: str, name: str, theme: str):
    ts = ROOT / "src" / "game" / "data" / "maps.ts"
    src = ts.read_text()
    if f'id: "{mid}"' in src:
        return "already registered"
    t = THEMES[theme]
    entry = f'''  {{
    id: "{mid}",
    name: "{name}",
    file: "/assets/maps/map_{mid}_7x6.png",
    palette: {{ bg: "{t['bg']}", glow: "{t['glow']}", panel: "{t['panel']}" }},
  }},
'''
    src2 = re.sub(r"(export const MAPS: ArenaMap\[\] = \[\n(?:.*\n)*?)(\];)", lambda m: m.group(1) + entry + m.group(2), src, count=1)
    ts.write_text(src2)
    return "registered in src/game/data/maps.ts"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--theme", default="forest", choices=sorted(THEMES))
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--bushes", type=int, default=26)
    ap.add_argument("--rocks", type=int, default=7)
    ap.add_argument("--sprinkles", type=int, default=18)
    ap.add_argument("--no-path", action="store_true")
    ap.add_argument("--no-pond", action="store_true")
    ap.add_argument("--no-register", action="store_true")
    ap.add_argument("--style", default="nature", choices=["nature", "stage"], help="nature = painted clearing; stage = concert floor")
    ap.add_argument("--spots", type=int, default=4, help="spotlight cones (stage style)")
    args = ap.parse_args()

    feats = dict(bushes=args.bushes, rocks=args.rocks, sprinkles=args.sprinkles, path=not args.no_path, pond=not args.no_pond, spots=args.spots)
    img = generate_stage(args.theme, args.seed, feats) if args.style == "stage" else generate(args.theme, args.seed, feats)
    out = ROOT / "public" / "assets" / "maps" / f"map_{args.id}_7x6.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    print(f"wrote {out.relative_to(ROOT)}  ({W}×{H}, theme {args.theme}, seed {args.seed})")
    if not args.no_register:
        print(register(args.id, args.name, args.theme))


if __name__ == "__main__":
    main()
