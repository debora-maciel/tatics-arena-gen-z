"""
MakeHuman base mesh (CC0, assets/base.obj) + its skeleton and skin weights, as a posable figure.

- `Base` loads the body, eye/eyelash/scalp helpers, joint positions, bone hierarchy and weights.
- `Rig.pose(rotations)` gives world matrices per bone; `skin(V, W, mats)` deforms any vertices
  that carry bone weights (linear blend skinning). Attachments (hair, cloth, props) get weights
  from the nearest body vertex or a single bone, so they follow the pose.
- Units: the body is scaled so its rest height is HEIGHT and its feet sit on y = 0; it faces +Z.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import trimesh
from scipy.spatial import cKDTree

ASSETS = Path(__file__).resolve().parents[1] / "assets"
HEIGHT = 3.0


def _tri(face):
    return [[face[0], face[i], face[i + 1]] for i in range(1, len(face) - 1)]


@dataclass
class Bone:
    name: str
    parent: str | None
    head: np.ndarray
    tail: np.ndarray


class Base:
    def __init__(self, head_scale=1.0, slim=1.0, arms=1.0, legs=1.0):
        V, groups, cur = [], {}, None
        for line in open(ASSETS / "base.obj"):
            if line.startswith("v "):
                V.append([float(x) for x in line.split()[1:4]])
            elif line.startswith("g "):
                cur = line[2:].strip()
                groups.setdefault(cur, [])
            elif line.startswith("f ") and cur:
                groups[cur] += _tri([int(t.split("/")[0]) - 1 for t in line.split()[1:]])
        V = np.asarray(V, float)
        # normalise: feet on the ground, HEIGHT tall
        body_idx = np.unique(np.asarray(groups["body"]))
        lo, hi = V[body_idx].min(0), V[body_idx].max(0)
        s = HEIGHT / (hi[1] - lo[1])
        self.native_scale = s  # our units per MakeHuman unit (proxy offsets are in MakeHuman units)
        V = (V - [0, lo[1], 0]) * s
        V[:, 0] -= (V[body_idx, 0].max() + V[body_idx, 0].min()) / 2
        self.V0 = V
        self.groups = {k: np.asarray(v) for k, v in groups.items()}
        self.faces = {k: self.groups[k] for k in ("body", "helper-l-eye", "helper-r-eye", "helper-hair", "helper-l-eyelashes-1", "helper-r-eyelashes-1")}

        sk = json.load(open(ASSETS / "default.mhskel"))
        self.joint = {name: V[np.asarray(ids)].mean(0) for name, ids in sk["joints"].items()}
        self.bones: dict[str, Bone] = {}
        for name, b in sk["bones"].items():
            self.bones[name] = Bone(name, b["parent"], self.joint[b["head"]], self.joint[b["tail"]])
        self.order = self._topo()

        w = json.load(open(ASSETS / "default_weights.mhw"))["weights"]
        names = [n for n in self.order if n in w]
        self.bone_index = {n: i for i, n in enumerate(self.order)}
        W = {}  # vertex → list of (bone idx, weight)
        for n in names:
            bi = self.bone_index[n]
            for vid, wt in w[n]:
                W.setdefault(vid, []).append((bi, wt))
        self.W = W

        # stylisation morphs in rest pose: bigger head, longer/shorter limbs (weights-driven scaling)
        if head_scale != 1.0:
            self._scale_region(["head", "neck03", "neck02", "jaw", "eye.L", "eye.R", "special04", "special05.L", "special05.R"] + [n for n in self.order if n.startswith(("oris", "oculi", "orbicularis", "levator", "risorius", "tongue"))], self.bones["neck02"].head, head_scale, soft="neck01")
        if slim != 1.0:
            self._slim(slim)
        if arms != 1.0:
            self._stretch([n for n in self.order if n.startswith(("upperarm", "lowerarm", "wrist", "metacarpal", "finger"))], "upperarm01", arms)
        if legs != 1.0:
            self._stretch([n for n in self.order if n.startswith(("upperleg", "lowerleg", "foot", "toe"))], "upperleg01", legs)
        self.V = self.V0

    def _stretch(self, bone_names, pivot_bone, k):
        """Lengthen a limb chain by k along its axis from the pivot joint, per side; refresh joints."""
        idx_all = {self.bone_index[n]: n for n in bone_names if n in self.bone_index}
        V = self.V0.copy()
        for side in ("L", "R"):
            pv = self.bones[f"{pivot_bone}.{side}"]
            tip = self.bones[f"wrist.{side}" if pivot_bone == "upperarm01" else f"foot.{side}"]
            axis = tip.head - pv.head
            axis /= np.linalg.norm(axis) + 1e-9
            side_idx = {bi for bi, n in idx_all.items() if n.endswith(f".{side}")}
            for vid, lst in self.W.items():
                w = sum(wt for bi, wt in lst if bi in side_idx)
                if w <= 0:
                    continue
                along = (V[vid] - pv.head) @ axis
                V[vid] += axis * along * (k - 1) * min(1.0, w * 1.5)
        self.V0 = V
        # ground again after leg changes
        body = np.unique(self.faces["body"])
        self.V0[:, 1] -= self.V0[body, 1].min()
        sk = json.load(open(ASSETS / "default.mhskel"))
        self.joint = {name: self.V0[np.asarray(ids)].mean(0) for name, ids in sk["joints"].items()}
        for name, b in sk["bones"].items():
            self.bones[name] = Bone(name, b["parent"], self.joint[b["head"]], self.joint[b["tail"]])

    def _slim(self, k):
        """Scale the body toward each limb's bone axis (torso toward the spine) by k; head, hands and feet untouched."""
        limb_bones = [n for n in self.order if n.startswith(("upperarm", "lowerarm", "upperleg", "lowerleg"))]
        torso_bones = ["spine01", "spine02", "spine03", "spine04", "spine05", "root", "pelvis.L", "pelvis.R", "clavicle.L", "clavicle.R", "breast.L", "breast.R", "shoulder01.L", "shoulder01.R", "neck01", "neck02"]
        axes = {}
        for n in limb_bones:
            b = self.bones[n]
            d = b.tail - b.head
            axes[self.bone_index[n]] = (b.head, d / (np.linalg.norm(d) + 1e-9))
        spine = (self.bones["root"].head, np.array([0, 1.0, 0]))
        for n in torso_bones:
            axes[self.bone_index[n]] = spine
        V = self.V0.copy()
        for vid, lst in self.W.items():
            shift = np.zeros(3)
            for bi, w in lst:
                if bi in axes:
                    o, d = axes[bi]
                    rel = V[vid] - o
                    perp = rel - d * (rel @ d)
                    shift += w * (k - 1) * perp
            V[vid] += shift
        self.V0 = V
        sk = json.load(open(ASSETS / "default.mhskel"))
        self.joint = {name: self.V0[np.asarray(ids)].mean(0) for name, ids in sk["joints"].items()}
        for name, b in sk["bones"].items():
            self.bones[name] = Bone(name, b["parent"], self.joint[b["head"]], self.joint[b["tail"]])

    def _topo(self):
        out, seen = [], set()
        def visit(n):
            if n in seen:
                return
            p = self.bones[n].parent
            if p:
                visit(p)
            seen.add(n)
            out.append(n)
        for n in self.bones:
            visit(n)
        return out

    def _scale_region(self, bone_names, pivot, k, soft=None):
        idx = {self.bone_index[n] for n in bone_names if n in self.bone_index}
        soft_i = self.bone_index.get(soft)
        f = np.zeros(len(self.V0))
        for vid, lst in self.W.items():
            f[vid] = sum(w for bi, w in lst if bi in idx) + 0.5 * sum(w for bi, w in lst if bi == soft_i)
        # helper meshes on the head (eyes, lashes, teeth, tongue) carry no weights: move them with the head
        for g in ("helper-l-eye", "helper-r-eye", "helper-l-eyelashes-1", "helper-r-eyelashes-1", "helper-l-eyelashes-2", "helper-r-eyelashes-2", "helper-upper-teeth", "helper-lower-teeth", "helper-tongue"):
            f[np.unique(self.groups[g])] = 1.0
        f = np.clip(f, 0, 1)[:, None]
        self.V0 = pivot + (self.V0 - pivot) * (1 + (k - 1) * f)
        # joints move with the mesh
        for name in self.joint:
            pass  # joints are recomputed from vertices below
        sk = json.load(open(ASSETS / "default.mhskel"))
        self.joint = {name: self.V0[np.asarray(ids)].mean(0) for name, ids in sk["joints"].items()}
        for name, b in sk["bones"].items():
            self.bones[name] = Bone(name, b["parent"], self.joint[b["head"]], self.joint[b["tail"]])

    # ── convenience ──
    def mesh(self, group):
        """Compact mesh for a group: only its own vertices; `metadata["vid"]` maps back to base ids."""
        F = self.faces[group]
        ids, inv = np.unique(F, return_inverse=True)
        m = trimesh.Trimesh(self.V0[ids], inv.reshape(F.shape), process=False)
        m.metadata["vid"] = ids
        return m

    def weights_matrix(self, nverts):
        """Sparse-ish weights as arrays (idx[N,4], w[N,4]) for the base vertices."""
        idx = np.zeros((nverts, 4), int)
        wt = np.zeros((nverts, 4), float)
        for vid, lst in self.W.items():
            lst = sorted(lst, key=lambda t: -t[1])[:4]
            for j, (bi, w) in enumerate(lst):
                idx[vid, j], wt[vid, j] = bi, w
        ssum = wt.sum(1, keepdims=True)
        wt = np.where(ssum > 0, wt / np.maximum(ssum, 1e-9), 0)
        return idx, wt

    def nearest_weights(self, points, restrict=None):
        """Weights for arbitrary rest-pose points, copied from the nearest body vertex."""
        body = np.unique(self.faces["body"])
        if restrict is not None:
            body = body[restrict(body)]
        tree = cKDTree(self.V0[body])
        _, near = tree.query(points)
        idx, wt = self.weights_matrix(len(self.V0))
        return idx[body[near]], wt[body[near]]

    def bone_weights(self, n, bone):
        idx = np.zeros((n, 4), int)
        wt = np.zeros((n, 4), float)
        idx[:, 0] = self.bone_index[bone]
        wt[:, 0] = 1.0
        return idx, wt

    def region(self, bones, thresh=0.5):
        """Body vertex ids mostly weighted to the given bones (helper shells such as tights/skirt excluded)."""
        if not hasattr(self, "_body_set"):
            self._body_set = set(np.unique(self.faces["body"]).tolist())
        ids = {self.bone_index[b] for b in bones}
        out = []
        for vid, lst in self.W.items():
            if vid in self._body_set and sum(w for bi, w in lst if bi in ids) >= thresh:
                out.append(vid)
        return np.asarray(sorted(out))


