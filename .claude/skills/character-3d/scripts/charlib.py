"""
Parametric character builder for Tactics Arena (v2).

Anatomy comes from lathe surfaces (elliptical rings along a profile) posed on a small
forward-kinematics skeleton, so a figure has a chest, waist, hips, thighs, calves and
joints, and poses are data. Hair is strand clumps laid on the skull, cloth is lathe
garments with hems/pleats/prints, and every part carries painted vertex gradients.

Coordinates: Y up, character faces +Z. Parts are (name, mesh, rgba, vertex_colors).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import trimesh
from trimesh.creation import box, icosphere, torus
from trimesh.transformations import rotation_matrix, translation_matrix

# ─── colour ────────────────────────────────────────────────────────────────────

def rgba(v, default="#888888"):
    v = v or default
    if isinstance(v, (list, tuple)):
        return [int(x) for x in v][:3] + [255]
    h = v.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return [int(h[i : i + 2], 16) for i in (0, 2, 4)] + [255]


def shade(c, k):
    return [max(0, min(255, int(x * k))) for x in c[:3]] + [255]


def f3(c):
    return np.asarray(c[:3], np.float32) / 255


# ─── transforms ────────────────────────────────────────────────────────────────

def M(x=0.0, y=0.0, z=0.0, rx=0.0, ry=0.0, rz=0.0):
    """Translate ∘ Rz ∘ Ry ∘ Rx as a 4×4 matrix (rotations in degrees)."""
    m = translation_matrix([x, y, z])
    for ang, axis in ((rz, [0, 0, 1]), (ry, [0, 1, 0]), (rx, [1, 0, 0])):
        if ang:
            m = m @ rotation_matrix(math.radians(ang), axis)
    return m


def xf(mesh, m, sx=1.0, sy=1.0, sz=1.0):
    out = mesh.copy()
    if (sx, sy, sz) != (1.0, 1.0, 1.0):
        S = np.eye(4)
        S[0, 0], S[1, 1], S[2, 2] = sx, sy, sz
        out.apply_transform(S)
    out.apply_transform(m)
    return out


def pt(m, x=0.0, y=0.0, z=0.0):
    return (m @ np.array([x, y, z, 1.0]))[:3]


# ─── surfaces ──────────────────────────────────────────────────────────────────

def lathe(rings, segments=28, wave=None, caps=(True, True)):
    """
    Closed surface of revolution around local Y with elliptical cross-sections.
    rings: [(y, rx, rz)] from bottom to top. wave(i, theta) → radius multiplier for pleats/hems.
    Returns (mesh, local_vertices) so callers can paint by local position.
    """
    n = segments
    th = np.linspace(0, 2 * math.pi, n, endpoint=False)
    V = []
    for i, (y, rx, rz) in enumerate(rings):
        f = np.ones(n) if wave is None else np.array([wave(i, t) for t in th])
        V.append(np.stack([rx * f * np.cos(th), np.full(n, y), rz * f * np.sin(th)], 1))
    V = np.vstack(V)
    F = []
    for i in range(len(rings) - 1):
        for j in range(n):
            a, b = i * n + j, i * n + (j + 1) % n
            c, d = (i + 1) * n + (j + 1) % n, (i + 1) * n + j
            F += [[a, c, b], [a, d, c]]
    verts = [V]
    if caps[0]:
        cb = len(V)
        verts.append([[0, rings[0][0], 0]])
        F += [[cb, (j + 1) % n, j] for j in range(n)]
    if caps[1]:
        ct = sum(len(v) for v in verts)
        verts.append([[0, rings[-1][0], 0]])
        base = (len(rings) - 1) * n
        F += [[ct, base + j, base + (j + 1) % n] for j in range(n)]
    V = np.vstack([np.asarray(v, float) for v in verts])
    m = trimesh.Trimesh(V, np.asarray(F), process=False)
    m.fix_normals()
    return m


def segment(length, r0, r1, bulge=0.0, rings=6, flat=1.0):
    """Limb piece along -Y from 0 to -length; radius r0 at the joint, r1 at the far end, with a mid bulge."""
    rs = []
    for i in range(rings):
        t = i / (rings - 1)
        r = r0 * (1 - t) + r1 * t + bulge * math.sin(math.pi * t)
        rs.append((-length * t, r, r * flat))
    return lathe(rs[::-1], segments=20)  # bottom→top order


def clump(a, b, r, taper=0.35, segments=14):
    """Hair strand: tapered lathe from point a (thick) to point b (thin)."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    d = b - a
    L = np.linalg.norm(d)
    if L < 1e-6:
        return None
    m = lathe([(0, r * taper, r * taper * 0.8), (L * 0.4, r, r * 0.8), (L * 0.75, r * 0.85, r * 0.7), (L, r * 0.3, r * 0.25)], segments)
    # align local +Y with d
    y = d / L
    up = np.array([0, 0, 1.0]) if abs(y[1]) > 0.9 else np.array([0, 1.0, 0])
    x = np.cross(up, y)
    x /= np.linalg.norm(x)
    z = np.cross(x, y)
    R = np.eye(4)
    R[:3, 0], R[:3, 1], R[:3, 2] = x, y, z
    R[:3, 3] = a
    m.apply_transform(R)
    return m


def head_mesh(R, shape="oval", chin=1.0, cheeks=1.0):
    """
    Sculpted head: a subdivided sphere displaced into a human skull — taller than wide,
    flatter sides, tapered jaw, forward chin, cheekbones, flat forehead plane, full occiput.
    Returns (mesh, unit_verts) with the head centred at the origin; the face looks along +Z.
    """
    m = icosphere(4, 1.0)
    v = m.vertices.copy()
    x, y, z = v[:, 0], v[:, 1], v[:, 2]
    taper, jaw_w = {"oval": (0.46, 0.0), "heart": (0.55, 0.0), "square": (0.30, 0.08), "round": (0.30, 0.0)}[shape]
    down = np.clip(-y, 0, 1)
    front = np.clip(z, 0, 1)
    fx = 1 - taper * down ** 1.7 + jaw_w * np.exp(-((y + 0.6) / 0.25) ** 2)  # jaw width
    fz = 1 - 0.32 * down ** 1.8
    chin_m = np.exp(-((y + 0.92) / 0.22) ** 2) * front ** 0.5 * chin
    cheek = np.exp(-((y + 0.12) / 0.22) ** 2 - ((np.abs(x) - 0.72) / 0.22) ** 2) * front * 0.07 * cheeks
    brow = np.exp(-((y - 0.32) / 0.12) ** 2) * front * 0.04
    forehead = np.clip(y - 0.35, 0, 1) * front * 0.10
    occiput = np.clip(-z, 0, 1) * np.exp(-((y - 0.1) / 0.5) ** 2) * 0.12
    temple = np.exp(-((y - 0.25) / 0.3) ** 2) * (np.abs(x) > 0.6) * 0.05
    xs = x * 0.86 * fx + np.sign(x) * (cheek - temple)
    ys = y * 1.22 - chin_m * 0.10
    zs = z * fz + chin_m * 0.20 + brow - forehead - occiput * (z < 0) + (z < 0) * 0.0
    m.vertices = np.stack([xs, ys, zs], 1) * R
    m.fix_normals()
    return m, v


