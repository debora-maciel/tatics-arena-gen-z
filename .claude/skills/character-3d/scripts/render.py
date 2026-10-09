"""
Software renderer for character parts: orthographic camera, per-pixel smooth shading with a
soft two-tone ramp, rim light, z-buffer, depth-edge lines, silhouette outline, ground contact
shadow, transparent background. Only numpy + Pillow. Produces the six views the game uses.

A part is (name, trimesh, rgba) or (name, trimesh, rgba, vertex_colors[N,3] float 0..1).
"""
from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

# Camera directions (unit vector from model centre towards the camera).
VIEWS = {
    "front": (0.0, 0.0, 1.0),
    "back": (0.0, 0.0, -1.0),
    "east": (-1.0, 0.0, 0.0),  # character faces screen-right
    "west": (1.0, 0.0, 0.0),
    "board": (0.0, 0.7, 0.714),  # 45° above, from the front (TFT board camera)
}


def _basis(cam_dir):
    d = np.asarray(cam_dir, float)
    d /= np.linalg.norm(d)
    fwd = -d
    up = np.array([0.0, 1.0, 0.0])
    right = np.cross(fwd, up)
    if np.linalg.norm(right) < 1e-6:
        right = np.array([1.0, 0.0, 0.0])
    right /= np.linalg.norm(right)
    up = np.cross(right, fwd)
    return right, up, fwd


# Per-part material from the part name: (specular strength, shininess, grain amplitude, grain kind)
MATERIALS = {
    "skin": (0.10, 18, 0.018, "fine"),
    "hair": (0.12, 60, 0.10, "strand"),
    "cloth": (0.06, 8, 0.07, "weave"),
    "leather": (0.35, 26, 0.04, "fine"),
    "metal": (0.65, 60, 0.02, "fine"),
    "eye": (0.6, 80, 0.0, "fine"),
}
_MAT_PREFIX = [
    (("body", "neck", "ear", "nose", "lip", "hand", "arm", "leg", "thigh", "shin", "foot", "midriff", "waist", "torso", "shoulder", "elbow", "knee", "blush", "brow"), "skin"),
    (("strand", "lock", "scalp", "bang", "part_", "tail", "tuft", "spike", "curl", "bun", "hawk", "hair"), "hair"),
    (("boot", "shoe", "sole", "strap", "jacket", "glove", "gauntlet", "bag", "belt", "collar_", "pouch", "heel"), "leather"),
    (("blade", "guard", "grip", "buckle", "crown", "bracelet", "necklace", "pendant", "earring", "knuckle", "halo", "tie_", "rim_", "bridge", "shades", "chest_plate", "pauldron", "orb", "star", "boss", "mic_head"), "metal"),
    (("eye_", "iris", "pupil", "lens"), "eye"),
]


def material_for(name: str):
    for prefixes, mat in _MAT_PREFIX:
        if name.startswith(prefixes):
            return MATERIALS[mat]
    return MATERIALS["cloth"]