def rot(rx=0.0, ry=0.0, rz=0.0):
    """Rotation about world axes (deg), applied X then Y then Z."""
    m = np.eye(4)
    for ang, axis in ((rx, 0), (ry, 1), (rz, 2)):
        if ang:
            m = trimesh.transformations.rotation_matrix(np.radians(ang), np.eye(3)[axis]) @ m
    return m


class Rig:
    def __init__(self, base: Base):
        self.base = base

    def pose(self, rotations: dict[str, tuple]):
        """
        rotations: bone → (rx, ry, rz) about world axes at the bone head, in the rest pose.
        Returns world matrices [nbones, 4, 4] that map rest-pose points to posed points.
        """
        B = self.base
        mats = np.tile(np.eye(4), (len(B.order), 1, 1))
        for i, n in enumerate(B.order):
            b = B.bones[n]
            parent = mats[B.bone_index[b.parent]] if b.parent else np.eye(4)
            r = rotations.get(n)
            local = np.eye(4)
            if r:
                h = b.head
                local = trimesh.transformations.translation_matrix(h) @ rot(*r) @ trimesh.transformations.translation_matrix(-h)
            mats[i] = parent @ local
        return mats


def skin(V, idx, wt, mats):
    """Linear blend skinning of rest points V[N,3] with up-to-4 (bone idx, weight) per vertex."""
    Vh = np.hstack([V, np.ones((len(V), 1))])
    out = np.zeros((len(V), 3))
    for j in range(idx.shape[1]):
        M = mats[idx[:, j]]  # [N,4,4]
        out += wt[:, j : j + 1] * np.einsum("nij,nj->ni", M, Vh)[:, :3]
    return out
