---
name: character-3d
description: Build a 3D chibi character for Tactics Arena from a design brief (hair, colours, outfit, props, accessories) and render the six in-game views (portrait, board, front, back, east, west) into public/units/<id>/. Use whenever the user asks for a new character model, a re-skin of a unit with 3D art, or changes to an existing generated character's look.
---

# 3D character builder

Turns a design brief into a TFT-style character plus the PNG views the game needs, in seconds, with no external tools.

Two engines share one spec format:

- **`base` (default)** — a real human. `assets/base.obj` is the MakeHuman base mesh (CC0: modelled face, ears, hands, feet) with its skeleton and skin weights. `figure.py` stylises the head, paints skin/lips/eyes, grows hair clumps from the scalp helper, fits garments by slicing the body, hangs accessories and props on joints, then poses everything with linear blend skinning. Every character is the same body; only hair, clothes, colours and pose change.
- **`procedural`** — `charlib.py`, primitives on a small skeleton. Used automatically for `preset: "chibi"`; pick it with `"engine": "procedural"` for mascots.

Pipeline: `spec.json → figure.py / charlib.py → render.py (numpy renderer) → public/units/<id>/`.

## Files

- `scripts/figure.py` — the base-mesh engine (see above). `POSES` are rotations per MakeHuman bone about world axes, relative to the A-pose. Garments: `top()` slices the torso, `limb_garment()` slices a bone chain, `skirt()`, `belt()`. Attachments use `rigid="<bone>"` to follow one bone or nearest-vertex weights to follow the skin.
- `scripts/basemesh.py` — loads `assets/base.obj`, `default.mhskel`, `default_weights.mhw`; `Base` (mesh, joints, weights, head-scale morph), `Rig.pose()`, `skin()`.
- `scripts/facecam.py` — close-up of the head (`--angle front|three_quarter|side`) for judging faces; writes `face_<angle>.png` next to the renders. Use it every time you touch hair, eyes, glasses or expression.
- `scripts/build.py` — CLI. `--preview` renders front + board at 384px in ~1 s for iterating; a full run exports GLB/OBJ and the six 1024px views plus 256px web copies.
- `scripts/charlib.py` — the figure. Anatomy is lathe surfaces (elliptical rings along a profile: chest, waist, hips, thigh, calf) posed on a forward-kinematics skeleton (`build_skeleton`, `POSES`), so every attachment — sleeves, trousers, boots, gauntlets, bracelets, weapons — follows its bone. Two presets (`hero` ≈5 heads, `chibi` ≈2.5) × four builds. Hair is strand clumps (`clump`) laid on a scalp cap. Cloth is lathe garments with hems, pleats, chest prints, stripes and lapels. Every part gets a painted vertex gradient (darker toward its base) via `Character.add(..., paint=)`.
- `scripts/render.py` — orthographic renderer: per-pixel smooth normals with a three-band cel ramp (cooled shadows), rim light, painted specular highlights, per-material grain (skin/hair/cloth/leather/metal, picked from the part name in `MATERIALS` / `_MAT_PREFIX`), depth-buffer ambient occlusion, vertex colours, depth-edge lines, silhouette outline, ground contact shadow, transparent background. `VIEWS` holds the camera for each view. When you add a part with a new name, make sure a prefix in `_MAT_PREFIX` catches it or it renders as cloth.
- `specs/_template.json` — every field and allowed value. `specs/liora.json` and `specs/example-ember-knight.json` are working examples.
- `.venv/` — private Python env (numpy, Pillow, trimesh). Recreate with `python3 -m venv .venv && .venv/bin/pip install numpy pillow trimesh scipy networkx` if missing.

Run everything from this folder:

```bash
cd .claude/skills/character-3d
.venv/bin/python scripts/build.py specs/<id>.json --preview   # iterate on the look
.venv/bin/python scripts/build.py specs/<id>.json             # final: models + views + web copies
```

