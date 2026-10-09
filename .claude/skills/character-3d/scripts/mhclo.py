"""
MakeHuman proxy assets (.mhclo + .obj + diffuse texture): hair, eyebrows, clothes.

Each asset vertex is defined relative to three base-mesh vertices (weights + an offset scaled by
reference distances on the base), so it follows any base morph. We turn one into a renderer part:
positions from the current Base, vertex colours sampled from the diffuse texture (optionally tinted),
faces whose texture alpha is mostly transparent dropped, skin weights copied from the base vertices.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

MH = Path(__file__).resolve().parents[1] / "assets" / "mh"


class Proxy:
    def __init__(self, kind: str, name: str):
        d = MH / kind / name
        self.name = name
        self.ref = []  # (i0, i1, i2, w0, w1, w2, ox, oy, oz)
        self.scale = {}
        obj = None
        for line in open(d / f"{name}.mhclo"):
            t = line.split()
            if not t or line.startswith("#"):
                continue
            if t[0] in ("x_scale", "y_scale", "z_scale"):
                self.scale[t[0][0]] = (int(t[1]), int(t[2]), float(t[3]))
            elif t[0] == "obj_file":
                obj = t[1]
            elif t[0] == "verts":
                continue
            elif len(t) == 9 and t[0].isdigit():
                self.ref.append([float(x) for x in t])
            elif len(t) == 1 and t[0].isdigit():  # a lone base vertex id: the vertex is exactly that base vertex
                i = int(t[0])
                self.ref.append([i, i, i, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0])
        self.ref = np.asarray(self.ref, float)
        V, VT, F, FT = [], [], [], []
        for line in open(d / obj):
            t = line.split()
            if not t:
                continue
            if t[0] == "v":
                V.append([float(x) for x in t[1:4]])
            elif t[0] == "vt":
                VT.append([float(t[1]), float(t[2])])
            elif t[0] == "f":
                idx = [c.split("/") for c in t[1:]]
                vi = [int(c[0]) - 1 for c in idx]
                ti = [int(c[1]) - 1 if len(c) > 1 and c[1] else -1 for c in idx]
                for k in range(1, len(vi) - 1):
                    F.append([vi[0], vi[k], vi[k + 1]])
                    FT.append([ti[0], ti[k], ti[k + 1]])
        self.n = len(V)
        self.F = np.asarray(F)
        self.FT = np.asarray(FT)
        self.VT = np.asarray(VT) if VT else None
        tex = d / f"{name}_diffuse.png"
        if not tex.exists():
            tex = d / f"{name}.png"
        self.tex = np.asarray(Image.open(tex).convert("RGBA"), np.float32) / 255 if tex.exists() else None

    def positions(self, base_V0: np.ndarray, native_scale: float):
        """Asset vertices for the given (already normalised) base vertices; native_scale = our units per MakeHuman unit."""
        r = self.ref
        i = r[:, :3].astype(int)
        w = r[:, 3:6]
        P = (base_V0[i[:, 0]] * w[:, :1] + base_V0[i[:, 1]] * w[:, 1:2] + base_V0[i[:, 2]] * w[:, 2:3])
        off = r[:, 6:9].copy()
        for k, ax in enumerate("xyz"):
            a, b, den = self.scale[ax]
            s = abs(base_V0[a][k] - base_V0[b][k]) / (den * native_scale)  # current/reference along that axis
            off[:, k] *= s * native_scale
        return P + off

    def vertex_uv(self):
        """One UV per vertex (average of its face corners)."""
        uv = np.zeros((self.n, 2))
        cnt = np.zeros(self.n)
        for f, ft in zip(self.F, self.FT):
            for v, t in zip(f, ft):
                if t >= 0:
                    uv[v] += self.VT[t]
                    cnt[v] += 1
        cnt[cnt == 0] = 1
        return uv / cnt[:, None]

    def sample(self, uv):
        """RGBA per vertex from the diffuse texture."""
        if self.tex is None:
            return np.tile([0.5, 0.5, 0.5, 1.0], (len(uv), 1))
        h, w = self.tex.shape[:2]
        x = np.clip((uv[:, 0] % 1.0) * (w - 1), 0, w - 1).astype(int)
        y = np.clip(((1 - uv[:, 1]) % 1.0) * (h - 1), 0, h - 1).astype(int)
        return self.tex[y, x]

    def base_ids(self):
        """The dominant base vertex per asset vertex (for skin weights)."""
        r = self.ref
        k = np.argmax(r[:, 3:6], axis=1)
        return r[np.arange(len(r)), k].astype(int)
