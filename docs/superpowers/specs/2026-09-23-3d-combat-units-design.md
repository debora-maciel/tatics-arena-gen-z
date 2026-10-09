# 3D combat units (Three.js) — design

Date: 2026-09-23
Status: approved; amended during implementation (see Amendments)

## Goal

Show Kim Petras as a live 3D model on the arena during combat, driven by the existing
combat simulation, without changing how any other unit is drawn. The change must be
generic enough that any unit with a baked GLB can opt in by setting one field.

## Scope

In scope:

- An offline bake that turns the 75 MB source GLB into a few-MB web asset.
- A `model` field on `UnitDef`.
- A renderer service that draws GLB models onto small per-unit canvases.
- `Fighter` (combat only) uses the model when the unit has one; everything else falls back
  to the existing PNG/emoji path.
- Preloading models during planning.
- Unit tests for the pure math; manual browser checks for the rest.

Rule for both arena views: the character never bends with the arena. The model is a
screen-facing billboard whose Three.js camera is fixed; in the flat (top-down) view it is
not rotated at all, and in the perspective view only the ground plane leans while the
existing `.stand` counter-rotation keeps the character upright, exactly as with the PNGs.

Out of scope:

- 3D on the planning board, bench, shop, roster or detail panel (the user chose combat only).
- Rigged animation. The source model has no rig; all motion stays in CSS keyframes.
- A full-arena WebGL scene or camera matched to the CSS perspective.
- Any change to `reducer.ts`, `combat.ts`, `enemy.ts`, `storage.ts` or save format.

## 1. Asset bake

Source: `public/units/3d/GLB/kim-petras.glb` (75 MB, 1,499,900 triangles, three 4096 px PNG
textures: base colour, normal, metallic/roughness; `KHR_materials_specular`; no rig).
The OBJ export of the same model lives in `public/units/3d/OBJ/`.

Output: `public/units/kim-petras/model.glb`, target 2–3 MB.

Tool: `npx @gltf-transform/cli` (runs without adding an app dependency). Script:
`scripts/bake-model.sh <source.glb> <output.glb>`, applying in order:

1. `simplify` to roughly 40,000 triangles (ratio ≈ 0.027, error tolerance 0.001). The normal
   map carries the surface detail; the sprite is at most about 120 CSS px tall.
2. `resize` all textures to 1024 px and re-encode as WebP (`EXT_texture_webp`).
3. `meshopt` compression (`EXT_meshopt_compression`).
4. Orientation check: render one frame with the runtime camera (or inspect the bounding box
   and a known feature such as the face normal). glTF forward is +Z; if the export faces
   another way, re-run the bake with a yaw argument that rotates the root nodes before
   simplification, so the runtime never needs a per-model offset.

`.gitignore` gains `/public/units/3d/` so the source exports never ship or get committed.

## 2. Data model

`UnitDef` gains `model?: string` — path to the baked GLB under `/units/<id>/`. Only
`UnitArt`/`UnitModel` read it. Kim Petras (`moss` skin) sets
`model: "/units/kim-petras/model.glb"` and keeps `art`, `photo`, `splash` unchanged, since the
PNGs remain the fallback and the planning-phase image.

The `def()` helper in `units.ts` takes positional optionals; rather than adding a fourth,
`model` is applied with a spread after the call for the units that have one, so the other
entries do not change.

## 3. Renderer service — `src/three/modelRenderer.ts`

New dependency: `three` (runtime) and `@types/three` (dev). Imported with a dynamic
`import()` inside the service so the bundle for a game with no 3D unit on the arena never
includes it.

Singleton state:

- `renderer`: one `WebGLRenderer` on an offscreen `<canvas>` (not in the DOM), `alpha: true`,
  `antialias: true`, size 256 × 256 backing pixels, `outputColorSpace = SRGBColorSpace`,
  no tone mapping. 256 px matches the PNG renders.
- `scene`: a hemisphere light (sky/ground) and one directional key light from top-front-left,
  chosen to resemble the PNG renders. One perspective camera at a fixed spot slightly above
  the front, looking at the model's centre, framed so a normalised model fills about 90 % of
  the canvas height with its feet near the bottom edge (same framing as the `front` PNG).
- `templates: Map<url, Promise<Group>>` — the model cache.
- `views: Set<View>` — live per-unit views.

`supported: boolean` — true if a WebGL context could be created on first use. Checked lazily.

`loadModel(url): Promise<Group>`: `GLTFLoader` with `MeshoptDecoder`. After load, normalise
once: compute the bounding box, translate so the box is centred on x/z and its minimum y is
0, uniform-scale so height is 1. Cached per URL; a failed load is cached as a rejected
promise so it is not retried every frame (a page reload retries).

`createView(url, canvas, onReady): ViewHandle`:

- The handle has `setYaw(rad)` and `dispose()`. `onReady` fires once, after the first frame
  has been drawn onto `canvas`; it never fires if the load fails.
- The view holds a clone of the template (`template.clone()`, sharing geometry and materials),
  a `targetYaw`, a `currentYaw`, and the destination 2D canvas + its context.
- If the template is already resolved when the view is created, the view renders once
  synchronously so a remounted canvas (the hit wrapper remounts its child on every hit) never
  shows a blank frame.
- `dispose()` removes the view and stops the loop when none remain.

Frame loop: `requestAnimationFrame`, running only while `views.size > 0` and
`document.visibilityState === "visible"` (re-armed on `visibilitychange`). Per frame, per
view with a resolved template:

1. Ease `currentYaw` toward `targetYaw` along the shortest arc at a fixed angular speed
   (about 10 rad/s, clamped so one frame never overshoots).
