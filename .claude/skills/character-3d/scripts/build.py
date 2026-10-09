#!/usr/bin/env python
"""
Build a character from a spec: GLB + OBJ, six renders, and the 256px web copies.

  build.py specs/liora.json            # everything
  build.py specs/liora.json --preview  # fast 384px front + board only, to iterate on a design
  build.py specs/liora.json --size 768

Outputs (relative to the repo root):
  public/assets/characters/<id>/  <id>.glb, <id>.obj, spec.json, front.png back.png east.png west.png board.png portrait.png
  public/units/<id>/              256px copies of the six views used by the game
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import trimesh
from trimesh.visual.material import PBRMaterial
from trimesh.visual import TextureVisuals

sys.path.insert(0, str(Path(__file__).parent))
from charlib import Character  # noqa: E402
from figure import Figure, FigureProps  # noqa: E402
from render import VIEWS, portrait, render  # noqa: E402

ROOT = Path(__file__).resolve().parents[4]  # repo root (…/.claude/skills/character-3d/scripts)


def export_models(parts, out: Path, cid: str):
    scene = trimesh.Scene()
    meshes = []
    for part in parts:
        name, mesh, rgba = part[0], part[1], part[2]
        m = mesh.copy()
        m.visual = TextureVisuals(material=PBRMaterial(name=name, baseColorFactor=rgba, metallicFactor=0.0, roughnessFactor=0.9))
        scene.add_geometry(m, node_name=name, geom_name=name)
        meshes.append(m)
    scene.export(out / f"{cid}.glb")
    trimesh.util.concatenate(meshes).export(out / f"{cid}.obj")


EQUIP_SLOTS = {
    "headgear": ("crown", "hood", "hat", "goggle", "halo", "horn", "cat_ear", "headband"),
    "vestment": ("top", "tee", "bodice", "tunic", "jacket", "gambeson", "chest_plate", "pauldron", "robe", "collar", "placket", "lapel", "shirt", "tie", "belt", "buckle", "skirt", "tassets", "cape", "sleeve", "cuff", "scarf", "necklace", "bag"),
    "gloves": ("gauntlet", "knuckle", "bracelet"),
    "leggings": ("pants", "kneepad", "pouch"),
    "boots": ("boot", "shoe", "sole", "strap"),
    "main-hand": ("blade", "guard", "grip", "staff", "orb", "wand", "star", "mic", "book", "spine", "guitar", "bow", "string"),
    "offhand": ("shield", "boss"),
}


def write_manifest(spec, src: Path, cid: str, engine: str, tris: int, height: float, parts):
    """Actor contract in the shape of build-rigged-game-assets' character template. The game only
    consumes the PNG views, so delivery is catalog-only; the GLB is the source/main model."""
    names = [p[0] for p in parts]
    slots = []
    for slot, prefixes in EQUIP_SLOTS.items():
        layer = [n for n in names if n.startswith(prefixes)]
        slots.append({"id": slot, "supported": bool(layer), "asset": f"{src.relative_to(ROOT)}/{cid}.glb#{slot}" if layer else None,
                      "socket": "right-hand" if slot == "main-hand" else "left-hand" if slot == "offhand" else "head" if slot == "headgear" else "skeleton",
                      "parts": layer})
    base_rig = engine == "base"
    manifest = {
        "schemaVersion": 1,
        "id": cid,
        "kind": "character",
        "status": "catalog-only",
        "provenance": {
            "pipeline": "generated",
            "source": f".claude/skills/character-3d/specs/{cid}.json",
            "engine": engine,
            "baseMesh": "MakeHuman hm08 base.obj + default rig/weights (CC0)" if base_rig else "procedural primitives",
            "referenceImage": spec.get("reference"),
        },
        "files": {
            "sourceModel": f"{src.relative_to(ROOT)}/{cid}.glb",
            "mainModel": f"{src.relative_to(ROOT)}/{cid}.glb",
            "runtimeModel": None,
            "catalogPng": f"public/units/{cid}/portrait.png",
            "views": {v: f"public/units/{cid}/{v}.png" for v in ("portrait", "board", "front", "back", "east", "west")},
        },
        "budget": {"runtimeTriangles": tris, "runtimeBytes": (src / f"{cid}.glb").stat().st_size, "materials": len(parts), "textures": 0, "skinnedMeshes": 0, "bones": 163 if base_rig else 0},
        "rig": {
            "skeletonId": "makehuman-default-v1" if base_rig else "procedural-v2",
            "rootBone": "root",
            "actorHeightUnits": round(height, 3),
            "actorHeightMeters": round(height / 3.0 * 1.72, 3),
            "upAxis": "Y",
            "forwardAxis": "+Z",
            "maxSkinInfluences": 4,
            "sockets": [
                {"role": "root", "name": "root"}, {"role": "hips", "name": "root"}, {"role": "head", "name": "head"},
                {"role": "left-hand", "name": "wrist.L"}, {"role": "right-hand", "name": "wrist.R"}, {"role": "back", "name": "spine01"},
                {"role": "left-foot", "name": "foot.L"}, {"role": "right-foot", "name": "foot.R"},
            ] if base_rig else [],
        },
        "pose": spec.get("pose", "idle"),
        "actions": [],
        "equipment": {"separateFromMainModel": True, "slots": slots + [{"id": "back-ranged", "supported": False, "asset": None, "socket": None}]},
        "collision": {"navigation": {"shape": "capsule", "radius": 0.35, "height": round(height, 2)}, "hurtboxes": [{"id": "body", "shape": "capsule", "socket": "hips"}]},
        "catalog": {"cardImage": f"public/units/{cid}/portrait.png", "inspectorRoute": None, "cardCanvasCount": 0, "inspectorCanvasCount": 0, "controls": []},
        "verification": {"focusedTests": False, "build": False, "lint": False, "fullTestsRun": False, "browserProof": False, "commit": None},
        "notes": "Static renders for a 2D board: no animation clips, so build-rigged-game-assets' runtime gates (actions, inspector) are intentionally unmet and status stays catalog-only. Each GLB node is one named part so equipment layers can be toggled by name.",
    }
    (src / "manifest.json").write_text(json.dumps(manifest, indent=2))


def tight_square(im, pad=0.03):
    """Crop to the opaque content plus padding, then pad to a square so the figure fills the game's sprite box."""
    from PIL import Image
    bbox = im.getbbox()
    if not bbox:
        return im
    x0, y0, x1, y1 = bbox
    w, h = x1 - x0, y1 - y0
    side = int(max(w, h) * (1 + 2 * pad))
    out = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    out.paste(im.crop(bbox), ((side - w) // 2, (side - h) // 2))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("spec")
    ap.add_argument("--size", type=int, default=1024)
    ap.add_argument("--preview", action="store_true", help="only front + board at 384px, no models")
    ap.add_argument("--no-web", action="store_true", help="skip the public/units copies")
    args = ap.parse_args()

    spec = json.loads(Path(args.spec).read_text())
    cid = spec["id"]
    style = spec.get("style", {})
    cel, outline = style.get("cel", True), style.get("outline", True)
    engine = spec.get("engine", "procedural" if spec.get("proportions", {}).get("preset") == "chibi" else "base")
    if engine == "base":
        fig = Figure(spec)
        parts = fig.build()
        ch = type("C", (), {"P": FigureProps(fig)})()
    else:
        ch = Character(spec)
        parts = ch.build()
    tris = sum(len(p[1].faces) for p in parts)
    height = max(p[1].bounds[1][1] for p in parts)
    # Portrait side: 1.5 head diameters for big-headed chibis, never less than 42 % of the figure (hero gets shoulders).
    portrait_side = max(1.5 * 2 * ch.P.head_r / height, 0.42)

    src = ROOT / "public" / "assets" / "characters" / cid
    src.mkdir(parents=True, exist_ok=True)

    if args.preview:
        size = 384
        for view in ("front", "board"):
            render(parts, VIEWS[view], size, height, cel, outline).save(src / f"preview_{view}.png")
        print(f"{cid}: {len(parts)} parts, {tris} tris, height {height:.2f} → {src}/preview_front.png, preview_board.png")
        return

    export_models(parts, src, cid)
    (src / "spec.json").write_text(json.dumps(spec, indent=2))
    imgs = {}
    for view, cam in VIEWS.items():
        imgs[view] = render(parts, cam, args.size, height, cel, outline)
        imgs[view].save(src / f"{view}.png")
    imgs["portrait"] = portrait(imgs["front"], portrait_side)
    imgs["portrait"].save(src / "portrait.png")

    if not args.no_web:
        web = ROOT / "public" / "units" / cid
        web.mkdir(parents=True, exist_ok=True)
        for view, im in imgs.items():
            tight_square(im, 0.06 if view == "portrait" else 0.03).resize((256, 256), resample=1).save(web / f"{view}.png")

    write_manifest(spec, src, cid, engine, tris, height, parts)
    print(f"{cid}: {len(parts)} parts, {tris} tris, height {height:.2f}")
    print(f"  models + {args.size}px renders → {src.relative_to(ROOT)}/")
    if not args.no_web:
        print(f"  web copies → public/units/{cid}/  (set art: \"/units/{cid}\" on the unit)")


if __name__ == "__main__":
    main()