# ─── proportions ───────────────────────────────────────────────────────────────

@dataclass
class Prop:
    head_r: float
    head_y: float
    neck_len: float
    shoulder_y: float
    hip_y: float
    crotch_y: float
    shoulder_w: float      # half width at shoulders
    chest: tuple           # (rx, rz) at chest
    waist: tuple
    hips: tuple
    upper_arm: float
    forearm: float
    arm_r: float
    hand_r: float
    thigh: float
    shin: float
    thigh_r: float
    shin_r: float
    leg_x: float
    foot_len: float
    eye_dx: float = 0.36
    eye_r: float = 0.12
    hair_k: float = 1.0    # scale of hair pieces vs head


PRESETS = {
    "hero": Prop(head_r=0.30, head_y=2.66, neck_len=0.14, shoulder_y=2.24, hip_y=1.50, crotch_y=1.30, shoulder_w=0.40,
                 chest=(0.31, 0.21), waist=(0.23, 0.17), hips=(0.30, 0.22), upper_arm=0.48, forearm=0.42, arm_r=0.075, hand_r=0.08,
                 thigh=0.66, shin=0.60, thigh_r=0.15, shin_r=0.10, leg_x=0.14, foot_len=0.30),
    "chibi": Prop(head_r=0.42, head_y=1.55, neck_len=0.10, shoulder_y=1.10, hip_y=0.48, crotch_y=0.40, shoulder_w=0.34,
                  chest=(0.28, 0.21), waist=(0.24, 0.18), hips=(0.30, 0.22), upper_arm=0.30, forearm=0.26, arm_r=0.085, hand_r=0.09,
                  thigh=0.22, shin=0.20, thigh_r=0.11, shin_r=0.09, leg_x=0.14, foot_len=0.28, eye_dx=0.36, eye_r=0.15, hair_k=1.0),
}

BUILDS = {  # multipliers on (shoulder_w, chest, waist, hips, limb radii)
    "slim": (0.95, 0.95, 0.92, 0.95, 0.9),
    "average": (1.0, 1.0, 1.0, 1.0, 1.0),
    "athletic": (1.08, 1.06, 0.98, 1.0, 1.08),
    "heavy": (1.15, 1.2, 1.25, 1.2, 1.25),
}

# bone rotations (rx, ry, rz) in degrees; rest = limbs hanging along -Y
POSES = {
    "idle": {"upper_arm_L": (-4, 0, -12), "upper_arm_R": (-4, 0, 12), "forearm_L": (-18, 0, 0), "forearm_R": (-18, 0, 0),
             "thigh_L": (0, 0, -4), "thigh_R": (0, 0, 4)},
    "ready": {"upper_arm_L": (-25, 0, -18), "upper_arm_R": (-70, 0, 22), "forearm_L": (-30, 0, 0), "forearm_R": (-70, 0, 0),
              "thigh_L": (8, 0, -9), "thigh_R": (-6, 0, 9), "shin_L": (-8, 0, 0)},
    "hand_on_hip": {"upper_arm_L": (0, 0, -38), "upper_arm_R": (-4, 0, 12), "forearm_L": (0, 0, 92), "forearm_R": (-18, 0, 0),
                    "thigh_L": (0, 0, -3), "thigh_R": (0, 0, 8)},
    "cast": {"upper_arm_L": (-75, 0, -20), "upper_arm_R": (-75, 0, 20), "forearm_L": (-30, 0, 0), "forearm_R": (-30, 0, 0),
             "thigh_L": (0, 0, -8), "thigh_R": (0, 0, 8)},
    "brace": {"upper_arm_L": (-40, 0, -25), "upper_arm_R": (-40, 0, 25), "forearm_L": (-110, 0, 10), "forearm_R": (-110, 0, -10),
              "thigh_L": (6, 0, -12), "thigh_R": (-4, 0, 12), "shin_R": (-6, 0, 0)},
}


# ─── builder ───────────────────────────────────────────────────────────────────

