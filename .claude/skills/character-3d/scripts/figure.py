"""
Dress and pose the MakeHuman base mesh from a character spec.

Pipeline: Base (rest pose, stylised head) → paint skin/lips/eyes → hair clumps grown from the
scalp helper → garments fitted by slicing the body → accessories/props on joints → pose via
linear blend skinning → parts for the renderer.
"""
from __future__ import annotations

import math

import numpy as np
import trimesh
from trimesh.creation import box, icosphere, torus
from trimesh.transformations import rotation_matrix, translation_matrix

from basemesh import Base, Rig, skin
from charlib import M, clump, f3, rgba, shade, xf
from mhclo import Proxy

# Poses are rotations about world axes at each bone's head, relative to the base's A-pose
# (arms hang ~45° out). L is +X. rz<0 lowers the left arm toward the body; rx<0 swings forward.
POSES = {
    # the base A-pose holds the arms ~22° forward; standing poses pull them back to the sides with rx≈+20
    "relaxed": {"upperarm01.L": (20, 0, -38), "upperarm01.R": (20, 0, 38), "lowerarm01.L": (-4, 0, -2), "lowerarm01.R": (-4, 0, 2),
                "upperleg01.L": (0, 0, -3), "upperleg01.R": (0, 0, 3)},
    "idle": {"upperarm01.L": (20, 0, -34), "upperarm01.R": (20, 0, 34), "lowerarm01.L": (-10, 0, -6), "lowerarm01.R": (-10, 0, 6)},
    "ready": {"upperarm01.L": (-20, 0, -25), "upperarm01.R": (-70, 0, 25), "lowerarm01.L": (-25, 0, 0), "lowerarm01.R": (-60, 0, 0),
              "upperleg01.L": (6, 0, -6), "upperleg01.R": (-6, 0, 6), "lowerleg01.L": (8, 0, 0)},
    "hand_on_hip": {"upperarm01.L": (18, 0, -12), "lowerarm01.L": (0, 0, -82), "upperarm01.R": (20, 0, 30), "lowerarm01.R": (-10, 0, 8),
                    "upperleg01.R": (0, 0, 4), "spine03": (0, 0, 3)},
    "cast": {"upperarm01.L": (-70, 0, -30), "upperarm01.R": (-70, 0, 30), "lowerarm01.L": (-20, 0, 0), "lowerarm01.R": (-20, 0, 0)},
    "brace": {"upperarm01.L": (-35, 0, -30), "upperarm01.R": (-35, 0, 30), "lowerarm01.L": (-100, 0, 20), "lowerarm01.R": (-100, 0, -20),
              "upperleg01.L": (6, 0, -10), "upperleg01.R": (-4, 0, 10), "lowerleg01.R": (8, 0, 0)},
}

ARM = {"L": ["upperarm01.L", "upperarm02.L"], "R": ["upperarm01.R", "upperarm02.R"]}
FOREARM = {"L": ["lowerarm01.L", "lowerarm02.L"], "R": ["lowerarm01.R", "lowerarm02.R"]}
THIGH = {"L": ["upperleg01.L", "upperleg02.L"], "R": ["upperleg01.R", "upperleg02.R"]}
SHIN = {"L": ["lowerleg01.L", "lowerleg02.L"], "R": ["lowerleg01.R", "lowerleg02.R"]}
TORSO = ["spine01", "spine02", "spine03", "spine04", "spine05", "root", "pelvis.L", "pelvis.R", "clavicle.L", "clavicle.R", "breast.L", "breast.R", "shoulder01.L", "shoulder01.R"]


def ring_lathe(rings, segments=28, wave=None):
    """Closed surface from rings (y, rx, rz, cx, cz)."""
    n = segments
    th = np.linspace(0, 2 * math.pi, n, endpoint=False)
    V = []
    for i, (y, rx, rz, cx, cz) in enumerate(rings):
        f = np.ones(n) if wave is None else np.array([wave(i, t) for t in th])
        V.append(np.stack([cx + rx * f * np.cos(th), np.full(n, y), cz + rz * f * np.sin(th)], 1))
    V = np.vstack(V)
    F = []
    for i in range(len(rings) - 1):
        for j in range(n):
            a, b = i * n + j, i * n + (j + 1) % n
            c, d = (i + 1) * n + (j + 1) % n, (i + 1) * n + j
            F += [[a, c, b], [a, d, c]]
    cb, ct = len(V), len(V) + 1
    V = np.vstack([V, [[rings[0][3], rings[0][0], rings[0][4]], [rings[-1][3], rings[-1][0], rings[-1][4]]]])
    F += [[cb, (j + 1) % n, j] for j in range(n)]
    base = (len(rings) - 1) * n
    F += [[ct, base + j, base + (j + 1) % n] for j in range(n)]
    m = trimesh.Trimesh(V, np.asarray(F), process=False)
    m.fix_normals()
    return m


def shell(rows, centers, thickness=0.03):
    """
    Closed thin shell from rows of points (each row: same count of 3D points along an open arc)
    e.g. a curtain of hair. The inner skin is each row pulled toward its centre by `thickness`;
    the open ends and the top/bottom rims are stitched, so the result is watertight.
    """
    rows = [np.asarray(r, float) for r in rows]
    n = len(rows[0])
    outer = np.vstack(rows)
    inner = np.vstack([c + (r - c) * np.clip(1 - thickness / (np.linalg.norm(r - c, axis=1, keepdims=True) + 1e-9), 0.2, 1) for r, c in zip(rows, centers)])
    V = np.vstack([outer, inner])
    m = len(rows)
    F = []
    off = len(outer)
    for i in range(m - 1):
        for j in range(n - 1):
            a, b, c, d = i * n + j, i * n + j + 1, (i + 1) * n + j + 1, (i + 1) * n + j
            F += [[a, b, c], [a, c, d], [off + a, off + c, off + b], [off + a, off + d, off + c]]
    for i in range(m - 1):  # side edges
        for j in (0, n - 1):
            a, d = i * n + j, (i + 1) * n + j
            F += [[a, d, off + d], [a, off + d, off + a]] if j == 0 else [[a, off + d, d], [a, off + a, off + d]]
    for i in (0, m - 1):  # rims
        for j in range(n - 1):
            a, b = i * n + j, i * n + j + 1
            F += [[a, off + b, b], [a, off + a, off + b]] if i == 0 else [[a, b, off + b], [a, off + b, off + a]]
    mesh = trimesh.Trimesh(V, np.asarray(F), process=False)
    mesh.fix_normals()
    return mesh