Outputs: `public/assets/characters/<id>/` (GLB, OBJ, spec copy, full-size renders) and `public/units/<id>/` (256px `portrait/board/front/back/east/west.png`).

## Choosing proportions

- The base engine is a real body; `"head": 1.25` (default) enlarges the skull about the neck for the TFT read. 1.0 is realistic, 1.4 is cartoon.
- `"preset": "chibi"` switches to the procedural engine: big head, stubby limbs. Keep it for mascots or if the user asks for cute.
- Mixing presets on one board is fine but looks deliberate; ask if the user wants the whole roster in one style.

## Working from a reference photo

The user will often give a picture of a person or an outfit and say "make it like this". The goal is a stylised stand-in with the same read at a glance, not a likeness: same hair mass and colour, same colour blocks in the same places, the one or two accessories that define the look. Do this:

1. **Read the image and write the brief out loud** before touching the spec: hair (style, length, colour, parting), skin tone, top (type, colour, print), bottom (type, colour), belt/buckle, shoes, bag/jewellery/glasses, pose. State it back to the user in one short paragraph so they can correct it.
2. **Map to spec fields.** Hex colours from the photo, slightly more saturated than real life (cel shading flattens them). Typical mappings: polo/tee + skirt → `polo_skirt`/`tee_skirt` with `print` for a chest graphic and `buckle` for a visible belt buckle; jeans/trousers → the `*_pants` variants with `secondary` as the denim colour; sunglasses → `sunglasses` with `sunglasses_frame`; handbag → `shoulder_bag`; heels or platforms → `boots.height: "heel"`; a hand on the hip → `pose: "hand_on_hip"`.
3. **Always `hero` proportions** for a photo reference, `eye_style: "almond"`, and blush only if the reference has visible make-up.
4. Preview, compare against the photo on silhouette and colour blocks only, iterate. Do not chase the face: at board size the face is four pixels.
5. Skin as normal. If the person is a real celebrity the user named, use their name and a song/film for the ability like the photo-skin skill does.

## Workflow

1. **Get the brief.** Ask for or extract: name, vibe in one line, hair style + colour, skin tone, outfit type + 2–3 colours, boots, accessories, prop, pose, and which unit it will be (new unit or a re-skin of an existing id). If the user gives a reference image, describe its palette and silhouette back to them before building. Fill anything unspecified with sensible defaults and say what you chose.
2. **Write the spec** to `specs/<id>.json`, copying the shape of `_template.json`. `id` must be a lowercase slug; it names both output folders.
3. **Preview**, then Read `public/assets/characters/<id>/preview_front.png` and `preview_board.png`. For anything involving the face or hair also run `facecam.py` and Read `face_front.png` / `face_three_quarter.png`. Check the checklist below and iterate; a preview is ~4 s on the base engine.
4. **Full build** without `--preview`. Read `board.png` and `east.png` once to confirm framing and facing.
5. **Wire it in.** In `src/game/data/units.ts` set `art: "/units/<id>"` on the unit (or add a unit — prefer re-skinning an existing id so pools, saves and balance stay untouched). Remove any `photo`/`splash` fields on that unit; `art` takes priority for the six views. Run `npx tsc --noEmit && npm run lint`.
6. **Check in the game** on the dev server: shop card, bench, board (both Flat and 3D), and a fight, so the facing renders swap correctly.
7. Delete `preview_*.png` when done.

## Design rules (what makes it read on the board)