def _smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def render(parts, cam_dir, size=1024, model_height=None, cel=True, outline=True, light=(-0.45, 0.75, 0.6), margin=0.08, shadow=True, recenter=True, center=None):
    right, up, fwd = _basis(cam_dir)
    L = np.asarray(light, float)
    L /= np.linalg.norm(L)
    view = -fwd

    allv = np.vstack([p[1].vertices for p in parts])
    lo, hi = allv.min(0), allv.max(0)
    center = (lo + hi) / 2 if center is None else np.asarray(center, float)
    height = model_height or (hi[1] - lo[1])
    scale = size * (1 - 2 * margin) / height

    color = np.zeros((size, size, 3), np.float32)
    alpha = np.zeros((size, size), bool)
    zbuf = np.full((size, size), np.inf, np.float32)
    H = L + view
    H /= np.linalg.norm(H)
    rng = np.random.default_rng(11)
    grain_fine = rng.random((size, size), np.float32)
    # woven cloth: two crossed sine grids; strand hair: smoothed per-column noise (vertical streaks)
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    grain_weave = (np.sin(xx * 1.9) * np.sin(yy * 1.9)) * 0.5 + 0.5
    col_noise = rng.random(size, np.float32)
    k = np.ones(3) / 3
    col_noise = np.convolve(col_noise, k, mode="same")
    grain_strand = np.tile(col_noise, (size, 1)) * 0.6 + grain_fine * 0.4
    grains = {"fine": grain_fine, "weave": grain_weave, "strand": grain_strand}
    shadow_tint = np.array([0.88, 0.86, 1.0], np.float32)

    for part in parts:
        mesh, rgba = part[1], part[2]
        vcol = part[3] if len(part) > 3 and part[3] is not None else None
        spec_k, shin, grain_amp, grain_kind = material_for(part[0])
        two_sided = bool(part[4].get("two_sided")) if len(part) > 4 and isinstance(part[4], dict) else False
        grain = grains[grain_kind]
        base = np.asarray(rgba[:3], np.float32) / 255
        V = mesh.vertices - center
        X = V @ right * scale + size / 2
        Y = size / 2 - V @ up * scale
        Z = V @ fwd
        VN = mesh.vertex_normals
        FN = mesh.face_normals
        facing = FN @ view
        for fi, f in enumerate(mesh.faces):
            flip = False
            if facing[fi] <= -0.05:
                if not two_sided:
                    continue
                flip = True
            x0, x1, x2 = X[f]
            y0, y1, y2 = Y[f]
            minx, maxx = int(max(0, np.floor(min(x0, x1, x2)))), int(min(size - 1, np.ceil(max(x0, x1, x2))))
            miny, maxy = int(max(0, np.floor(min(y0, y1, y2)))), int(min(size - 1, np.ceil(max(y0, y1, y2))))
            if minx > maxx or miny > maxy:
                continue
            area = (x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0)
            if abs(area) < 1e-9:
                continue
            px = np.arange(minx, maxx + 1) + 0.5
            py = np.arange(miny, maxy + 1) + 0.5
            PX, PY = np.meshgrid(px, py)
            w0 = ((x1 - PX) * (y2 - PY) - (x2 - PX) * (y1 - PY)) / area
            w1 = ((x2 - PX) * (y0 - PY) - (x0 - PX) * (y2 - PY)) / area
            w2 = 1 - w0 - w1
            inside = (w0 >= -1e-4) & (w1 >= -1e-4) & (w2 >= -1e-4)
            if not inside.any():
                continue
            z = w0 * Z[f[0]] + w1 * Z[f[1]] + w2 * Z[f[2]]
            sub = zbuf[miny : maxy + 1, minx : maxx + 1]
            upd = inside & (z < sub)
            if not upd.any():
                continue
            # per-pixel normal
            n = w0[..., None] * VN[f[0]] + w1[..., None] * VN[f[1]] + w2[..., None] * VN[f[2]]
            n /= np.linalg.norm(n, axis=-1, keepdims=True) + 1e-9
            if flip:
                n = -n
            diff = n @ L
            if cel:
                # three bands: core shadow 0.5, mid 0.72, lit 1.0, with soft edges; shadow is cooled by shadow_tint
                lit = _smoothstep(0.08, 0.32, diff)
                mid = _smoothstep(-0.25, -0.02, diff)
                shade = 0.5 + 0.22 * mid + 0.28 * lit
            else:
                shade = 0.45 + 0.55 * np.clip(diff, 0, 1)
            tint = shadow_tint[None, None, :] * (1 - lit[..., None]) + (1 - lit[..., None] * 0) * 0 + lit[..., None] * 1.0
            # rim light on grazing normals (top-left key)
            ndv = np.clip(n @ view, 0, 1)
            rim = (1 - ndv) ** 3 * 0.3 * _smoothstep(-0.2, 0.4, diff)
            # specular (Blinn-Phong), cel-stepped so it reads as a painted highlight
            ndh = np.clip(n @ H, 0, 1)
            spec = spec_k * _smoothstep(0.55, 0.75, ndh ** (shin / 8))
            if vcol is not None:
                col = w0[..., None] * vcol[f[0]] + w1[..., None] * vcol[f[1]] + w2[..., None] * vcol[f[2]]
            else:
                col = base
            g = grain[miny : maxy + 1, minx : maxx + 1]
            texture = 1 + (g - 0.5) * grain_amp * 2
            out = np.clip(col * (shade * texture)[..., None] * tint + rim[..., None] + spec[..., None], 0, 1)
            sub[upd] = z[upd]
            color[miny : maxy + 1, minx : maxx + 1][upd] = out[upd]
            alpha[miny : maxy + 1, minx : maxx + 1] |= upd

    # ambient occlusion from the depth buffer: pixels deeper than their neighbourhood sit in creases
    if alpha.any():
        from scipy.ndimage import uniform_filter
        zf = np.where(alpha, zbuf, 0).astype(np.float32)
        k = max(5, size // 40) | 1
        num = uniform_filter(zf, k)
        den = uniform_filter(alpha.astype(np.float32), k)
        zmean = num / np.maximum(den, 1e-3)
        occ = np.clip((zbuf - zmean) * 9.0, 0, 1) * alpha
        color *= (1 - 0.4 * occ)[..., None]

    img = np.zeros((size, size, 4), np.uint8)
    img[..., :3] = (np.clip(color, 0, 1) * 255).astype(np.uint8)
    img[..., 3] = alpha * 255

    if outline:
        zf = np.where(alpha, zbuf, np.nan)
        gy = np.abs(np.diff(zf, axis=0, prepend=zf[:1]))
        gx = np.abs(np.diff(zf, axis=1, prepend=zf[:, :1]))
        step = (np.nan_to_num(gx, nan=0) > 0.08) | (np.nan_to_num(gy, nan=0) > 0.08)
        img[step & alpha, :3] = (img[step & alpha, :3] * 0.6).astype(np.uint8)
        a = Image.fromarray(img[..., 3])
        k = max(3, int(size / 180)) | 1
        dil = np.array(a.filter(ImageFilter.MaxFilter(k)))
        edge = (dil > 0) & ~alpha
        img[edge] = (24, 18, 30, 255)

    # Recentre the drawing in the canvas so every view is framed the same way.
    a = img[..., 3] > 0
    if recenter and a.any():
        rows = np.where(a.any(1))[0]
        cols = np.where(a.any(0))[0]
        dy = size // 2 - (rows[0] + rows[-1]) // 2
        dx = size // 2 - (cols[0] + cols[-1]) // 2
        img = np.roll(img, (dy, dx), axis=(0, 1))

    out = Image.fromarray(img, "RGBA")
    if shadow and cam_dir[1] > 0.1:
        # soft contact shadow under the feet, for views that see the ground
        a = np.array(out)[..., 3] > 0
        rows = np.where(a.any(1))[0]
        cols = np.where(a.any(0))[0]
        foot_y = rows[-1]
        cx = (cols[0] + cols[-1]) / 2
        w = (cols[-1] - cols[0]) * 0.55
        sh = Image.new("RGBA", out.size, (0, 0, 0, 0))
        ImageDraw.Draw(sh).ellipse((cx - w / 2, foot_y - w * 0.14, cx + w / 2, foot_y + w * 0.14), fill=(10, 8, 14, 150))
        sh = sh.filter(ImageFilter.GaussianBlur(size / 120))
        out = Image.alpha_composite(sh, out)
    return out


def portrait(front_img: Image.Image, side_fraction=0.52):
    """Square crop of the head and shoulders from the front render; side is a fraction of the figure's height."""
    a = np.array(front_img)[..., 3] > 0
    rows = np.where(a.any(1))[0]
    cols = np.where(a.any(0))[0]
    top, bottom = rows[0], rows[-1]
    h = bottom - top
    side = int(h * side_fraction)
    cx = int((cols[0] + cols[-1]) / 2)
    box = (cx - side // 2, max(0, top - side // 10), cx + side // 2, max(0, top - side // 10) + side)
    return front_img.crop(box)