class Figure:
    def __init__(self, spec):
        self.spec = spec
        pr = spec.get("proportions", {})
        slim = {"slim": 0.86, "average": 1.0, "athletic": 1.04, "heavy": 1.18}[pr.get("build", "average")]
        # stylised defaults: slightly longer arms and legs than the realistic base, like the reference sheets
        self.base = Base(head_scale=float(pr.get("head", 1.25)), slim=slim, arms=float(pr.get("arms", 1.18)), legs=float(pr.get("legs", 1.1)))
        self.rig = Rig(self.base)
        self.skin_col = rgba(spec.get("skin"), "#f5dccb")
        self.parts = []  # (name, rest_vertices, faces, rgba, vcols, idx, wt)
        B = self.base
        self.nverts_body = len(B.V0)
        self.body_idx, self.body_wt = B.weights_matrix(self.nverts_body)
        self.J = lambda n: B.bones[n].head
        pose = spec.get("pose", "idle")
        self.pose = {**POSES["idle"], **POSES.get(pose, {})} if isinstance(pose, str) else {**POSES["idle"], **pose}
        # champions look slightly up toward the board camera
        self.pose.setdefault("head", (-10, 0, 0))
        # heels: toes down at the ankle, so the heel rises and the figure stands on the heel block
        if spec.get("boots", {}).get("height") == "heel":
            tilt = float(spec["boots"].get("heel_tilt", 38))
            for side in ("L", "R"):
                self.pose.setdefault(f"foot.{side}", (tilt, 0, 0))

    # ── part registration ──
    def add(self, name, mesh, color, idx=None, wt=None, paint=None, gradient=True, rigid=None, colors=None, flags=None):
        if mesh is None:
            return
        V = np.asarray(mesh.vertices, float)
        base = f3(color)
        cols = np.tile(base, (len(V), 1)) if colors is None else np.asarray(colors, np.float32)
        if gradient and len(V) > 1:
            y = V[:, 1]
            t = (y - y.min()) / max(1e-6, y.max() - y.min())
            cols = cols * (0.88 + 0.16 * t)[:, None]
        if paint is not None:
            cols = paint(V, cols)
        if rigid:
            idx, wt = self.base.bone_weights(len(V), rigid)
        elif idx is None:
            idx, wt = self.base.nearest_weights(V)
        self.parts.append((name, V, np.asarray(mesh.faces), color, np.clip(cols, 0, 1).astype(np.float32), idx, wt, flags or {}))

    # ── body & face ──
    def build_body(self):
        B, s = self.base, self.spec
        face = s.get("face", {})
        mouth = f3(rgba(face.get("mouth"), "#b5776e"))
        blush = f3(rgba(face["blush"])) if face.get("blush") else None
        lip_w = np.zeros(self.nverts_body)
        cheek_w = np.zeros(self.nverts_body)
        lip_bones = {B.bone_index[n] for n in B.order if n.startswith("oris")}
        cheek_bones = {B.bone_index[n] for n in B.order if n.startswith(("levator", "risorius"))}
        for vid, lst in B.W.items():
            lip_w[vid] = sum(w for bi, w in lst if bi in lip_bones)
            cheek_w[vid] = sum(w for bi, w in lst if bi in cheek_bones)
        lip_w = np.clip((lip_w - 0.6) / 0.3, 0, 1) * 0.75
        cheek_w = np.clip(cheek_w * 0.5, 0, 0.45)

        def paint(V, cols):
            cols = cols * (1 - lip_w[:, None]) + mouth * lip_w[:, None]
            if blush is not None:
                cols = cols * (1 - cheek_w[:, None]) + blush * cheek_w[:, None]
            return cols

        body = B.mesh("body")
        vid = body.metadata["vid"]
        lip_w, cheek_w = lip_w[vid], cheek_w[vid]
        self.add("body", body, self.skin_col, idx=self.body_idx[vid], wt=self.body_wt[vid], paint=paint, gradient=False)

        eye_col = f3(rgba(face.get("eyes"), "#3a3a54"))
        for side in ("L", "R"):
            em = B.mesh(f"helper-{side.lower()}-eye")
            c = self.J(f"eye.{side}")
            def eye_paint(V, cols, c=c):
                d = V - c
                d /= np.linalg.norm(d, axis=1, keepdims=True) + 1e-9
                ang = np.degrees(np.arccos(np.clip(d[:, 2], -1, 1)))
                out = np.full_like(cols, 0.97)
                out[ang < 34] = eye_col * 1.15
                out[ang < 26] = eye_col
                out[ang < 12] = 0.08
                return out
            self.add(f"eye_{side}", em, [250, 250, 250, 255], paint=eye_paint, gradient=False, rigid="head")
            lash = B.mesh(f"helper-{side.lower()}-eyelashes-1")
            self.add(f"lash_{side}", lash, shade(rgba(s.get("hair", {}).get("color"), "#444"), 0.4), gradient=False, rigid="head")
            # brow: a tapered clump above the eye, angled by expression
            if face.get("brows", "mh:eyebrow001") and str(face.get("brows", "mh:eyebrow001")).startswith("mh:"):
                if side == "L":  # the asset holds both brows
                    self.add_proxy("eyebrows", face.get("brows", "mh:eyebrow001")[3:], "brow_mh", tint=shade(rgba(s.get("hair", {}).get("color"), "#444"), 0.6), tint_mode="lum", alpha_cut=0.35)
                continue
            e = self.J(f"eye.{side}")
            sgn = 1 if side == "L" else -1
            stern = face.get("expression") == "stern"
            a = (e[0] - sgn * 0.03, e[1] + (0.045 if stern else 0.058), e[2] + 0.06)
            b = (e[0] + sgn * 0.11, e[1] + (0.068 if stern else 0.058), e[2] + 0.0)
            self.add(f"brow_{side}", clump(a, b, 0.014, 0.5, 8), shade(rgba(s.get("hair", {}).get("color"), "#444"), 0.7), gradient=False)

    # ── MakeHuman proxy assets ──
    def add_proxy(self, kind, asset, name, tint=None, tint_mode="lum", alpha_cut=0.5, two_sided=True, extra_flags=None, streak=None):
        """
        Attach a MakeHuman .mhclo asset fitted to the current base. tint: rgba; tint_mode "lum" recolours by
        the texture's luminance (hair), "mul" multiplies (clothes). Faces whose texture alpha is mostly
        transparent are dropped, so strand-cutout hair keeps its silhouette without alpha blending.
        """
        B = self.base
        px = Proxy(kind, asset)
        P = px.positions(B.V0, B.native_scale)
        rgba_v = px.sample(px.vertex_uv())
        if tint is not None:
            t = f3(tint)
            if tint_mode == "lum":
                lum = rgba_v[:, :3] @ np.array([0.3, 0.59, 0.11])
                lo, hi = np.percentile(lum, 8), np.percentile(lum, 92)
                lum = np.clip((lum - lo) / max(1e-6, hi - lo), 0, 1)
                # keep the texture's strand contrast: dark roots/underside, bright ridges
                cols = np.clip(t * (0.46 + 0.66 * lum[:, None]), 0, 1)
                if streak is not None:
                    # coloured under-layer: strand columns (texture u bands) below the jaw, every third band
                    uv = px.vertex_uv()
                    band = np.floor(uv[:, 0] * 24).astype(int)
                    jaw = self.J("jaw")[1]
                    m_ = ((band % 3) == 1) & (P[:, 1] < jaw + 0.05)
                    cols[m_] = np.clip(f3(streak) * (0.5 + 0.6 * lum[m_, None]), 0, 1)
            else:
                cols = np.clip(rgba_v[:, :3] * t, 0, 1)
        else:
            cols = rgba_v[:, :3]
        keep = rgba_v[px.F, 3].mean(1) >= alpha_cut
        F = px.F[keep]
        ids = px.base_ids()
        idx, wt = B.weights_matrix(len(B.V0))
        m = trimesh.Trimesh(P, F, process=False)
        self.add(name, m, tint or [128, 128, 128, 255], idx=idx[ids], wt=wt[ids], colors=cols, gradient=False,
                 flags={"two_sided": two_sided, **(extra_flags or {})})

    # ── hair ──
    def build_hair(self):
        B, h = self.base, self.spec.get("hair", {})
        style = h.get("style", "long")
        if style == "bald":
            return
        col = rgba(h.get("color"), "#f4f6fa")
        if style.startswith("mh:"):
            # a MakeHuman hair asset (assets/mh/hair/<name>), recoloured to `color` by texture luminance
            self.add_proxy("hair", style[3:], "hair_mh", tint=col, tint_mode="lum", alpha_cut=float(h.get("alpha_cut", 0.5)), streak=rgba(h["streak"]) if h.get("streak") else None)
            return
        col2 = rgba(h.get("shade")) if h.get("shade") else shade(col, 0.88)
        streak = rgba(h["streak"]) if h.get("streak") else None  # under-layer / tips colour (every third strand)
        scalp = B.mesh("helper-hair")
        eye_y = self.J("eye.L")[1]
        head_c = self.J("head") + [0, 0.12, 0]
        Rh0 = 0.2 * float(self.spec.get("proportions", {}).get("head", 1.25))
        fv = scalp.vertices[scalp.faces]
        keep = (fv[:, :, 1] > eye_y + 0.07).all(1)
        if h.get("bangs") == "parted" or (style == "long" and h.get("bangs", "parted") is not False):
            # parted / swept-back: the hairline sits high on the forehead, the curtains cover the temples
            front = fv[:, :, 2].mean(1) > head_c[2] + Rh0 * 0.35
            # rounded hairline: highest at the part, sweeping down toward the temples
            # the curtains draw the visible hairline (their inner edge sweeps from the part to the temples);
            # the coarse scalp helper only keeps the crown behind that line
            fx = np.abs(fv[:, :, 0].mean(1) - head_c[0]) / Rh0
            hairline = head_c[1] + Rh0 * (0.42 - 0.3 * np.clip(fx, 0, 1))
            keep &= ~front | (fv[:, :, 1].mean(1) > hairline)
        scalp = trimesh.Trimesh(scalp.vertices, scalp.faces[keep], process=False)
        sv = scalp.vertices
        # inflate the scalp cap so the hair has body over the skull (more at the crown)
        d = sv - head_c
        scalp.vertices = sv + d / (np.linalg.norm(d, axis=1, keepdims=True) + 1e-9) * 0.012
        top = sv[:, 1].max()
        cap_ids = np.unique(scalp.faces)
        if style != "mohawk":
            head_c2 = self.J("head") + [0, 0.12, 0]
            Rh = 0.2 * float(self.spec.get("proportions", {}).get("head", 1.25))
            parted = h.get("bangs") == "parted" or style == "long"
            def scalp_paint(V, cols):
                out = cols.copy()
                shine = np.exp(-((V[:, 1] - (head_c2[1] + Rh * 0.55)) / (Rh * 0.2)) ** 2) * 0.12
                out = np.clip(out + shine[:, None], 0, 1)
                ang = np.arctan2(V[:, 0] - head_c2[0], V[:, 2] - head_c2[2])
                band = np.floor((ang + math.pi) / (2 * math.pi) * 36)
                out[(band % 3 == 0)] *= 0.9
                if parted:
                    groove = (np.abs(V[:, 0] - head_c2[0]) < 0.012) & (V[:, 2] > -0.05)
                    out[groove] *= 0.6
                return out
            self.add("scalp", scalp, col, paint=scalp_paint, rigid="head", gradient=False)
        rng = np.random.default_rng(3)
        pts = sv[cap_ids]
        R = 0.2 * float(self.spec.get("proportions", {}).get("head", 1.25))
        chin = self.J("jaw")[1] - 0.05

        def strands(sel, ends, r, taper=0.5, alt=True, rig="head"):
            for i, (p, e) in enumerate(zip(sel, ends)):
                c = col if (i % 3 or not alt) else (streak or col2)
                self.add(f"strand_{style}_{i}_{len(self.parts)}", clump(p, e, r, taper), c, rigid=rig, gradient=True)

        back = pts[(pts[:, 2] < 0.05) & (pts[:, 1] > top - 0.32)]
        front = pts[(pts[:, 2] > 0.12) & (pts[:, 1] > top - 0.12)]
        bangs = h.get("bangs", True)
        if style == "long":
            bangs = "curtain"  # long hair draws its own front as sheets (see hair_curtains)
        if bangs in (True, "full") and style not in ("mohawk", "slick", "bald"):
            sel = front[np.argsort(front[:, 0])][:: max(1, len(front) // 7)]
            ends = [(p[0] * 1.1, self.J("eye.L")[1] + 0.1, p[2] + 0.07) for p in sel]
            strands(sel, ends, 0.04, 0.5, alt=False)
        elif bangs == "parted" and style not in ("mohawk", "slick"):
            sel = front[np.argsort(front[:, 0])][:: max(1, len(front) // 6)]
            ends = [(np.sign(p[0]) * (0.17 + abs(p[0]) * 0.4), self.J("eye.L")[1] - 0.05 - abs(p[0]) * 0.5, 0.1 + abs(p[0]) * 0.3) for p in sel]
            strands(sel, ends, 0.04, 0.45, alt=False)
        if style == "long":
            end_y = {"shoulder": self.J("spine01")[1] + 0.05, "chest": self.J("spine02")[1], "waist": self.J("spine03")[1] - 0.05, "hips": self.J("root")[1] - 0.1}[h.get("length", "waist")]
            self.hair_mantle(end_y, col, col2, streak)
            side_end = {"shoulder": self.J("spine01")[1], "chest": self.J("spine02")[1] - 0.05, "waist": self.J("spine02")[1] - 0.2, "hips": self.J("spine03")[1]}[h.get("length", "waist")]
            self.hair_curtains(side_end, col, col2, streak, part=h.get("bangs", "parted") is not False)
            sel = back[rng.choice(len(back), 8, replace=False)]
            ends = [(p[0] * 1.4 + rng.normal(0, 0.02), end_y + rng.normal(0, 0.06), p[2] * 1.2 - 0.1) for p in sel]
            strands(sel, ends, 0.045, 0.55, rig=None)
        elif style == "bob":
            sel = np.vstack([back, pts[(np.abs(pts[:, 0]) > 0.12) & (pts[:, 1] > top - 0.25)]])
            sel = sel[rng.choice(len(sel), 18, replace=False)]
            ends = [(p[0] * 1.35, chin + rng.normal(0, 0.03), p[2] * 1.1 - 0.02) for p in sel]
            strands(sel, ends, 0.065, 0.5)
        elif style == "pixie":
            sel = pts[rng.choice(len(pts), 14, replace=False)]
            ends = [(p[0] * 1.3, p[1] - 0.12, p[2] * 1.25 - 0.03) for p in sel]
            strands(sel, ends, 0.05, 0.5)
        elif style == "spiky":
            crown = pts[pts[:, 1] > top - 0.18]
            sel = crown[rng.choice(len(crown), 12, replace=False)]
            ends = [(p[0] * 2.2, p[1] + 0.22 + rng.uniform(0, 0.08), p[2] - 0.28) for p in sel]
            strands(sel, ends, 0.055, 0.35)
            side = pts[(np.abs(pts[:, 0]) > 0.14) & (pts[:, 2] > 0.0)]
            sel = side[rng.choice(len(side), 6, replace=False)]
            strands(sel, [(p[0] * 1.3, p[1] - 0.14, p[2] + 0.05) for p in sel], 0.045, 0.45)
        elif style == "ponytail":
            n = self.J("head") + [0, 0.05, -0.2]
            self.add("tail", clump(n, (0, self.J("spine02")[1], -0.35), 0.09, 0.45), col2, rigid="head")
            self.add("tie", xf(torus(0.07, 0.018), M(*n, rx=70)), rgba(h.get("tie"), "#c9a86a"), rigid="head", gradient=False)
        elif style == "twintails":
            for sgn in (-1, 1):
                a = self.J("head") + [sgn * 0.2, -0.02, -0.05]
                self.add(f"tail_{sgn}", clump(a, (sgn * 0.28, self.J("spine03")[1], 0.0), 0.08, 0.45), col2, rigid="head")
                self.add(f"tie_{sgn}", xf(torus(0.065, 0.018), M(*a, rz=90)), rgba(h.get("tie"), "#c9a86a"), rigid="head", gradient=False)
        elif style == "bun":
            self.add("bun", xf(icosphere(3, 0.11), M(0, top + 0.02, -0.14)), col2, rigid="head")
        elif style == "curly":
            for i in range(30):
                p = pts[rng.integers(len(pts))]
                d = p - head_c
                d /= np.linalg.norm(d) + 1e-9
                q = p + d * rng.uniform(0.03, 0.09) + [0, -rng.uniform(0, 0.25), 0]
                self.add(f"curl_{i}", xf(icosphere(2, rng.uniform(0.05, 0.075)), M(*q)), col if i % 2 else col2, rigid="head")
        elif style == "mohawk":
            for i in range(7):
                z = 0.1 - i * 0.05
                self.add(f"hawk_{i}", clump((0, top - 0.02, z), (0, top + 0.22, z - 0.06), 0.045, 0.3), col, rigid="head")

    def hair_mantle(self, end_y, col, col2, streak=None):
        """Continuous curtain of hair over the back and sides, from the crown to end_y, fitted to head and torso."""
        B = self.base
        head = self.J("head") + [0, 0.12, 0]
        R = 0.2 * float(self.spec.get("proportions", {}).get("head", 1.25))
        top = head[1] + R * 0.9
        torso_ids = B.region(TORSO, 0.35)
        TV = B.V0[torso_ids]
        chest_y = self.J("spine02")[1]
        base_rings = self.rings_for(B.V0[B.region(["spine01", "spine02", "spine03", "spine04", "spine05"], 0.5)], [chest_y, chest_y - 0.15], 0.03)
        hang_rx = max(r[1] for r in base_rings) if base_rings else R * 1.3
        hang_cx = np.mean([r[3] for r in base_rings]) if base_rings else 0.0
        n_pts, rows, centers = 18, [], []
        th = np.radians(np.linspace(75, 285, n_pts))  # around the back, from temple to temple
        for y in np.linspace(top, end_y, 14):
            if y > head[1] - R * 0.7:  # skull: a thin sheet on the back of the head
                t = (y - (head[1] - R * 0.7)) / (top - (head[1] - R * 0.7))
                r = R * 1.02 * math.sqrt(max(0.05, 1 - (t * 1.15 - 0.15) ** 2)) + 0.012
                rx, rz, cx, cz = r, r * 0.97, head[0], head[2] - 0.02
            else:  # neck to hem: blend from head width to the hang width, sitting just off the back
                rr = self.rings_for(TV, [y], 0.045)
                rx0, rz0, cx0, cz0 = (rr[0][1], rr[0][2], rr[0][3], rr[0][4]) if rr else (hang_rx, 0.16, hang_cx, 0.0)
                # just clear of the garments (0.028 gap), hugging the back, narrowing toward the hem
                fall = (self.J("spine01")[1] - y) / max(0.2, self.J("spine01")[1] - end_y)
                rx = min(rx0 + 0.02, hang_rx + 0.02) * (1 - 0.12 * max(0, fall))
                rz, cx, cz = max(rz0, 0.11) + 0.035, cx0, cz0 - 0.012
            # V hem: the centre back hangs lowest, the sides lift toward the hem
            lift = max(0.0, (end_y + 0.4 - y) / 0.4) * 0.28 * np.abs(np.sin(th))
            rows.append(np.stack([cx + rx * np.sin(th), y + lift, cz + rz * np.cos(th)], 1))
            centers.append(np.array([cx, y, cz]))
        m = shell(rows, centers, 0.035)
        base, dark = f3(col), f3(col2)
        strk = f3(streak) if streak else None
        def paint(V, cols):
            ang = np.arctan2(V[:, 0] - V[:, 0].mean(), -(V[:, 2] - V[:, 2].mean()))
            band = np.floor((ang + math.pi) / (2 * math.pi) * 22)
            out = np.where((band % 3 == 0)[:, None], dark, base)
            if strk is not None:
                out = np.where((band % 7 == 3)[:, None], strk, out)
            t = (V[:, 1] - V[:, 1].min()) / max(1e-6, np.ptp(V[:, 1]))
            shine = np.exp(-((V[:, 1] - (head[1] + R * 0.55)) / (R * 0.2)) ** 2) * 0.14
            return np.clip(out * (0.82 + 0.22 * t)[:, None] + shine[:, None], 0, 1)
        # nearest-skin weights: the crown follows the head, the fall follows the back (a head-only rig would swing the hem into the torso)
        self.add("hair_mantle", m, col, paint=paint, gradient=False)

    def hair_curtains(self, end_y, col, col2, streak=None, part=True):
        """
        Two continuous sheets of hair, one per side: they hug the skull from the crown, sweep away from
        the centre part over the forehead, frame the face, then fall in front of the shoulders to end_y.
        """
        B = self.base
        head = self.J("head") + [0, 0.12, 0]
        R = 0.2 * float(self.spec.get("proportions", {}).get("head", 1.25))
        top = head[1] + R * 0.88
        brow_y, jaw_y = head[1] + R * 0.22, head[1] - R * 0.85
        neck_y = self.J("spine01")[1] + 0.16
        TV = B.V0[B.region(TORSO, 0.35)]
        base, dark = f3(col), f3(col2)
        strk = f3(streak) if streak else None
        hl_y = head[1] + R * 0.55  # painted shine band across the crown

        def torso_ring(y):
            rr = self.rings_for(TV, [y], 0.03)
            if rr:
                return rr[0][1] + 0.03, rr[0][2] + 0.04, rr[0][3], rr[0][4]
            return 0.3, 0.18, 0.0, 0.0

        for sgn in (-1, 1):
            rows, centers = [], []
            for y in np.linspace(top, end_y, 18):
                if y > jaw_y:  # a thin sheet on the skull; hair only gains body below the ears
                    u = (y - head[1]) / (R * 1.05)
                    below = max(0.0, (head[1] - R * 0.15 - y) / (R * 0.7))  # 0 at ear level → 1 at the jaw
                    r = R * 1.02 * math.sqrt(max(0.04, 1 - u * u)) + 0.012 + 0.05 * below
                    rx, rz, cx, cz = r, r * 0.98, head[0], head[2] - 0.02
                elif y > neck_y:  # blend jaw → shoulders
                    t = (jaw_y - y) / max(1e-6, jaw_y - neck_y)
                    r = R * 0.75
                    tx, tz, tcx, tcz = torso_ring(neck_y)
                    rx, rz = r * (1 - t) + tx * t, r * 0.98 * (1 - t) + tz * t
                    cx, cz = head[0] * (1 - t) + tcx * t, (head[2] - 0.02) * (1 - t) + tcz * t
                else:
                    rx, rz, cx, cz = torso_ring(y)
                # inner edge: from the part at the crown it sweeps to the temple (≈50° off centre) by brow
                # level and stays there, so the whole face and the cheeks are open like in the references
                if not part:
                    th0 = 40.0
                elif y >= brow_y:
                    th0 = 8.0 + 44.0 * (top - y) / max(1e-6, top - brow_y)
                else:
                    th0 = 52.0
                th = np.radians(np.linspace(th0, 96.0, 8)) * sgn
                f = max(0.0, (y - end_y) / max(1e-6, top - end_y))  # 1 at the crown, 0 at the ends
                curl = 1 - 0.18 * max(0.0, 1 - f / 0.22)  # the last fifth tucks inward
                rows.append(np.stack([cx + rx * curl * np.sin(th), np.full(8, y), cz + rz * curl * np.cos(th)], 1))
                centers.append(np.array([cx, y, cz]))
            m = shell(rows, centers, 0.04)

            def paint(V, cols, sgn=sgn):
                ang = np.arctan2((V[:, 0] - V[:, 0].mean()) * sgn, (V[:, 2] - V[:, 2].mean()))
                band = np.floor((ang + math.pi) / (2 * math.pi) * 40)
                out = np.where((band % 3 == 0)[:, None], dark, base)
                if strk is not None:
                    out = np.where((band % 5 == 2)[:, None], strk, out)
                shine = np.exp(-((V[:, 1] - hl_y) / (R * 0.2)) ** 2) * 0.14
                t = (V[:, 1] - V[:, 1].min()) / max(1e-6, np.ptp(V[:, 1]))
                return np.clip(out * (0.8 + 0.22 * t)[:, None] + shine[:, None], 0, 1)

            self.add(f"hair_curtain_{sgn}", m, col, paint=paint, gradient=False)

    # ── garments ──
    def rings_for(self, verts, ys, gap):
        out = []
        for y in ys:
            sl = verts[np.abs(verts[:, 1] - y) < 0.03]
            if len(sl) < 6:
                sl = verts[np.abs(verts[:, 1] - y) < 0.06]
            if len(sl) < 6:
                continue
            cx, cz = (sl[:, 0].max() + sl[:, 0].min()) / 2, (sl[:, 2].max() + sl[:, 2].min()) / 2
            rx, rz = (sl[:, 0].max() - sl[:, 0].min()) / 2 + gap, (sl[:, 2].max() - sl[:, 2].min()) / 2 + gap
            out.append((y, rx, rz, cx, cz))
        return out

    def limb_garment(self, chain_bones, t0, t1, gap, color, paint=None, name="g", segments=20, rings_n=7):
        """Tube fitted around a limb between fractions t0..t1 of the chain, in the rest pose."""
        B = self.base
        head, tail = B.bones[chain_bones[0]].head, B.bones[chain_bones[-1]].tail
        axis = tail - head
        L = np.linalg.norm(axis)
        y = axis / L
        up = np.array([0, 0, 1.0]) if abs(y[1]) > 0.9 else np.array([0, 1.0, 0])
        x = np.cross(up, y)
        x /= np.linalg.norm(x)
        z = np.cross(x, y)
        R = np.stack([x, y, z], 1)  # columns
        ids = B.region(chain_bones, 0.6)
        local = (B.V0[ids] - head) @ R
        rings = []
        for t in np.linspace(t0, t1, rings_n):
            yy = t * L
            sl = local[np.abs(local[:, 1] - yy) < L * 0.05]
            if len(sl) < 6:
                continue
            d = np.sqrt(sl[:, 0] ** 2 + sl[:, 2] ** 2)
            r = np.percentile(d, 85) + gap  # robust to stray hip/shoulder vertices in the slice
            rings.append((yy, r, r, 0, 0))
        # no ring may be wildly bigger than its neighbours (the hip end of a thigh)
        if len(rings) >= 3:
            med = np.median([r[1] for r in rings])
            rings = [(y, min(r, med * 1.35), min(r, med * 1.35), 0, 0) for y, r, _, _, _ in rings]
        if len(rings) < 2:
            return
        m = ring_lathe(rings, segments)
        m.vertices = m.vertices @ R.T + head
        self.add(name, m, color, paint=paint)

    def build_cloth(self):
        B, s = self.base, self.spec
        o = s.get("outfit", {})
        kind = o.get("type", "tunic")
        c1 = rgba(o.get("primary"), "#141418")
        c2 = rgba(o.get("secondary")) if o.get("secondary") else shade(c1, 1.4)
        acc = rgba(o.get("accent"), "#c9a86a")
        gap = 0.028
        torso_ids = B.region(TORSO, 0.35)
        TV = B.V0[torso_ids]
        hip_y, waist_y, chest_y, shoulder_y = self.J("root")[1], self.J("spine03")[1], self.J("spine01")[1] - 0.05, self.J("spine01")[1] + 0.2
        crotch_y = self.J("upperleg01.L")[1] - 0.05
        print_col = f3(rgba(o["print"])) if o.get("print") else None
        pattern = o.get("pattern")
        pat = f3(rgba(o.get("pattern_color"), "#2a2a2e")) if pattern else None

        def chest_print(V, cols):
            if print_col is None:
                return cols
            cy = chest_y + 0.02
            d = (V[:, 0] / 0.17) ** 2 + ((V[:, 1] - cy) / 0.11) ** 2
            m = (d < 1) & (V[:, 2] > 0.05)
            cols = cols.copy()
            cols[m] = print_col
            return cols

        def leopard(V, cols):
            # gold base with clustered dark rosettes, hashed from vertex position
            h1 = np.sin(V[:, 0] * 61.7 + V[:, 1] * 43.1 + V[:, 2] * 77.3) * 43758.5
            n = h1 - np.floor(h1)
            spot = n > 0.62
            cols = cols.copy()
            cols[spot] = f3(rgba(o.get("pattern_color"), "#3a2412"))
            return cols

        def fishnet(V, cols):
            # diamond net: dark where the grid lines cross, skin between (garment is drawn in skin colour)
            u = np.floor(V[:, 1] * 34) + np.floor((V[:, 0] + V[:, 2]) * 34)
            line = (u % 2) == 0
            cols = cols.copy()
            cols[line] = cols[line] * 0.35
            return cols

        painters = {"stripes": None, "leopard": leopard, "fishnet": fishnet}

        def stripes(V, cols):
            if pattern != "stripes":
                return cols
            th = np.arctan2(V[:, 2] - V[:, 2].mean(), V[:, 0] - V[:, 0].mean())
            band = (np.floor((th + math.pi) / (2 * math.pi) * 8) % 2) == 0
            cols = cols.copy()
            cols[band] = cols[band] * 0.35 + pat * 0.65
            return cols

        def top(y0, y1, extra=0.0, name="top", paint=chest_print, color=c1):
            ys = np.linspace(y0, y1, 9)
            rings = self.rings_for(TV, ys, gap + extra)
            if len(rings) >= 2:
                self.add(name, ring_lathe(rings, 32), color, paint=paint)

        def belt(y, col, h=0.05, extra=0.01):
            rings = self.rings_for(TV, [y - h / 2, y + h / 2], gap + extra)
            if len(rings) == 2:
                self.add(f"belt_{y:.2f}", ring_lathe(rings, 32), col, gradient=False)

        def skirt(y_top, y_hem, flare, col, pleats=0):
            r0 = self.rings_for(TV, [y_top], gap)[0]
            rings = [(y_hem, r0[1] * flare, r0[2] * flare, r0[3], r0[4]), (y_hem + (y_top - y_hem) * 0.5, r0[1] * (1 + (flare - 1) * 0.45), r0[2] * (1 + (flare - 1) * 0.45), r0[3], r0[4]), r0]
            self.add("skirt", ring_lathe(rings, 36, wave=(lambda i, t: 1 + (0.04 * math.sin(t * pleats) if pleats and i == 0 else 0.0))), col)

        sleeves = o.get("sleeves", "none")
        if sleeves is True:
            sleeves = "long"
        legwear = o.get("legwear", kind.endswith("pants") or kind in ("suit", "armor", "tunic"))

        if kind in ("tee_skirt", "tee_pants", "polo_skirt", "polo_pants", "crop_top", "crop_shorts"):
            y0 = waist_y + (0.12 if kind.startswith("crop") else 0.0)
            top(y0, shoulder_y)
            if kind == "crop_shorts":
                bottom_paint = painters.get(o.get("bottom_pattern"))
                for side in ("L", "R"):
                    self.limb_garment(THIGH[side], -0.18, 0.42, gap, c2, paint=bottom_paint, name=f"shorts_{side}", segments=32, rings_n=12)
                rings = self.rings_for(TV, np.linspace(crotch_y - 0.06, hip_y + 0.05, 4), gap * 1.1)
                if len(rings) >= 2:
                    self.add("shorts_hips", ring_lathe(rings, 32), c2, paint=bottom_paint)
                belt(hip_y + 0.05, acc, 0.04)
            if kind.startswith("polo"):
                n = self.J("neck01")
                for sgn in (-1, 1):
                    self.add(f"collar_{sgn}", xf(box([0.13, 0.07, 0.015]), M(sgn * 0.07, n[1] - 0.02, 0.13, rz=sgn * 40, rx=-25)), shade(c1, 0.95), gradient=False, rigid="spine01")
                self.add("placket", xf(box([0.02, 0.12, 0.01]), M(0, n[1] - 0.1, 0.16)), shade(c1, 0.9), gradient=False, rigid="spine01")
            if kind.endswith("skirt"):
                belt(hip_y + 0.02, acc, 0.05)
                if o.get("buckle"):
                    r = self.rings_for(TV, [hip_y + 0.02], gap)[0]
                    self.add("buckle", xf(box([0.08, 0.05, 0.02]), M(0, hip_y + 0.02, r[4] + r[2] + 0.01)), rgba(o["buckle"]), gradient=False, rigid="root")
                skirt(hip_y + 0.02, crotch_y - 0.12, 1.3, c2, o.get("pleats", 0))
            else:
                belt(hip_y + 0.02, acc, 0.05)
        elif kind == "dress":
            top(waist_y - 0.05, shoulder_y, name="bodice")
            belt(waist_y, c2, 0.05)
            skirt(waist_y, max(0.08, self.J("lowerleg01.L")[1] + (0.05 if o.get("length", "knee") == "knee" else -0.35)), 1.7, c1, o.get("pleats", 0))
        elif kind == "tunic":
            top(hip_y - 0.12, shoulder_y, 0.01, name="tunic")
            belt(waist_y - 0.02, acc, 0.06)
        elif kind == "armor":
            top(hip_y - 0.05, shoulder_y, 0.015, name="gambeson", paint=None)
            self.add("chest_plate", xf(icosphere(3, 0.2), M(0, chest_y + 0.02, 0.1), sy=0.75, sz=0.55), c2, rigid="spine01")
            for side in ("L", "R"):
                self.add(f"pauldron_{side}", xf(icosphere(3, 0.11), M(*(self.J(f"upperarm01.{side}") + [0, 0.02, 0])), sy=0.8), c2, rigid=f"upperarm01.{side}")
            belt(hip_y + 0.02, acc, 0.06)
            r = self.rings_for(TV, [hip_y], gap)[0]
            self.add("tassets", ring_lathe([(crotch_y - 0.1, r[1] * 1.3, r[2] * 1.3, r[3], r[4]), r], 12), c1)
        elif kind == "robe":
            r = self.rings_for(TV, [hip_y], gap)[0]
            top(hip_y, shoulder_y, name="robe_top")
            self.add("robe", ring_lathe([(0.08, r[1] * 2.0, r[2] * 2.0, r[3], r[4]), (hip_y, r[1], r[2], r[3], r[4])], 32), c1)
            self.add("robe_trim", ring_lathe([(0.07, r[1] * 2.02, r[2] * 2.02, r[3], r[4]), (0.13, r[1] * 2.0, r[2] * 2.0, r[3], r[4])], 32), acc, gradient=False)
            belt(waist_y, c2, 0.05)
        elif kind in ("jacket_skirt", "jacket_pants", "vest", "suit"):
            top(waist_y - 0.02, shoulder_y, 0.015, name="jacket")
            if kind == "vest":
                self.add("shirt", xf(box([0.14, 0.34, 0.015]), M(0, chest_y - 0.02, 0.17)), rgba(o.get("shirt"), "#f2f2f2"), gradient=False, rigid="spine01")
                for sgn in (-1, 1):
                    self.add(f"lapel_{sgn}", xf(box([0.08, 0.22, 0.02]), M(sgn * 0.1, chest_y + 0.05, 0.19, rz=sgn * -14)), acc, gradient=False, rigid="spine01")
            elif kind == "suit":
                self.add("shirt", xf(box([0.12, 0.3, 0.015]), M(0, chest_y, 0.17)), [245, 245, 245, 255], gradient=False, rigid="spine01")
                self.add("tie", xf(box([0.045, 0.25, 0.015]), M(0, chest_y - 0.03, 0.19)), acc, gradient=False, rigid="spine01")
            if kind == "jacket_skirt":
                skirt(hip_y + 0.02, crotch_y - 0.12, 1.3, c2, o.get("pleats", 0))
            belt(waist_y - 0.02, acc, 0.05)
        else:
            raise ValueError(f"unknown outfit type {kind!r}")

        for side in ("L", "R"):
            if sleeves in ("short", "long"):
                self.limb_garment(ARM[side], -0.05, 0.55 if sleeves == "short" else 1.0, gap, c1, name=f"sleeve_{side}")
                if sleeves == "long":
                    self.limb_garment(FOREARM[side], 0.0, 0.95, gap * 0.8, c1, name=f"cuff_{side}")
            if legwear:
                self.limb_garment(THIGH[side], -0.15, 1.02, gap, c2, paint=stripes, name=f"pants_thigh_{side}")
                self.limb_garment(SHIN[side], 0.0, 0.9, gap * 0.9, c2, paint=stripes, name=f"pants_shin_{side}")
        if o.get("tights"):
            # tights drawn over the skin in skin colour with a pattern (fishnet) or a solid colour
            tcol = self.skin_col if o["tights"] == "fishnet" else rgba(o.get("tights_color"), "#1a1a1e")
            tp = fishnet if o["tights"] == "fishnet" else None
            for side in ("L", "R"):
                self.limb_garment(THIGH[side], 0.3 if kind == "crop_shorts" else -0.1, 1.02, gap * 0.4, tcol, paint=tp, name=f"tights_thigh_{side}", segments=32, rings_n=18)
                self.limb_garment(SHIN[side], 0.0, 0.96, gap * 0.4, tcol, paint=tp, name=f"tights_shin_{side}", segments=32, rings_n=18)
        if legwear:
            rings = self.rings_for(TV, np.linspace(crotch_y - 0.06, hip_y + 0.04, 4), gap * 1.1)
            if len(rings) >= 2:
                self.add("pants_hips", ring_lathe(rings, 28), c2, paint=stripes)
        self.build_feet()

    def build_feet(self):
        B, bt = self.base, self.spec.get("boots", {})
        col = rgba(bt.get("color"), "#141418")
        height = bt.get("height", "ankle")
        for side in ("L", "R"):
            f = self.J(f"foot.{side}")
            toe = B.bones[f"toe1-1.{side}"].tail if f"toe1-1.{side}" in B.bones else f + [0, -0.1, 0.25]
            if height == "knee":
                self.limb_garment(SHIN[side], 0.05, 1.0, 0.03, col, name=f"boot_{side}")
            elif height == "ankle":
                self.limb_garment(SHIN[side], 0.72, 1.0, 0.03, col, name=f"boot_{side}")
            if height == "heel":
                # High heel: the foot is drawn as-is; a wedge sole under the ball, a slim heel block under the
                # heel, a toe cap and an ankle strap. The block reaches below y=0 so grounding lifts the whole
                # figure onto its heels.
                tilt = float(bt.get("heel_tilt", 38))
                heel_pt = f + [0, -0.11, -0.05]  # bottom of the heel in the rest pose
                lift = 0.22 * math.sin(math.radians(tilt))  # how far the toes drop when the foot tilts
                # the block is pre-rotated by -tilt so it stands vertical once the foot bone tilts it back
                self.add(f"heel_block_{side}", xf(box([0.045, lift + 0.03, 0.045]), M(heel_pt[0], heel_pt[1], heel_pt[2]) @ M(0, -(lift + 0.03) / 2, 0, rx=-tilt)), shade(col, 0.75), rigid=f"foot.{side}", gradient=False)
                self.add(f"sole_{side}", xf(box([0.13, 0.03, 0.27]), M(f[0], heel_pt[1] - 0.005, f[2] + 0.09)), col, rigid=f"foot.{side}", gradient=False)
                self.add(f"toe_cap_{side}", xf(icosphere(2, 1.0), M(f[0], 0.045, f[2] + 0.22), sx=0.065, sy=0.04, sz=0.07), col, rigid=f"foot.{side}", gradient=False)
                self.add(f"strap_{side}", xf(torus(0.05, 0.011), M(f[0], 0.12, f[2] + 0.01, rx=90)), col, rigid=f"foot.{side}", gradient=False)
                continue
            self.add(f"shoe_{side}", xf(icosphere(3, 1.0), M(f[0], 0.075, f[2] + 0.12), sx=0.1, sy=0.08, sz=0.23), col, rigid=f"foot.{side}")
            self.add(f"sole_{side}", xf(box([0.17, 0.035, 0.38]), M(f[0], 0.018, f[2] + 0.12)), shade(col, 0.6), rigid=f"foot.{side}", gradient=False)

    # ── accessories & props ──
    def build_accessories(self):
        B, s = self.base, self.spec
        colors = s.get("accessory_colors", {})
        gold = [222, 178, 90, 255]
        c = lambda k, d: rgba(colors[k]) if colors.get(k) else d
        eL, eR = self.J("eye.L"), self.J("eye.R")
        ey, ez = eL[1], eL[2]
        for a in s.get("accessories", []):
            if a == "sunglasses":
                lens = f3(c(a, [40, 30, 60, 255]))
                frame = c("sunglasses_frame", [240, 240, 240, 255])
                def lens_paint(V, cols):
                    t = (V[:, 1] - V[:, 1].min()) / max(1e-6, np.ptp(V[:, 1]))
                    dark, light = lens * 0.45, np.clip(lens * 0.8 + 0.3, 0, 1)
                    return dark[None] * t[:, None] + light[None] * (1 - t[:, None])
                for e, sgn in ((eL, 1), (eR, -1)):
                    self.add(f"lens_{sgn}", xf(box([0.15, 0.1, 0.012]), M(e[0] + sgn * 0.012, ey - 0.005, ez + 0.085, ry=sgn * 22, rx=-8)), c(a, [40, 30, 60, 255]), paint=lens_paint, gradient=False, rigid="head")
                    self.add(f"rim_{sgn}", xf(box([0.16, 0.018, 0.015]), M(e[0] + sgn * 0.012, ey + 0.05, ez + 0.09, ry=sgn * 22)), frame, gradient=False, rigid="head")
                self.add("bridge", xf(box([0.05, 0.015, 0.015]), M(0, ey + 0.045, ez + 0.11)), frame, gradient=False, rigid="head")
                for sgn in (-1, 1):
                    self.add(f"shade_arm_{sgn}", xf(box([0.01, 0.012, 0.28]), M(sgn * 0.2, ey + 0.045, ez - 0.04)), frame, gradient=False, rigid="head")
            elif a == "glasses":
                for e, sgn in ((eL, 1), (eR, -1)):
                    self.add(f"glasses_{sgn}", xf(torus(0.05, 0.005), M(e[0], ey, ez + 0.05)), c(a, [30, 30, 34, 255]), gradient=False, rigid="head")
                self.add("glasses_bridge", xf(box([0.06, 0.006, 0.006]), M(0, ey, ez + 0.05)), c(a, [30, 30, 34, 255]), gradient=False, rigid="head")
            elif a == "shoulder_bag":
                col = c(a, [90, 60, 40, 255])
                sh, hp = self.J("shoulder01.R"), self.J("root")
                self.add("bag_strap", clump((sh[0] * 0.6, sh[1] + 0.04, 0.12), (-sh[0] * 0.2 - 0.32, hp[1] - 0.05, 0.05), 0.012, 0.95, 8), col, gradient=False)
                self.add("bag", xf(box([0.2, 0.17, 0.1]), M(-0.36, hp[1] - 0.02, 0.02)), col, rigid="root")
            elif a == "bracelets":
                col = c(a, [230, 80, 120, 255])
                for side in ("L", "R"):
                    w = self.J(f"wrist.{side}")
                    d = B.bones[f"wrist.{side}"].tail - w
                    for j, k in enumerate((-0.02, 0.02)):
                        p = w + d / np.linalg.norm(d) * k * 2
                        self.add(f"bracelet_{side}_{j}", xf(torus(0.045, 0.008), M(*p, rx=90, rz=35 * (1 if side == "L" else -1))), col if j == 0 else shade(col, 1.3), gradient=False, rigid=f"wrist.{side}")
            elif a == "earrings":
                for sgn in (-1, 1):
                    self.add(f"earring_{sgn}", xf(icosphere(2, 0.014), M(sgn * 0.2, ey - 0.1, 0.0)), c(a, gold), gradient=False, rigid="head")
            elif a == "necklace":
                n = self.J("neck01")
                self.add("necklace", xf(torus(0.11, 0.006), M(0, n[1] - 0.02, 0.02, rx=80)), c(a, gold), gradient=False, rigid="spine01")
            elif a == "crown":
                t = self.J("head")[1] + 0.25
                self.add("crown", xf(torus(0.17, 0.014), M(0, t, -0.02, rx=90)), c(a, gold), gradient=False, rigid="head")
            elif a == "cape":
                r = self.J("root")
                sh = self.J("spine01")
                self.add("cape", ring_lathe([(0.15, 0.36, 0.2, 0, -0.22), (sh[1] + 0.15, 0.25, 0.12, 0, -0.12)], 24), c(a, [120, 30, 40, 255]))
            elif a == "gauntlets":
                col, trim = c(a, [40, 50, 90, 255]), c("gauntlets_trim", gold)
                for side in ("L", "R"):
                    w = self.J(f"wrist.{side}")
                    d = B.bones[f"wrist.{side}"].tail - w
                    d /= np.linalg.norm(d)
                    ctr = w + d * 0.16
                    self.add(f"gauntlet_{side}", xf(box([0.34, 0.3, 0.36]), M(*ctr)), col, rigid=f"wrist.{side}")
                    self.limb_garment(FOREARM[side], 0.3, 1.0, 0.09, col, name=f"gauntlet_cuff_{side}", segments=16)
                    for k in range(4):
                        self.add(f"knuckle_{side}_{k}", xf(box([0.07, 0.07, 0.08]), M(*(ctr + d * 0.2 + [(k - 1.5) * 0.08, 0.05, 0]))), trim, gradient=False, rigid=f"wrist.{side}")
            elif a in ("gloves", "fishnet_gloves"):
                col = c(a, [30, 30, 34, 255])
                for side in ("L", "R"):
                    pnt = (lambda V, cols: (lambda k: np.where(((np.floor(V[:, 1] * 40) + np.floor((V[:, 0] + V[:, 2]) * 40)) % 2 == 0)[:, None], cols * 0.3, cols))(0)) if a == "fishnet_gloves" else None
                    self.limb_garment(FOREARM[side], 0.35, 1.0, 0.018, self.skin_col if a == "fishnet_gloves" else col, paint=pnt, name=f"glove_{side}", segments=24, rings_n=12)
                    w = self.J(f"wrist.{side}")
                    self.add(f"glove_band_{side}", xf(torus(0.052, 0.01), M(*w, rx=90, rz=35 * (1 if side == "L" else -1))), col, gradient=False, rigid=f"wrist.{side}")
            elif a == "knee_pads":
                for side in ("L", "R"):
                    k = self.J(f"lowerleg01.{side}")
                    self.add(f"kneepad_{side}", xf(icosphere(2, 0.075), M(k[0], k[1] + 0.02, k[2] + 0.06), sz=0.6), c(a, [60, 60, 70, 255]), rigid=f"lowerleg01.{side}")
            elif a == "belt_pouch":
                r = self.J("root")
                self.add("pouch", xf(box([0.1, 0.12, 0.08]), M(0.24, r[1] - 0.1, 0.04)), c(a, [70, 45, 35, 255]), rigid="root")
            else:
                raise ValueError(f"unknown accessory {a!r} for the base-mesh engine")

    def build_prop(self):
        p = self.spec.get("prop", {})
        kind = p.get("type", "none")
        if kind == "none":
            return
        B = self.base
        col = rgba(p.get("color"), "#c0c4cc")
        acc = rgba(p.get("accent"), "#c9a86a")
        w = self.J("wrist.R")
        d = B.bones["wrist.R"].tail - w
        d /= np.linalg.norm(d)
        # a grip frame: local -Y along the hand, so weapons extend along the hand direction
        y = -d
        up = np.array([0, 0, 1.0])
        x = np.cross(up, y)
        x /= np.linalg.norm(x)
        z = np.cross(x, y)
        F = np.eye(4)
        F[:3, 0], F[:3, 1], F[:3, 2], F[:3, 3] = x, y, z, w + d * 0.08
        if kind == "sword":
            self.add("blade", xf(box([0.04, 1.1, 0.015]), F @ M(0, 0.6, 0)), col, gradient=False, rigid="wrist.R")
            self.add("guard", xf(box([0.18, 0.03, 0.04]), F @ M(0, 0.05, 0)), acc, gradient=False, rigid="wrist.R")
            self.add("grip", xf(box([0.03, 0.16, 0.035]), F @ M(0, -0.06, 0)), shade(acc, 0.5), gradient=False, rigid="wrist.R")
        elif kind == "dagger":
            self.add("blade", xf(box([0.035, 0.45, 0.012]), F @ M(0, 0.28, 0)), col, gradient=False, rigid="wrist.R")
            self.add("guard", xf(box([0.11, 0.025, 0.035]), F @ M(0, 0.04, 0)), acc, gradient=False, rigid="wrist.R")
        elif kind == "staff":
            self.add("staff", xf(box([0.035, 2.0, 0.035]), F @ M(0, 0.5, 0)), shade(acc, 0.6), rigid="wrist.R")
            self.add("orb", xf(icosphere(3, 0.09), F @ M(0, 1.55, 0)), col, gradient=False, rigid="wrist.R")
        elif kind == "wand":
            self.add("wand", xf(box([0.02, 0.5, 0.02]), F @ M(0, 0.22, 0)), shade(acc, 0.6), gradient=False, rigid="wrist.R")
            self.add("star", xf(icosphere(2, 0.05), F @ M(0, 0.5, 0)), col, gradient=False, rigid="wrist.R")
        elif kind == "mic":
            self.add("mic", xf(box([0.035, 0.22, 0.035]), F @ M(0, 0.08, 0)), shade(col, 0.4), gradient=False, rigid="wrist.R")
            self.add("mic_head", xf(icosphere(2, 0.055), F @ M(0, 0.24, 0)), col, gradient=False, rigid="wrist.R")
        elif kind == "shield":
            wl = self.J("lowerarm01.L")
            self.add("shield", xf(ring_lathe([(-0.02, 0.32, 0.32, 0, 0), (0.02, 0.26, 0.26, 0, 0)], 24), M(wl[0] + 0.12, wl[1] - 0.1, wl[2], rz=90)), col, rigid="lowerarm01.L")
        elif kind == "book":
            self.add("book", xf(box([0.2, 0.26, 0.05]), F @ M(0, 0.1, 0.05, rx=-25)), col, rigid="wrist.R")
        else:
            raise ValueError(f"unknown prop {kind!r} for the base-mesh engine")

    # ── assemble ──
    def build(self):
        self.build_body()
        self.build_hair()
        self.build_cloth()
        self.build_accessories()
        self.build_prop()
        mats = self.rig.pose(self.pose)
        out = []
        for name, V, F, color, cols, idx, wt, flags in self.parts:
            P = skin(V, idx, wt, mats)
            out.append((name, trimesh.Trimesh(P, F, process=False), color, cols, flags))
        lo = min(p[1].bounds[0][1] for p in out)
        for p in out:
            p[1].apply_translation([0, -lo, 0])
        return out


class FigureProps:
    """Adapter so build.py can read head size like the procedural Character."""
    def __init__(self, fig: Figure):
        self.head_r = 0.19 * float(fig.spec.get("proportions", {}).get("head", 1.25))