class Character:
    def __init__(self, spec: dict):
        self.spec = spec
        pr = spec.get("proportions", {})
        base = PRESETS[pr.get("preset", "hero")]
        self.P = P = Prop(**{**base.__dict__})
        P.head_r *= float(pr.get("head", 1.0))
        bw, bc, bwst, bh, br = BUILDS[pr.get("build", "average")]
        P.shoulder_w *= bw
        P.chest = (P.chest[0] * bc, P.chest[1] * bc)
        P.waist = (P.waist[0] * bwst, P.waist[1] * bwst)
        P.hips = (P.hips[0] * bh, P.hips[1] * bh)
        P.arm_r *= br
        P.thigh_r *= br
        P.shin_r *= br
        self.parts: list = []
        self.bones: dict[str, np.ndarray] = {}
        self.skin = rgba(spec.get("skin"), "#f5dccb")
        pose = spec.get("pose", "idle")
        self.pose = {**POSES["idle"], **POSES.get(pose, {})} if isinstance(pose, str) else {**POSES["idle"], **pose}

    # ── helpers ──
    def add(self, name, mesh, color, paint=None, gradient=True, local=None):
        """paint(local_xyz[N,3], base[3]) → colors[N,3]. Gradient darkens toward the bottom of the part."""
        if mesh is None:
            return
        base = f3(color)
        V = local if local is not None else mesh.vertices
        cols = np.tile(base, (len(mesh.vertices), 1))
        if gradient and len(V) > 1:
            y = V[:, 1]
            t = (y - y.min()) / max(1e-6, y.max() - y.min())
            cols = cols * (0.86 + 0.2 * t)[:, None]
        if paint is not None:
            cols = paint(V, cols)
        self.parts.append((name, mesh, color, np.clip(cols, 0, 1).astype(np.float32)))

    def bone(self, name, parent: np.ndarray | None, offset, length, rot=None):
        """Create a bone whose origin sits at `offset` in the parent frame, rotated by the pose. Stores its matrix."""
        rot = rot or self.pose.get(name, (0, 0, 0))
        m = (parent if parent is not None else np.eye(4)) @ M(*offset) @ M(0, 0, 0, *rot)
        self.bones[name] = m
        self.bone_len = getattr(self, "bone_len", {})
        self.bone_len[name] = length
        return m

    def end(self, name):
        return self.bones[name] @ translation_matrix([0, -self.bone_len[name], 0])

    # ── skeleton ──
    def build_skeleton(self):
        P = self.P
        root = self.bone("pelvis", None, (0, P.hip_y, 0), 0)
        chest = self.bone("chest", root, (0, P.shoulder_y - P.hip_y, 0), 0)
        for s, n in ((-1, "L"), (1, "R")):
            ua = self.bone(f"upper_arm_{n}", chest, (s * P.shoulder_w, -0.03, 0), P.upper_arm)
            fa = self.bone(f"forearm_{n}", self.end(f"upper_arm_{n}"), (0, 0, 0), P.forearm)
            self.bone(f"hand_{n}", self.end(f"forearm_{n}"), (0, 0, 0), P.hand_r * 1.6)
            th = self.bone(f"thigh_{n}", root, (s * P.leg_x, P.crotch_y - P.hip_y + 0.05, 0), P.thigh)
            self.bone(f"shin_{n}", self.end(f"thigh_{n}"), (0, 0, 0), P.shin)
            self.bone(f"foot_{n}", self.end(f"shin_{n}"), (0, 0, 0), 0)

    # ── body ──
    def build_body(self):
        P, skin = self.P, self.skin
        hy, sy = P.hip_y, P.shoulder_y
        th = sy - hy
        cx, cz = P.chest
        wx, wz = P.waist
        hx, hz = P.hips
        torso = lathe([
            (P.crotch_y, hx * 0.9, hz * 0.9), (hy, hx, hz), (hy + th * 0.3, wx, wz), (hy + th * 0.55, cx, cz),
            (hy + th * 0.8, cx * 1.02, cz), (sy - 0.05, P.shoulder_w * 0.72, cz * 0.9), (sy + 0.02, P.shoulder_w * 0.6, cz * 0.7),
            (sy + 0.06, 0.12, 0.10),
        ])
        self.add("torso", torso, skin)
        neck = lathe([(sy + 0.02, P.head_r * 0.34, P.head_r * 0.32), (P.head_y - P.head_r * 0.85, P.head_r * 0.3, P.head_r * 0.3)], 16)
        self.add("neck", neck, skin)
        for s, n in ((-1, "L"), (1, "R")):
            self.add(f"shoulder_{n}", xf(icosphere(3, P.arm_r * 1.45), self.bones[f"upper_arm_{n}"]), skin)

    def build_limbs(self):
        P, s_ = self.P, self.spec
        o = s_.get("outfit", {})
        skin = self.skin
        c1 = rgba(o.get("primary"), "#141418")
        c2 = rgba(o.get("secondary"), None) if o.get("secondary") else shade(c1, 1.4)
        sleeves = o.get("sleeves", "none")
        if sleeves is True:
            sleeves = "long"
        kind = o.get("type", "tunic")
        legs_col = c2 if o.get("legwear", kind.endswith("pants") or kind in ("suit", "armor", "tunic")) else None
        pattern = o.get("pattern")
        pat_col = f3(rgba(o.get("pattern_color"), "#2a2a2e")) if pattern else None

        def stripes(V, cols):
            if pattern != "stripes":
                return cols
            th = np.arctan2(V[:, 2], V[:, 0])
            band = (np.floor((th + math.pi) / (2 * math.pi) * 8) % 2) == 0
            cols = cols.copy()
            cols[band] = cols[band] * 0.35 + pat_col * 0.65
            return cols

        if legs_col is not None:
            # hips/seat of the trousers, so no skin shows between top and thighs
            hp = lathe([(P.crotch_y - 0.08, P.hips[0] * 0.95, P.hips[1] * 0.95), (P.hip_y + 0.06, P.hips[0] + 0.035, P.hips[1] + 0.035)], 28)
            self.add("pants_hips", hp, legs_col, paint=stripes, local=hp.vertices)
        for s, n in ((-1, "L"), (1, "R")):
            ua, fa, hd = self.bones[f"upper_arm_{n}"], self.bones[f"forearm_{n}"], self.bones[f"hand_{n}"]
            self.add(f"upper_arm_{n}", xf(segment(P.upper_arm, P.arm_r * 1.05, P.arm_r * 0.85, 0.012), ua), skin)
            self.add(f"elbow_{n}", xf(icosphere(2, P.arm_r * 0.9), fa), skin)
            self.add(f"forearm_{n}", xf(segment(P.forearm, P.arm_r * 0.9, P.arm_r * 0.62, 0.015), fa), skin)
            self.add(f"hand_{n}", xf(icosphere(3, P.hand_r), hd @ translation_matrix([0, -P.hand_r * 0.7, 0]), sx=0.85, sy=1.15, sz=0.6), skin)
            if sleeves in ("short", "long"):
                L = P.upper_arm * (0.55 if sleeves == "short" else 1.02)
                self.add(f"sleeve_{n}", xf(segment(L, P.arm_r * 1.4, P.arm_r * 1.25, 0.0, flat=1.0), ua), c1, local=None)
                if sleeves == "long":
                    self.add(f"cuff_{n}", xf(segment(P.forearm * 0.98, P.arm_r * 1.25, P.arm_r * 0.95), fa), c1)
            th_, sh_, ft_ = self.bones[f"thigh_{n}"], self.bones[f"shin_{n}"], self.bones[f"foot_{n}"]
            self.add(f"thigh_{n}", xf(segment(P.thigh, P.thigh_r, P.thigh_r * 0.72, 0.01), th_), skin)
            self.add(f"knee_{n}", xf(icosphere(2, P.shin_r * 1.05), sh_), skin)
            self.add(f"shin_{n}", xf(segment(P.shin, P.shin_r, P.shin_r * 0.7, 0.02), sh_), skin)
            if legs_col is not None:
                lt = segment(P.thigh * 1.0, P.thigh_r * 1.12, P.thigh_r * 0.82, 0.0)
                self.add(f"pants_thigh_{n}", xf(lt, th_), legs_col, paint=stripes, local=lt.vertices)
                ls = segment(P.shin * 0.92, P.shin_r * 1.15, P.shin_r * 0.85, 0.0)
                self.add(f"pants_shin_{n}", xf(ls, sh_), legs_col, paint=stripes, local=ls.vertices)
            self.build_foot(n, ft_, sh_)

    def build_foot(self, n, ft, sh):
        P = self.P
        bt = self.spec.get("boots", {})
        col = rgba(bt.get("color"), "#141418")
        height = bt.get("height", "ankle")
        if height == "knee":
            self.add(f"boot_{n}", xf(segment(P.shin * 0.95, P.shin_r * 1.25, P.shin_r * 1.05), sh), col)
        elif height == "ankle":
            self.add(f"boot_{n}", xf(segment(P.shin * 0.3, P.shin_r * 1.2, P.shin_r * 1.08), sh @ translation_matrix([0, -P.shin * 0.7, 0])), col)
        if height == "heel":
            self.add(f"sole_{n}", xf(box([P.shin_r * 2.2, 0.09, P.foot_len]), ft @ translation_matrix([0, 0.04, P.foot_len * 0.15])), col)
            self.add(f"strap_{n}", xf(torus(P.shin_r * 1.0, 0.018), ft @ M(0, 0.13, 0, rx=90)), col)
            self.add(f"foot_{n}", xf(icosphere(3, P.shin_r), ft @ translation_matrix([0, 0.12, P.foot_len * 0.12]), sy=0.55, sz=1.9), self.skin)
            return
        # shoe: rounded wedge, toe forward
        self.add(f"shoe_{n}", xf(icosphere(3, P.shin_r * 1.15), ft @ translation_matrix([0, P.shin_r * 0.7, P.foot_len * 0.18]), sy=0.62, sz=1.9), col)
        self.add(f"sole_{n}", xf(box([P.shin_r * 2.2, 0.06, P.foot_len * 1.05]), ft @ translation_matrix([0, 0.03, P.foot_len * 0.15])), shade(col, 0.6))

    # ── cloth ──
    def build_cloth(self):
        P, s_ = self.P, self.spec
        o = s_.get("outfit", {})
        kind = o.get("type", "tunic")
        c1 = rgba(o.get("primary"), "#141418")
        c2 = rgba(o.get("secondary"), None) if o.get("secondary") else shade(c1, 1.4)
        acc = rgba(o.get("accent"), "#c9a86a")
        hy, sy = P.hip_y, P.shoulder_y
        th = sy - hy
        cx, cz = P.chest
        wx, wz = P.waist
        hx, hz = P.hips
        g = 0.035  # cloth gap over skin

        def top(y0, y1, extra=0.0):
            """Fitted upper garment between y0 and y1 following the torso."""
            def r(y):
                t = (y - hy) / th
                if t < 0.3:
                    u = max(0, t / 0.3)
                    return (hx + (wx - hx) * u, hz + (wz - hz) * u)
                if t < 0.55:
                    u = (t - 0.3) / 0.25
                    return (wx + (cx - wx) * u, wz + (cz - wz) * u)
                u = min(1, (t - 0.55) / 0.45)
                return (cx * (1 + 0.02 * u), cz)
            ys = np.linspace(y0, y1, 7)
            return lathe([(y, r(y)[0] + g + extra, r(y)[1] + g + extra) for y in ys], 28, caps=(True, True))

        print_col = f3(rgba(o["print"])) if o.get("print") else None

        def chest_print(V, cols):
            if print_col is None:
                return cols
            cy = hy + th * 0.66
            d = ((V[:, 0] / (cx * 0.55)) ** 2 + ((V[:, 1] - cy) / (th * 0.16)) ** 2)
            m = (d < 1) & (V[:, 2] > 0)
            cols = cols.copy()
            cols[m] = print_col
            return cols

        belt = lambda y, rx, rz, col, h=0.06: self.add(f"belt_{y:.2f}", lathe([(y - h / 2, rx + g + 0.01, rz + g + 0.01), (y + h / 2, rx + g + 0.01, rz + g + 0.01)], 28), col, gradient=False)
        skirt = lambda y_top, y_hem, flare, col, pleats=0: self.add(
            "skirt",
            lathe([(y_hem, hx * flare, hz * flare), (y_hem + (y_top - y_hem) * 0.5, hx * (1 + (flare - 1) * 0.45) + g, hz * (1 + (flare - 1) * 0.45) + g), (y_top, hx + g, hz + g)], 36,
                  wave=(lambda i, t: 1 + (0.04 * math.sin(t * pleats) if pleats and i == 0 else 0.0))),
            col)

        if kind in ("tee_skirt", "tee_pants", "polo_skirt", "polo_pants", "crop_top"):
            top_y0 = hy + th * (0.5 if kind == "crop_top" else 0.38)
            tm = top(top_y0, sy + 0.03)
            self.add("tee", tm, c1, paint=chest_print, local=tm.vertices)
            if kind.startswith("polo"):
                for s in (-1, 1):
                    self.add(f"collar_{s}", xf(box([P.head_r * 0.55, 0.14, 0.03]), M(s * P.head_r * 0.3, sy + 0.05, cz + g + 0.02, rz=s * 38, rx=-20)), shade(c1, 0.95), gradient=False)
                self.add("placket", xf(box([0.03, th * 0.2, 0.02]), M(0, sy - th * 0.12, cz + g + 0.02)), shade(c1, 0.9), gradient=False)
            if kind.endswith("skirt"):
                belt(hy + 0.02, hx, hz, acc, 0.07)
                if o.get("buckle"):
                    self.add("buckle", xf(box([0.15, 0.09, 0.03]), M(0, hy + 0.02, hz + g + 0.03)), rgba(o["buckle"]), gradient=False)
                skirt(hy + 0.02, hy - th * 0.32, 1.35, c2, pleats=o.get("pleats", 0))
            else:
                belt(hy + 0.02, hx, hz, acc, 0.06)
        elif kind == "dress":
            tm = top(hy + th * 0.3, sy + 0.03)
            self.add("bodice", tm, c1, paint=chest_print, local=tm.vertices)
            belt(hy + th * 0.32, wx, wz, c2, 0.06)
            skirt(hy + th * 0.32, max(0.06, hy - P.thigh * (0.8 if o.get("length", "knee") == "knee" else 1.5)), 1.6, c1, pleats=o.get("pleats", 0))
        elif kind == "tunic":
            tm = top(hy - th * 0.15, sy + 0.03, 0.01)
            self.add("tunic", tm, c1, paint=chest_print, local=tm.vertices)
            belt(hy + th * 0.28, wx, wz, acc, 0.07)
        elif kind == "armor":
            tm = top(hy + th * 0.05, sy + 0.03, 0.02)
            self.add("gambeson", tm, c1)
            self.add("chest_plate", xf(icosphere(3, cx * 1.15), M(0, hy + th * 0.66, cz * 0.35), sy=0.62, sz=0.55), c2)
            for s in (-1, 1):
                self.add(f"pauldron_{s}", xf(icosphere(3, P.arm_r * 2.3), self.bones[f"upper_arm_{'L' if s < 0 else 'R'}"] @ M(0, 0.02, 0), sy=0.75), c2)
            belt(hy + th * 0.1, hx, hz, acc, 0.08)
            self.add("tassets", lathe([(hy - th * 0.28, hx * 1.35, hz * 1.35), (hy + th * 0.08, hx + g, hz + g)], 12), c1)
        elif kind == "robe":
            self.add("robe", lathe([(0.06, hx * 2.0, hz * 2.0), (hy, hx + g, hz + g), (hy + th * 0.5, cx + g, cz + g), (sy + 0.03, P.shoulder_w * 0.7, cz * 0.9)], 32), c1)
            self.add("robe_trim", lathe([(0.05, hx * 2.02, hz * 2.02), (0.11, hx * 2.0, hz * 2.0)], 32), acc, gradient=False)
            belt(hy + th * 0.3, wx, wz, c2, 0.06)
            if o.get("hood"):
                self.add("hood", xf(icosphere(3, P.head_r + 0.1), M(0, P.head_y + 0.06, -0.12), sz=0.95), c1)
        elif kind in ("jacket_skirt", "jacket_pants", "vest", "suit"):
            tm = top(hy + th * 0.25, sy + 0.03, 0.02)
            self.add("jacket", tm, c1, paint=chest_print, local=tm.vertices)
            if kind == "vest":
                # open front: shirt strip + lapels
                self.add("shirt", xf(box([cx * 0.5, th * 0.7, 0.02]), M(0, hy + th * 0.62, cz + g + 0.03)), rgba(o.get("shirt"), "#f2f2f2"), gradient=False)
                for s in (-1, 1):
                    self.add(f"lapel_{s}", xf(box([cx * 0.28, th * 0.42, 0.025]), M(s * cx * 0.32, hy + th * 0.72, cz + g + 0.04, rz=s * -14)), acc, gradient=False)
            elif kind == "suit":
                self.add("shirt", xf(box([cx * 0.45, th * 0.55, 0.02]), M(0, hy + th * 0.66, cz + g + 0.03)), [245, 245, 245, 255], gradient=False)
                self.add("tie", xf(box([cx * 0.16, th * 0.45, 0.02]), M(0, hy + th * 0.62, cz + g + 0.05)), acc, gradient=False)
            if kind == "jacket_skirt":
                skirt(hy + 0.02, hy - th * 0.32, 1.3, c2, pleats=o.get("pleats", 0))
            belt(hy + th * 0.26, wx, wz, acc, 0.05)
        else:
            raise ValueError(f"unknown outfit type {kind!r}")

    # ── head ──
    def build_head(self):
        P, s_ = self.P, self.spec
        skin = self.skin
        face = s_.get("face", {})
        eye = rgba(face.get("eyes"), "#3a3a54")
        mouth = rgba(face.get("mouth"), "#b5776e")
        R, Y = P.head_r, P.head_y
        shape = face.get("shape", "square" if face.get("jaw") == "square" else "oval")
        head, unit = head_mesh(R, shape, float(face.get("chin", 1.0)), float(face.get("cheekbones", 1.0)))
        head.apply_translation([0, Y, 0])
        self.head_unit = unit
        self.add("head", head, skin)
        # eye line sits at the vertical centre of the skull; the face surface there is ~0.86 R forward
        ex, ey = R * 0.36, Y + R * 0.06
        ez = R * 0.80
        hidden = "sunglasses" in s_.get("accessories", [])
        hair_col = rgba(s_.get("hair", {}).get("color"), "#444")
        for s in (-1, 1):
            self.add(f"ear_{s}", xf(icosphere(2, R * 0.17), M(s * R * 0.9, Y - R * 0.02, -R * 0.08), sx=0.45, sy=1.15, sz=0.8), skin, gradient=False)
            if not hidden:
                w, h = R * 0.2, R * 0.11
                self.add(f"eye_white_{s}", xf(icosphere(2, 1.0), M(s * ex, ey, ez), sx=w, sy=h, sz=R * 0.06), [250, 250, 250, 255], gradient=False)
                self.add(f"iris_{s}", xf(icosphere(2, 1.0), M(s * (ex + R * 0.01), ey - h * 0.1, ez + R * 0.045), sx=R * 0.085, sy=R * 0.085, sz=R * 0.025), eye, gradient=False)
                self.add(f"pupil_{s}", xf(icosphere(2, 1.0), M(s * (ex + R * 0.012), ey - h * 0.12, ez + R * 0.065), sx=R * 0.04, sy=R * 0.04, sz=R * 0.02), [18, 16, 22, 255], gradient=False)
                self.add(f"eye_light_{s}", xf(icosphere(1, 1.0), M(s * (ex - R * 0.02), ey + h * 0.35, ez + R * 0.09), sx=R * 0.02, sy=R * 0.02, sz=R * 0.01), [255, 255, 255, 255], gradient=False)
                # upper lid + lashes as a thin dark arc
                self.add(f"lid_{s}", xf(icosphere(2, 1.0), M(s * ex, ey + h * 0.85, ez + R * 0.02, rz=s * 8), sx=w * 1.05, sy=h * 0.3, sz=R * 0.05), shade(hair_col, 0.45), gradient=False)
                brow = shade(hair_col, 0.7)
                bx0, bx1 = s * (ex - R * 0.2), s * (ex + R * 0.22)
                stern = face.get("expression") == "stern"
                self.add(f"brow_{s}", clump((bx0, ey + R * (0.24 if stern else 0.27), R * 0.86), (bx1, ey + R * (0.32 if stern else 0.3), R * 0.8), R * 0.035, 0.8, 8), brow, gradient=False)
        # nose: bridge to tip, plus the tip
        self.add("nose", clump((0, Y + R * 0.1, R * 0.9), (0, Y - R * 0.3, R * 1.05), R * 0.075, 0.55, 10), shade(skin, 0.96), gradient=False)
        self.add("nose_tip", xf(icosphere(2, 1.0), M(0, Y - R * 0.3, R * 1.02), sx=R * 0.085, sy=R * 0.06, sz=R * 0.06), shade(skin, 0.97), gradient=False)
        # lips: two stacked flattened ellipsoids
        my = Y - R * 0.56
        mz = R * 0.93
        self.add("lip_upper", xf(icosphere(2, 1.0), M(0, my + R * 0.025, mz), sx=R * 0.17, sy=R * 0.03, sz=R * 0.05), shade(mouth, 0.85), gradient=False)
        self.add("lip_lower", xf(icosphere(2, 1.0), M(0, my - R * 0.03, mz + R * 0.01), sx=R * 0.15, sy=R * 0.045, sz=R * 0.06), mouth, gradient=False)
        if face.get("blush"):
            for s in (-1, 1):
                self.add(f"blush_{s}", xf(icosphere(2, 1.0), M(s * R * 0.5, Y - R * 0.25, R * 0.72), sx=R * 0.15, sy=R * 0.1, sz=R * 0.04), rgba(face["blush"]), gradient=False)

    # ── hair ──
    def build_hair(self):
        P, h = self.P, self.spec.get("hair", {})
        style = h.get("style", "long")
        if style == "bald":
            return
        col = rgba(h.get("color"), "#f4f6fa")
        col2 = rgba(h.get("shade"), None) if h.get("shade") else shade(col, 0.88)
        R, Y = P.head_r, P.head_y
        rng = np.random.default_rng(7)
        # scalp: the skull itself, inflated a little, with the face region pushed inside the head
        face_shape = self.spec.get("face", {}).get("shape", "square" if self.spec.get("face", {}).get("jaw") == "square" else "oval")
        cap, unit = head_mesh(R, face_shape)
        u = unit
        hairline = 1 / (1 + np.exp(-((u[:, 2] - 0.25) * 9))) * (1 / (1 + np.exp(((u[:, 1] - 0.62) * 9))))  # front & below the hairline
        below = 1 / (1 + np.exp(((u[:, 1] + 0.55) * 9)))  # under the ears
        inside = np.clip(hairline + below, 0, 1)
        scale = (1.10 - 0.22 * inside)[:, None]
        cap.vertices = cap.vertices * scale
        cap.apply_translation([0, Y + R * 0.03, -R * 0.03])
        if style != "mohawk":
            self.add("scalp", cap, col)
        bangs = h.get("bangs", True)
        if bangs in (True, "full") and style not in ("mohawk", "slick"):
            for i, x in enumerate(np.linspace(-0.62, 0.62, 6)):
                a = (x * R, Y + R * 0.85, R * 0.45)
                b = (x * R * 1.1, Y + R * 0.28 - abs(x) * R * 0.15, R * 0.98)
                self.add(f"bang_{i}", clump(a, b, R * 0.22, 0.5), col)
        elif bangs == "parted" and style not in ("mohawk", "slick"):
            for s in (-1, 1):
                for i, t in enumerate(np.linspace(0.05, 0.6, 3)):
                    a = (s * R * 0.08, Y + R * 0.95, R * 0.5)
                    b = (s * R * (0.55 + t), Y + R * (0.45 - t * 0.9), R * (0.85 - t * 0.4))
                    self.add(f"part_{s}_{i}", clump(a, b, R * 0.24, 0.45), col)
        if style == "long":
            end = {"shoulder": P.shoulder_y - 0.05, "chest": P.hip_y + (P.shoulder_y - P.hip_y) * 0.7, "waist": P.hip_y + 0.15, "hips": P.hip_y - 0.1}[h.get("length", "waist")]
            for i in range(11):
                a_ang = -1.0 + i * 0.2  # around the back of the skull, radians from -z
                ang = math.pi + a_ang * 1.25
                ax, az = math.sin(ang) * R * 1.02, math.cos(ang) * R * 1.02
                a = (ax, Y + R * 0.35, az - R * 0.1)
                b = (ax * 1.25 + rng.normal(0, 0.02), end + rng.normal(0, 0.05) + abs(a_ang) * 0.12, az * 1.15 - R * 0.15)
                self.add(f"strand_{i}", clump(a, b, R * 0.24, 0.55), col if i % 3 else col2)
            if h.get("locks", True):
                for s in (-1, 1):
                    self.add(f"lock_{s}", clump((s * R * 0.95, Y + R * 0.2, R * 0.45), (s * R * 1.05, Y - R * 2.2, R * 0.6), R * 0.2, 0.5), col)
        elif style == "bob":
            for i in range(14):
                ang = math.pi * 0.25 + i * (math.pi * 1.5 / 13)
                ax, az = math.sin(ang) * R * 1.02, math.cos(ang) * R * 1.02
                self.add(f"strand_{i}", clump((ax, Y + R * 0.4, az - R * 0.1), (ax * 1.15, Y - R * 1.25, az * 1.05 - R * 0.1), R * 0.24, 0.5), col if i % 2 else col2)
        elif style == "pixie":
            for i in range(10):
                ang = rng.uniform(0, 2 * math.pi)
                a = (math.sin(ang) * R * 0.5, Y + R * 0.9, math.cos(ang) * R * 0.5 - R * 0.1)
                b = (math.sin(ang) * R * 1.05, Y + R * 0.35, math.cos(ang) * R * 1.0 - R * 0.15)
                self.add(f"tuft_{i}", clump(a, b, R * 0.2, 0.5), col if i % 2 else col2)
        elif style == "spiky":
            # swept-back spikes like Vi: root at the crown, tips flaring up and back
            for i in range(9):
                t = i / 8
                ang = -0.9 + t * 1.8
                a = (math.sin(ang) * R * 0.45, Y + R * 0.75, -R * 0.1 + math.cos(ang) * R * 0.3)
                b = (math.sin(ang) * R * 1.1 + rng.normal(0, 0.03), Y + R * (1.35 + 0.35 * math.cos(ang * 1.5)), -R * (0.9 + 0.5 * math.cos(ang)))
                self.add(f"spike_{i}", clump(a, b, R * 0.22, 0.4), col if i % 2 else col2)
            for i in range(4):
                s = -1 if i < 2 else 1
                self.add(f"side_{i}", clump((s * R * 0.7, Y + R * 0.6, R * 0.35 - i % 2 * R * 0.5), (s * R * 1.15, Y + R * 0.1, R * 0.55 - i % 2 * R * 0.7), R * 0.18, 0.45), col)
        elif style == "ponytail":
            self.add("tail", clump((0, Y + R * 0.4, -R * 0.95), (0, Y - R * 2.4, -R * 1.2), R * 0.3, 0.45), col2)
            self.add("tie", xf(torus(R * 0.3, R * 0.07), M(0, Y + R * 0.2, -R * 0.98, rx=75)), rgba(h.get("tie"), "#c9a86a"), gradient=False)
        elif style == "twintails":
            for s in (-1, 1):
                self.add(f"tail_{s}", clump((s * R * 0.95, Y + R * 0.1, -R * 0.2), (s * R * 1.3, Y - R * 2.6, -R * 0.1), R * 0.28, 0.45), col2)
                self.add(f"tie_{s}", xf(torus(R * 0.28, R * 0.07), M(s * R * 0.98, Y + R * 0.05, -R * 0.2, rz=s * 90)), rgba(h.get("tie"), "#c9a86a"), gradient=False)
        elif style == "bun":
            self.add("bun", xf(icosphere(3, R * 0.48), M(0, Y + R * 0.95, -R * 0.55)), col2)
        elif style == "curly":
            for i in range(26):
                ang = rng.uniform(0, 2 * math.pi)
                r = R * rng.uniform(0.9, 1.25)
                yy = Y + rng.uniform(-1.0, 0.7) * R
                self.add(f"curl_{i}", xf(icosphere(2, R * 0.3), M(math.sin(ang) * r, yy, math.cos(ang) * r - R * 0.25)), col if i % 2 else col2)
        elif style == "mohawk":
            for i in range(7):
                z = R * (0.55 - i * 0.22)
                self.add(f"hawk_{i}", clump((0, Y + R * 0.9, z), (0, Y + R * 1.9, z - R * 0.2), R * 0.2, 0.3), col)
        elif style == "slick":
            pass  # scalp only

    # ── accessories ──
    def build_accessories(self):
        P, s_ = self.P, self.spec
        colors = s_.get("accessory_colors", {})
        skin, gold = self.skin, [222, 178, 90, 255]
        R, Y = P.head_r, P.head_y
        c = lambda k, d: rgba(colors.get(k)) if colors.get(k) else d
        for a in s_.get("accessories", []):
            if a == "cape":
                self.add("cape", lathe([(0.15, P.hips[0] * 1.7, P.hips[1] * 1.3), (P.shoulder_y - 0.05, P.shoulder_w * 0.9, P.chest[1] * 0.9)], 24), c(a, [120, 30, 40, 255]))
            elif a == "hood_down":
                self.add("hood", xf(icosphere(3, R * 0.9), M(0, P.shoulder_y - 0.05, -P.chest[1] * 0.8), sy=0.5, sz=0.8), c(a, [40, 36, 50, 255]))
            elif a == "crown":
                self.add("crown_ring", xf(torus(R * 0.95, 0.035), M(0, Y + R * 0.85, 0, rx=90)), c(a, gold), gradient=False)
                for i in range(5):
                    ang = math.radians(-60 + i * 30)
                    self.add(f"crown_spike_{i}", xf(icosphere(1, 0.05), M(math.sin(ang) * R * 0.95, Y + R * 0.98, math.cos(ang) * R * 0.95), sy=2.5), c(a, gold), gradient=False)
            elif a == "horns":
                for s in (-1, 1):
                    self.add(f"horn_{s}", clump((s * R * 0.6, Y + R * 0.7, -R * 0.1), (s * R * 1.1, Y + R * 1.7, -R * 0.4), R * 0.2, 0.9), c(a, [60, 45, 40, 255]))
            elif a == "cat_ears":
                for s in (-1, 1):
                    self.add(f"ear_{s}", clump((s * R * 0.6, Y + R * 0.75, -R * 0.1), (s * R * 0.85, Y + R * 1.5, -R * 0.2), R * 0.26, 0.95), c(a, rgba(s_.get("hair", {}).get("color"), "#444")))
            elif a == "elf_ears":
                for s in (-1, 1):
                    self.add(f"elf_ear_{s}", xf(icosphere(2, R * 0.28), M(s * (R + 0.08), Y + 0.02, -0.02, rz=s * 20), sx=1.6, sy=0.5, sz=0.4), skin)
            elif a == "glasses":
                for s in (-1, 1):
                    self.add(f"glasses_{s}", xf(torus(R * 0.2, 0.012), M(s * P.eye_dx * R, Y + 0.01, R * 0.95)), c(a, [30, 30, 34, 255]), gradient=False)
                self.add("glasses_bridge", xf(box([R * 0.28, 0.015, 0.015]), M(0, Y + 0.02, R * 0.95)), c(a, [30, 30, 34, 255]), gradient=False)
            elif a == "sunglasses":
                lens = f3(c(a, [40, 30, 60, 255]))
                frame = c("sunglasses_frame", [240, 240, 240, 255])
                ex, ey, ez = R * 0.36, Y + R * 0.06, R * 0.86
                def lens_paint(V, cols):
                    t = (V[:, 1] - V[:, 1].min()) / max(1e-6, np.ptp(V[:, 1]))  # 0 bottom → 1 top
                    dark, light = lens * 0.45, np.clip(lens * 0.8 + 0.3, 0, 1)
                    return dark[None] * t[:, None] + light[None] * (1 - t[:, None])
                for s in (-1, 1):
                    lb = box([R * 0.64, R * 0.42, R * 0.04])
                    self.add(f"lens_{s}", xf(lb, M(s * (ex + R * 0.03), ey - R * 0.04, ez, ry=s * -14, rx=-6)), c(a, [40, 30, 60, 255]), paint=lens_paint, gradient=False, local=lb.vertices)
                    self.add(f"lens_rim_{s}", xf(box([R * 0.68, R * 0.07, R * 0.05]), M(s * (ex + R * 0.03), ey + R * 0.19, ez + R * 0.01, ry=s * -14)), frame, gradient=False)
                self.add("shades_bridge", xf(box([R * 0.16, R * 0.06, R * 0.05]), M(0, ey + R * 0.16, ez + R * 0.05)), frame, gradient=False)
                for s in (-1, 1):
                    self.add(f"shades_arm_{s}", xf(box([R * 0.035, R * 0.05, R * 1.0]), M(s * R * 0.95, ey + R * 0.16, R * 0.38)), frame, gradient=False)
            elif a == "goggles":
                for s in (-1, 1):
                    self.add(f"goggle_{s}", xf(torus(R * 0.2, 0.04), M(s * R * 0.32, Y + R * 0.78, R * 0.55, rx=-40)), c(a, [80, 70, 60, 255]), gradient=False)
                self.add("goggle_strap", xf(torus(R * 1.02, 0.03), M(0, Y + R * 0.72, 0, rx=70)), c(a, [80, 70, 60, 255]), gradient=False)
            elif a == "scarf":
                self.add("scarf", xf(torus(P.chest[0] * 0.75, R * 0.2), M(0, P.shoulder_y - 0.02, 0, rx=90)), c(a, [180, 50, 60, 255]))
            elif a == "wings":
                for s in (-1, 1):
                    self.add(f"wing_{s}", xf(icosphere(3, 0.35), M(s * 0.5, P.shoulder_y - 0.1, -P.chest[1] * 1.3, rz=s * 30), sx=1.4, sy=0.9, sz=0.12), c(a, [240, 240, 250, 255]))
            elif a == "halo":
                self.add("halo", xf(torus(R * 0.57, 0.025), M(0, Y + R * 1.35, 0, rx=90)), c(a, [255, 220, 120, 255]), gradient=False)
            elif a == "headband":
                self.add("headband", xf(torus(R * 1.03, 0.035), M(0, Y + R * 0.5, 0, rx=75)), c(a, [200, 60, 80, 255]), gradient=False)
            elif a == "earrings":
                for s in (-1, 1):
                    self.add(f"earring_{s}", xf(icosphere(2, 0.035), M(s * (R + 0.02), Y - R * 0.3, 0)), c(a, gold), gradient=False)
            elif a == "shoulder_bag":
                col = c(a, [90, 60, 40, 255])
                self.add("bag_strap", xf(box([0.035, P.shoulder_y - P.hip_y + 0.1, 0.02]), M(-P.shoulder_w * 0.5, (P.shoulder_y + P.hip_y) / 2 + 0.05, P.chest[1] + 0.05, rz=-16)), col, gradient=False)
                self.add("bag", xf(box([0.26, 0.22, 0.14]), M(-(P.shoulder_w + P.arm_r * 2.6), P.hip_y + 0.08, 0.05)), col)
            elif a == "collar":
                self.add("collar", xf(torus(R * 0.4, 0.035), M(0, P.shoulder_y + P.neck_len * 0.4, 0, rx=90)), c(a, [30, 30, 34, 255]), gradient=False)
            elif a == "bracelets":
                col = c(a, [230, 80, 120, 255])
                for n in ("L", "R"):
                    hd = self.bones[f"hand_{n}"]
                    for j, dy in enumerate((0.03, 0.08)):
                        self.add(f"bracelet_{n}_{j}", xf(torus(P.arm_r * 0.72, 0.012), hd @ M(0, dy, 0, rx=90)), col if j == 0 else shade(col, 1.3), gradient=False)
            elif a == "necklace":
                self.add("necklace", xf(torus(R * 0.55, 0.014), M(0, P.shoulder_y + 0.02, 0, rx=80)), c(a, gold), gradient=False)
                self.add("pendant", xf(icosphere(2, 0.035), M(0, P.shoulder_y - R * 0.5, P.chest[1] + 0.03)), c(a, gold), gradient=False)
            elif a == "gauntlets":
                col, trim = c(a, [40, 50, 90, 255]), c("gauntlets_trim", gold)
                for n in ("L", "R"):
                    hd = self.bones[f"hand_{n}"]
                    self.add(f"gauntlet_{n}", xf(box([P.arm_r * 5.2, P.arm_r * 4.6, P.arm_r * 5.6]), hd @ M(0, -P.arm_r * 1.4, P.arm_r * 0.4)), col)
                    self.add(f"gauntlet_cuff_{n}", xf(segment(P.forearm * 0.6, P.arm_r * 2.4, P.arm_r * 2.0), self.bones[f"forearm_{n}"] @ M(0, -P.forearm * 0.35, 0)), col)
                    for k in range(4):
                        self.add(f"knuckle_{n}_{k}", xf(box([P.arm_r * 1.0, P.arm_r * 1.0, P.arm_r * 1.2]), hd @ M((k - 1.5) * P.arm_r * 1.25, -P.arm_r * 3.4, P.arm_r * 2.6)), trim, gradient=False)
            elif a == "knee_pads":
                for n in ("L", "R"):
                    self.add(f"kneepad_{n}", xf(icosphere(2, P.shin_r * 1.3), self.bones[f"shin_{n}"] @ M(0, 0, P.shin_r * 0.4), sz=0.6), c(a, [60, 60, 70, 255]))
            elif a == "belt_pouch":
                self.add("pouch", xf(box([0.14, 0.16, 0.1]), M(P.hips[0] * 1.05, P.hip_y - 0.12, 0.05)), c(a, [70, 45, 35, 255]))
            else:
                raise ValueError(f"unknown accessory {a!r}")

    # ── props ──
    def build_prop(self):
        p, P = self.spec.get("prop", {}), self.P
        kind = p.get("type", "none")
        if kind == "none":
            return
        col = rgba(p.get("color"), "#c0c4cc")
        acc = rgba(p.get("accent"), "#c9a86a")
        hd = self.bones["hand_R"] @ M(0, -P.hand_r * 0.6, 0)
        L = P.forearm  # weapon scale follows the figure
        # In hand space, -Y continues the forearm; +Z is the palm-forward direction.
        if kind == "sword":
            self.add("blade", xf(box([0.06, L * 2.6, 0.02]), hd @ M(0, L * 1.35, 0.04)), col, gradient=False)
            self.add("guard", xf(box([0.24, 0.05, 0.06]), hd @ M(0, 0.06, 0.04)), acc, gradient=False)
            self.add("grip", xf(box([0.04, 0.22, 0.05]), hd @ M(0, -0.08, 0.04)), shade(acc, 0.5), gradient=False)
        elif kind == "dagger":
            self.add("blade", xf(box([0.05, L * 1.1, 0.02]), hd @ M(0, L * 0.6, 0.04)), col, gradient=False)
            self.add("guard", xf(box([0.14, 0.04, 0.05]), hd @ M(0, 0.04, 0.04)), acc, gradient=False)
        elif kind == "staff":
            self.add("staff", xf(box([0.05, L * 5.0, 0.05]), hd @ M(0, L * 1.2, 0.04)), shade(acc, 0.6))
            self.add("orb", xf(icosphere(3, 0.13), hd @ M(0, L * 3.75, 0.04)), col, gradient=False)
        elif kind == "wand":
            self.add("wand", xf(box([0.03, L * 1.4, 0.03]), hd @ M(0, L * 0.6, 0.04)), shade(acc, 0.6), gradient=False)
            self.add("star", xf(icosphere(2, 0.07), hd @ M(0, L * 1.35, 0.04)), col, gradient=False)
        elif kind == "bow":
            self.add("bow", xf(torus(L * 1.4, 0.025), hd @ M(0.05, 0.1, 0.04, ry=90), sx=0.55), shade(acc, 0.7), gradient=False)
            self.add("string", xf(box([0.01, L * 2.8, 0.01]), hd @ M(0.05, 0.1, 0.0)), [230, 230, 230, 255], gradient=False)
        elif kind == "shield":
            fl = self.bones["forearm_L"] @ M(0, -P.forearm * 0.5, 0)
            self.add("shield", xf(lathe([(-0.03, L * 0.9, L * 0.9), (0.03, L * 0.75, L * 0.75)], 24), fl @ M(-P.arm_r * 1.6, 0, 0, rz=90)), col)
            self.add("boss", xf(icosphere(2, 0.08), fl @ M(-P.arm_r * 2.0, 0, 0)), acc, gradient=False)
        elif kind == "guitar":
            self.add("guitar_body", xf(box([0.5, 0.42, 0.1]), M(0.05, P.hip_y + 0.2, P.chest[1] + 0.3, rz=-20)), col)
            self.add("guitar_neck", xf(box([0.06, L * 2.2, 0.05]), M(-0.4, P.hip_y + 0.55, P.chest[1] + 0.3, rz=-70)), shade(acc, 0.6))
        elif kind == "mic":
            self.add("mic_handle", xf(box([0.05, 0.3, 0.05]), hd @ M(0, 0.12, 0.04)), shade(col, 0.4), gradient=False)
            self.add("mic_head", xf(icosphere(2, 0.08), hd @ M(0, 0.32, 0.04)), col, gradient=False)
        elif kind == "book":
            self.add("book", xf(box([0.3, 0.36, 0.08]), hd @ M(0, 0.1, 0.12, rx=-25)), col)
            self.add("spine", xf(box([0.03, 0.36, 0.09]), hd @ M(-0.15, 0.1, 0.12, rx=-25)), acc, gradient=False)
        else:
            raise ValueError(f"unknown prop {kind!r}")

    def build(self):
        self.build_skeleton()
        self.build_body()
        self.build_limbs()
        self.build_cloth()
        self.build_head()
        self.build_hair()
        self.build_accessories()
        self.build_prop()
        lo = min(p[1].bounds[0][1] for p in self.parts)
        for p in self.parts:
            p[1].apply_translation([0, -lo, 0])
        return self.parts


def build_character(spec: dict):
    return Character(spec).build()