2. Add the clone to the scene with `rotation.y = currentYaw`, render, remove it.
3. `ctx.clearRect` then `ctx.drawImage(rendererCanvas, 0, 0)` onto the view's canvas.

Yaw convention (matches the four PNG views): 0 = facing the viewer (`front`), π = facing away
(`back`), +π/2 = facing screen-right (`east`), −π/2 = facing screen-left (`west`). The canvas
is a billboard inside `.stand`, so a rotation about the model's own y axis is exactly the
screen facing.

## 4. Components

### `src/game/facing.ts` (pure, framework-free)

- `facingYaw(u: CombatUnit, units: CombatUnit[]): number` — continuous angle toward the
  current target: with target at (dx, dy) in grid cells, `yaw = atan2(dx, dy)` (dy > 0 is
  down-screen, i.e. toward the viewer, so a target below yields 0 = front). With no target,
  player units face π (up-screen), enemy units face 0. The existing four-way `facing` in
  `Arena.tsx` moves here unchanged and stays in use for lunge offsets and the PNG fallback.
- `frameModel(box)`: given a bounding box, returns the translation and scale that centre it
  on x/z, put its feet at y = 0 and make it 1 unit tall. Used by `loadModel`.

### `src/components/UnitModel.tsx`

Props: `def`, `yaw`, `className`, `emojiClass`, `fallbackView: ArtView`.

- Renders a `<canvas width=256 height=256>` with the same size classes `Art` uses, plus the
  same soft `drop-shadow` glow, `pointer-events-none`, `select-none`.
- On mount: if `!supported` → render `UnitArtFacing` only. Otherwise `createView(def.model,
  canvas)`; keep a `ready` state that flips true when the view reports its first drawn frame;
  until then, and if the load fails, render `UnitArtFacing` with `fallbackView` instead of
  the canvas. On unmount `dispose()`.
- `useEffect` on `yaw` → `handle.setYaw(yaw)`.

### `Arena.tsx` — `Fighter`

In the slot that currently renders `UnitArtFacing`, render `UnitModel` when `def.model` is
set, else `UnitArtFacing`, with the same `className`/`emojiClass`. `Fighter` computes both
`view = facing(u, units)` (four-way, for lunge offsets and fallback) and
`yaw = facingYaw(u, units)`. Nothing else in `Fighter` changes: `.stand`, cast ring, bars,
lunge, idle, hit, hop, die and the death linger all wrap the canvas exactly as they wrap the
image today.

### `Game.tsx` — preload

A `useEffect` on `[state.phase, state.board, state.enemyBoard]`: while planning, for every
unit on either board whose def has `model`, call `preloadModel(url)` (a thin wrapper over
`loadModel` that swallows the rejection). The enemy board for the next round is already on
the state during planning, so the fight starts with everything cached.

## 5. Error handling and fallbacks

| Situation | Behaviour |
| --- | --- |
| No WebGL context | `supported` false → every 3D unit renders its PNGs. |
| GLB 404 or parse error | Rejected promise cached → that unit renders PNGs; other models unaffected. |
| Model still loading when combat starts | PNG until the first frame, then the canvas takes over. |
| Tab hidden | Loop pauses; resumes on visibility. Simulation is unaffected (it already runs on the wall clock). |
| `three` chunk fails to load | Same path as no WebGL. |
| Reduced motion | Yaw easing still runs (it is orientation, not decoration); CSS rules already disable the keyframes. |

## 6. Testing

Unit tests (new: Vitest as a dev dependency, `npm test`):

- `facingYaw`: target below → 0; above → π; right → +π/2; left → −π/2; diagonal → atan2;
  no target → π for player, 0 for enemy; target not found in `units` → same as no target.
- `frameModel`: an off-centre box of height 2 → scale 0.5, translation that centres x/z and
  puts min y at 0; a degenerate zero-height box does not divide by zero.
- Shortest-arc yaw easing helper: turning from −0.9π to +0.9π goes through π, not through 0;
  a step never overshoots the target.

Manual (dev server, Chrome):

- Kim on the board, start a fight: she turns toward targets smoothly, lunges, flashes on hit,
  hops on moves, shrinks and fades on death; both tilted and flat views; speed ×2.
- Block `model.glb` in DevTools → PNG fallback, no console errors beyond the failed request.
- Temporarily field nine 3D units → frame rate stays smooth; remove the change afterwards.
- `npm run build`, `npm run lint`, `npx tsc --noEmit` clean.

## 7. Files

New: `scripts/bake-model.sh`, `public/units/kim-petras/model.glb`, `src/three/modelRenderer.ts`,
`src/game/facing.ts` (+ test), `src/components/UnitModel.tsx`, `vitest.config.ts`.

Changed: `package.json` (three, @types/three, vitest, `test` script), `.gitignore`,
`src/game/types.ts`, `src/game/data/units.ts`, `src/components/Arena.tsx`,
`src/components/Game.tsx`, `CLAUDE.md`.

## Amendments (2026-09-23, during implementation)

- **Scope widened by the user:** the model also shows on the planning board and the bench
  (`UnitChip`), facing the viewer. Shop, roster and detail panel still use the portrait.
- **Camera follows the arena view:** `front` pose (about 18° above eye level) on the tilted
  arena, `board` pose (about 45° down, wider lens) on the flat arena, matching the user's
  reference of a top-down editor view. The earlier "camera never follows the tilt toggle" rule
  is withdrawn; the character still never bends with the ground.
- **Orientation:** the export faces +Z; the bake needs no rotation.
- **First frame:** `createView` takes the initial yaw and pose so a cached model's synchronous
  first frame is already correct.
- Baked asset came out at 700 KB (40,494 triangles), under the 2–3 MB target.