- **Silhouette first.** At 48 px only the outline and 2–3 colour blocks survive. Give every character one distinctive silhouette element: a hair shape, hat, cape, pauldrons or a prop. Two characters must not share the same hair + outfit combination.
- **Palette: 3 colours + 1 accent.** Primary (outfit), secondary (hair or trim), skin, and one bright accent (belt, trim, prop). Keep saturated colour for the accent; keep the primary dark or mid so the accent pops.
- **Contrast with the maps.** The arenas are green, orange-brown and purple. Avoid mid-green and mid-brown as a primary. Whites, blacks, reds, blues and golds read well on all three.
- **Origin colour language** (use as a hint, not a rule): Forest greens/browns with a bright leaf accent; Ember reds/oranges with gold; Tide teals/blues with white; Storm indigo/violet with electric yellow; Void black/purple with magenta; Iron greys with brass.
- **Cost tier feel.** 1-cost: simple outfit, no prop or a small one. 3-cost: accessory + prop. 5-cost: cape or wings, crown or halo, `pose: "ready"`, two accents.
- **Board camera is the truth.** Judge every design on `board.png` (55° from above, the TFT angle): that is what players see in a fight. Front/back/east/west only matter for the 3D tilt mode. Tall hair, hats and shoulders read well from above; details on the lower legs do not.
- **Face.** Keep eyes large and high-contrast; `almond` reads sharper/older, `round` softer/younger. Blush is optional and reads only in the portrait.
- **Hair sells the character.** Pick the style from the silhouette you want: `long`/`twintails`/`ponytail` add mass below the head, `spiky`/`mohawk` add height, `bob`/`bun`/`pixie` stay compact.

## Extending the library

New looks are branches in `charlib.py`. Conventions:

- **Attach to bones.** `self.bones["forearm_R"]` etc. are 4×4 matrices; a bone's local -Y runs down its length, +Z is forward. Place a mesh with `xf(mesh, bone @ M(x, y, z, rx, ry, rz))`. Use `self.end("thigh_L")` for a joint's far end. Never hard-code world positions for anything on a limb, or it will detach in other poses.
- **Shapes.** `lathe(rings)` for anything round (body, garments, boots), `segment(len, r0, r1, bulge)` for limb pieces along a bone, `clump(a, b, r)` for hair/horns/ears, `icosphere`/`box`/`torus` for small details. Keep meshes closed and outward-facing (`lathe` fixes winding for you).
- **Paint.** `add(name, mesh, rgba, paint=fn, gradient=True, local=verts)`; `paint(local_xyz, colors)` returns per-vertex colours, used for prints, stripes, two-tone garments. Pass `local=` the untransformed vertices when the mesh was posed with `xf`.
- **Poses** are dicts of bone → (rx, ry, rz) in `POSES`; rx negative swings a limb forward, rz outward for the right side. Add new named poses there; specs may also pass a raw dict.
- After adding, document the value in `specs/_template.json`.

Rendering knobs live in `render.py`: light direction, the cel ramp (`_smoothstep` bands), rim strength, depth-edge threshold, outline thickness (≈ size/180), the contact shadow, and `VIEWS` camera directions (the board view is 55° above the front).

## MakeHuman assets (preferred for hair, brows, later clothes)

`assets/mh/<kind>/<name>/` holds MakeHuman 1.2 proxy assets: `.mhclo` (each asset vertex = 3 base vertices + weights + offset, so it follows every morph), `.obj` with UVs, and a diffuse texture. `scripts/mhclo.py` loads one; `Figure.add_proxy()` fits it to the current base, samples vertex colours from the texture, recolours by luminance (`tint_mode="lum"`, for hair) or multiplies (`"mul"`, for clothes), drops faces whose texture alpha is below `alpha_cut` (strand cut-outs keep their silhouette without alpha blending), copies skin weights from the base, and renders two-sided.

- Hair: `"style": "mh:long01"` (also `bob02`, `ponytail01` downloaded; the pack at `http://download.tuxfamily.org/makehuman/assets/1.2/base/hair/` has `afro01 braid01 short01-04` too). Colour comes from `hair.color`; `hair.alpha_cut` trims wispy ends (0.5 default).
- Eyebrows: `face.brows` defaults to `"mh:eyebrow001"` (tinted from the hair colour); `eyebrow001-009` exist. Set `"brows": null` to get the procedural clumps.
- Clothes/shoes from the same pack (`clothes/shoes01-06`, `female_casualsuit01/02`, `female_elegantsuit01`, `male_*suit*`, `fedora01`) can be attached the same way with `tint_mode="mul"`; wire them into `build_cloth` when needed.
- Download more with `curl` from that URL (obj + mhclo + mhmat + diffuse png). License: the pack's headers say AGPLv3 (2016); the MakeHuman project states its bundled assets are CC0 from 1.1 on. Fine for this personal project; check before a commercial release.

Prefer an asset over the procedural shells whenever one exists for the style: the procedural hair below is the fallback.

## Hair (base engine, procedural fallback)

Long hair is three layers, all painted with strand bands and a soft shine band across the crown:

- **scalp** — the MakeHuman hair helper, inflated for volume (most at the crown), with the front faces cut along a rounded hairline for parted styles and a dark groove at the centre part.
- **mantle** (`hair_mantle`) — one continuous shell over the back from the crown to `length`, fitted to head and torso, hugging the back, narrowing toward a V-shaped hem. Skinned to the nearest skin so it follows the torso when the head tilts.
- **curtains** (`hair_curtains`) — one shell per side that sweeps away from the centre part over the forehead (a soft V), covers the temples, frames the face and falls in front of the shoulders; the last fifth curls inward. `bangs: false` starts them wider (no part).
- a handful of thin `clump` strands over the mantle for edge variety. Never use thick clumps for framing locks: at 48 px they read as dreadlocks.

Rules from the Kim Petras references (`public/assets/characters/kim-petras/reference/`): volume sits at the crown, not at the ends; the hairline is round and highest at the part; the shine is one broad band, never a spot highlight (hair material specular is kept low for that reason); the hem is a V from behind.

Bob / pixie / spiky / curly still use clumps; when one of them is next, give it a shell base the same way.

## Shoes

`boots.height`: `ankle` (shoe + short cuff), `knee` (shin tube + shoe), `heel` (the foot bone tilts toes-down by `heel_tilt`°, default 38, and a heel block, wedge sole, toe cap and ankle strap are attached to it; grounding then lifts the figure onto the heel). Heels only read from the side and board cameras, which is fine.

## Asset contract

Every build writes `manifest.json` next to the models, shaped like `build-rigged-game-assets`' character template: provenance (spec, engine, CC0 base), files (GLB source/main, PNG views), budget, rig (MakeHuman skeleton, +Z forward, sockets `root/hips/head/wrist.L/wrist.R/spine01/foot.L/foot.R`), equipment slots listing which GLB nodes form each layer, collision capsule. Status is `catalog-only` and `actions` is empty on purpose: the game draws PNGs, there are no animation clips, so that skill's runtime validator reports those gates as unmet. Do not fabricate clips to satisfy it; if the game ever moves to Three.js actors, add real clips and flip the status.

## Gotchas

- Base-engine attachments must be placed from joints (`self.J("wrist.L")`, `self.J("eye.R")`…) in the rest pose and given `rigid=` or nearest weights; anything placed by absolute numbers will not follow the pose.
- The MakeHuman helpers (`helper-*`) are not skinned by the weights file; eyes and lashes are moved with the head morph in `Base._scale_region` and attached `rigid="head"`.
- Credit: base mesh, rig and weights are MakeHuman (CC0, Data Collection AB / Joel Palmius / Jonas Hauquier). Keep the header comment in `assets/base.obj`.

- Meshes must be closed and outward-facing: the renderer back-face-culls. All `trimesh.creation` primitives and `frustum`/`cone` here are fine; do not use negative scale factors.
- The GLB is exported for other tools; the game only uses the PNGs.
- `portrait.png` is a square crop of the front render around the head; if a hat or halo is tall, lower `head_fraction` in `render.portrait` or accept a tighter crop.
- Rendering cost grows with triangle count: `icosphere(3, …)` is 1 280 faces, `icosphere(2, …)` 320. Use subdivision 2 for anything smaller than an eye. A hero figure is ~20–30 k tris and renders a view in about a second at 1024 px.
- The first build in a fresh environment can take ~20 s while trimesh warms its caches; later builds are a few seconds.
