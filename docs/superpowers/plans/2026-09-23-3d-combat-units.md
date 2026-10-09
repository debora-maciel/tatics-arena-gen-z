# 3D Combat Units Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Kim Petras fights on the arena as a live Three.js model, turning smoothly toward her target, while every other unit and every other screen keeps the existing PNG/emoji rendering.

**Architecture:** One offscreen `WebGLRenderer` singleton renders each 3D fighter into its own small 2D `<canvas>` that sits exactly where the facing `<Image>` sits today inside `Fighter`, so every CSS transform and keyframe (stand, lunge, hit, hop, cast, die) keeps working. A `model` field on `UnitDef` opts a unit in; PNGs remain the fallback while loading, on failure, and without WebGL. An offline gltf-transform bake shrinks the 75 MB source GLB to a few MB.

**Tech Stack:** Next.js 16 (App Router, client component tree), React 19, TypeScript, Tailwind v4, `three` (GLTFLoader + MeshoptDecoder from `three/addons`), `@gltf-transform/cli` for the bake, Vitest for pure-function tests.

**Spec:** `docs/superpowers/specs/2026-09-23-3d-combat-units-design.md`

## Global Constraints

- This project is **not a git repository**. There are no commit steps; each task ends by running `npx tsc --noEmit` and `npm run lint` (and `npm test` once it exists) and confirming clean output.
- Combat only: no 3D on the planning board, bench, shop, roster or detail panel.
- `reducer.ts`, `combat.ts`, `enemy.ts`, `storage.ts` and the save format do not change.
- Baked asset: `public/units/kim-petras/model.glb`, target 2–3 MB, about 40,000 triangles, 1024 px WebP textures, meshopt-compressed.
- The source exports under `public/units/3d/` never ship: `.gitignore` gets `/public/units/3d/`.
- `three` is loaded with a dynamic `import()` inside the renderer service, never statically from a component.
- Yaw convention: 0 = facing the viewer (`front`), π = facing away (`back`), +π/2 = screen-right (`east`), −π/2 = screen-left (`west`). glTF forward is +Z.
- Renderer backing size is 256 × 256 px, transparent, antialiased.
- The character never bends with the arena: the Three.js camera is fixed and never follows the tilt toggle. Flat view = the model is not rotated at all; perspective view = only the ground leans and the existing `.stand` counter-rotation keeps the character upright, exactly like the PNGs. Do not add any tilt-dependent logic to `modelRenderer.ts` or `UnitModel.tsx`.
- Use `@/` imports for `src/` (tsconfig `paths`). Client components start with `"use client"`.
- Before writing Next.js-specific code, read `node_modules/next/dist/docs/` for anything you are unsure about (this Next version differs from training data).

## Review Focus

1. **A unit remounts mid-turn** (the hit wrapper remounts its child on every hit). The new view must start at the unit's current facing, not spin from 0. Pinned by the `YawTracker` "first set snaps" test in Task 2.
2. **A frame after a long pause** (tab hidden, then visible). The turn must not jump by the whole accumulated time. Pinned by the `YawTracker` dt clamp test in Task 2.
3. **Target dies or its uid is stale**: `targetUid` set but no living unit with that uid. Must fall back to the team default facing. Pinned by the "target not found" test in Task 2.
4. **Two copies of the same model on the board** (two Kims). Each needs its own yaw; clones must not share rotation. Manual check in Task 7 (no WebGL in Vitest).
5. **View disposed while `three` is still downloading** (fight ends or unit dies during the first load). The async init must not draw onto a canvas that is gone or call `onReady` for a dead view. Manual check in Task 7 (block the request, start a fight, skip it before it resolves; expect no console error).

---

### Task 1: Bake the model

**Files:**
- Create: `scripts/bake-model.sh`
- Create: `scripts/rotate-glb.mjs`
- Create: `public/units/kim-petras/model.glb` (generated)
- Modify: `.gitignore`
- Modify: `package.json` (devDependencies)

**Interfaces:**
- Consumes: `public/units/3d/GLB/kim-petras.glb` (75 MB source, 1,499,900 triangles).
- Produces: `public/units/kim-petras/model.glb`, which Task 4 references as `"/units/kim-petras/model.glb"`.

- [ ] **Step 1: Install the bake tooling as dev dependencies**

Run:
```bash
npm install --save-dev @gltf-transform/cli@^4 @gltf-transform/core@^4 @gltf-transform/extensions@^4
```
Expected: `package.json` devDependencies gains the three packages; `node_modules/.bin/gltf-transform` exists.

- [ ] **Step 2: Ignore the source exports**

Append to `.gitignore`:
```
# 3D source exports (75 MB+); only the baked public/units/<id>/model.glb ships
/public/units/3d/
```

- [ ] **Step 3: Write the rotate script (used only if the model faces the wrong way)**

Create `scripts/rotate-glb.mjs`:
```js
// Rotates every root node of a glTF scene about the Y axis. Usage: node scripts/rotate-glb.mjs in.glb out.glb <degrees>
import { NodeIO } from "@gltf-transform/core";
import { ALL_EXTENSIONS } from "@gltf-transform/extensions";

const [input, output, degrees] = process.argv.slice(2);
if (!input || !output || degrees === undefined) {
  console.error("usage: node scripts/rotate-glb.mjs in.glb out.glb <degrees>");
  process.exit(1);
}
const half = (Number(degrees) * Math.PI) / 360;
const io = new NodeIO().registerExtensions(ALL_EXTENSIONS);
const doc = await io.read(input);
for (const scene of doc.getRoot().listScenes()) {
  for (const node of scene.listChildren()) {
    // Quaternion for a rotation of `degrees` about +Y, composed before the node's own rotation.
    const [x, y, z, w] = node.getRotation();
    const s = Math.sin(half), c = Math.cos(half);
    // q = (0, s, 0, c) * (x, y, z, w)
    node.setRotation([
      c * x + s * z,
      c * y + s * w,
      c * z - s * x,
      c * w - s * y,
    ]);
  }
}
await io.write(output, doc);
console.log(`rotated ${input} by ${degrees}° → ${output}`);
```

- [ ] **Step 4: Write the bake script**

Create `scripts/bake-model.sh`:
```bash
#!/usr/bin/env bash
# Bakes a high-poly source GLB into a small web asset.
# Usage: scripts/bake-model.sh <source.glb> <output.glb> [yaw-degrees]
#   yaw-degrees: optional rotation about Y applied first, for exports that do not face +Z.
set -euo pipefail

SRC="${1:?source.glb}"
OUT="${2:?output.glb}"
YAW="${3:-0}"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

GT="npx --no-install gltf-transform"
STAGE="$SRC"

if [ "$YAW" != "0" ]; then
  node scripts/rotate-glb.mjs "$STAGE" "$TMP/0-rotated.glb" "$YAW"
  STAGE="$TMP/0-rotated.glb"
fi

# ~1.5M → ~40k triangles. The normal map keeps the surface detail; the sprite is ~120 CSS px tall.
$GT simplify "$STAGE" "$TMP/1-simplified.glb" --ratio 0.027 --error 0.001
$GT resize "$TMP/1-simplified.glb" "$TMP/2-resized.glb" --width 1024 --height 1024
$GT webp "$TMP/2-resized.glb" "$TMP/3-webp.glb" --quality 85
$GT prune "$TMP/3-webp.glb" "$TMP/4-pruned.glb"
$GT meshopt "$TMP/4-pruned.glb" "$OUT" --level medium

mkdir -p "$(dirname "$OUT")"
$GT inspect "$OUT" | sed -n '1,60p'
ls -la "$OUT"
```
Then: `chmod +x scripts/bake-model.sh`.

- [ ] **Step 5: Run the bake**

Run:
```bash
scripts/bake-model.sh public/units/3d/GLB/kim-petras.glb public/units/kim-petras/model.glb
```
Expected: the `inspect` output shows one mesh of roughly 40,000 triangles (35k–45k is fine), textures at 1024 × 1024 `image/webp`, extensions including `EXT_meshopt_compression` and `EXT_texture_webp`; `ls -la` shows a file between about 1.5 MB and 4 MB. If the file is over 5 MB, lower `--quality` to 75 and re-run.

- [ ] **Step 6: Verify the output loads structurally**

Run:
```bash
python3 - <<'PY'
import struct, json
p='public/units/kim-petras/model.glb'
with open(p,'rb') as f:
    magic,ver,length=struct.unpack('<III',f.read(12)); clen,ctype=struct.unpack('<II',f.read(8)); js=json.loads(f.read(clen))
print('bytes',length,'ext',js.get('extensionsUsed'),'required',js.get('extensionsRequired'))
print('images',[(i.get('mimeType'), js['bufferViews'][i['bufferView']]['byteLength']) for i in js['images']])
print('materials',[(m.get('name'), 'pbrMetallicRoughness' in m, 'normalTexture' in m) for m in js['materials']])
PY
```
Expected: `EXT_meshopt_compression` in `required`, all images `image/webp`, one material with both `pbrMetallicRoughness` and `normalTexture` true.

- [ ] **Step 7: Verify nothing else changed**

Run: `npx tsc --noEmit && npm run lint`
Expected: both clean (the new files are `.sh`/`.mjs` outside `src`; ESLint's Next config only lints the project files it already did).

---

### Task 2: Pure facing math with tests

**Files:**
- Create: `vitest.config.ts`
- Create: `src/game/facing.ts`
- Create: `src/game/facing.test.ts`
- Modify: `package.json` (scripts, devDependencies)

**Interfaces:**
- Consumes: `CombatUnit` type from `src/game/combat.ts` (fields used: `uid`, `team`, `x`, `y`, `targetUid`).
- Produces (used by Tasks 3, 5, 6):
  - `type Facing = "front" | "back" | "east" | "west"`
  - `facing(u: CombatUnit, units: CombatUnit[]): Facing` (moved verbatim from `Arena.tsx`)
  - `facingYaw(u: CombatUnit, units: CombatUnit[]): number`
  - `frameModel(box: Box): { scale: number; offset: [number, number, number] }` where `type Box = { min: [number, number, number]; max: [number, number, number] }`
  - `normalizeAngle(a: number): number` → result in `(-π, π]`
  - `class YawTracker { current: number; target: number; set(target: number): void; step(dtSeconds: number): number }` with `YAW_SPEED = 10` rad/s and `MAX_DT = 0.1` s.

- [ ] **Step 1: Install Vitest and add the script**

Run:
```bash
npm install --save-dev vitest@^3
```
Add to `package.json` `"scripts"`: `"test": "vitest run"`.

Create `vitest.config.ts`:
```ts
import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "node",
    include: ["src/**/*.test.ts"],
  },
  resolve: {
    alias: { "@": new URL("./src", import.meta.url).pathname },
  },
});
```

- [ ] **Step 2: Write the failing tests**

Create `src/game/facing.test.ts`:
```ts
import { describe, expect, it } from "vitest";
import type { CombatUnit } from "./combat";
import { facing, facingYaw, frameModel, normalizeAngle, YawTracker, YAW_SPEED } from "./facing";

/** Minimal CombatUnit for facing tests; only position, team and target matter. */
const mk = (p: Partial<CombatUnit>): CombatUnit =>
  ({ uid: "a", team: "player", x: 3, y: 3, targetUid: null, alive: true, ...p }) as CombatUnit;

const PI = Math.PI;
const close = (a: number, b: number) => expect(a).toBeCloseTo(b, 6);

describe("facingYaw", () => {
  const me = mk({ uid: "me", x: 3, y: 3, targetUid: "t" });
  it("target below (toward the viewer) → 0", () => close(facingYaw(me, [me, mk({ uid: "t", x: 3, y: 5 })]), 0));
  it("target above → π", () => close(Math.abs(facingYaw(me, [me, mk({ uid: "t", x: 3, y: 1 })])), PI));
  it("target to the right → +π/2", () => close(facingYaw(me, [me, mk({ uid: "t", x: 6, y: 3 })]), PI / 2));
  it("target to the left → −π/2", () => close(facingYaw(me, [me, mk({ uid: "t", x: 0, y: 3 })]), -PI / 2));
  it("diagonal → atan2(dx, dy)", () => close(facingYaw(me, [me, mk({ uid: "t", x: 5, y: 4 })]), Math.atan2(2, 1)));
  it("no target: player faces away (π), enemy faces viewer (0)", () => {
    close(Math.abs(facingYaw(mk({ team: "player" }), [])), PI);
    close(facingYaw(mk({ team: "enemy" }), []), 0);
  });
  it("target uid not present → same as no target", () => {
    close(Math.abs(facingYaw(mk({ team: "player", targetUid: "ghost" }), [])), PI);
  });
});

describe("facing (four-way, unchanged behaviour)", () => {
  const me = mk({ uid: "me", x: 3, y: 3, targetUid: "t" });
  it("prefers the axis with the larger distance", () => {
    expect(facing(me, [me, mk({ uid: "t", x: 5, y: 4 })])).toBe("east");
    expect(facing(me, [me, mk({ uid: "t", x: 2, y: 5 })])).toBe("front");
  });
  it("defaults by team", () => {
    expect(facing(mk({ team: "player" }), [])).toBe("back");
    expect(facing(mk({ team: "enemy" }), [])).toBe("front");
  });
});

describe("normalizeAngle", () => {
  it("wraps into (−π, π]", () => {
    close(normalizeAngle(3 * PI), PI);
    close(normalizeAngle(-3 * PI), PI);
    close(normalizeAngle(PI / 2 + 2 * PI), PI / 2);
    close(normalizeAngle(-PI / 2 - 2 * PI), -PI / 2);
  });
});

describe("YawTracker", () => {
  it("first set snaps current to target (a remounted view starts facing the right way)", () => {
    const t = new YawTracker();
    t.set(1.2);
    expect(t.current).toBe(1.2);
    expect(t.step(0.016)).toBe(1.2);
  });
  it("turns the short way round: −0.9π → +0.9π passes through π, never through 0", () => {
    const t = new YawTracker();
    t.set(-0.9 * PI);
    t.set(0.9 * PI);
    const y = t.step(0.01); // 0.1 rad step
    expect(y).toBeLessThan(-0.9 * PI + 1e-9); // moved further negative, toward −π
    expect(Math.abs(y)).toBeGreaterThan(0.9 * PI);
  });
  it("never overshoots the target", () => {
    const t = new YawTracker();
    t.set(0);
    t.set(0.05);
    close(t.step(1), 0.05);
    close(t.step(1), 0.05);
  });
  it("clamps a long frame so a hidden tab does not snap the whole way", () => {
    const t = new YawTracker();
    t.set(0);
    t.set(PI);
    const y = t.step(5);
    close(Math.abs(y), Math.min(PI, YAW_SPEED * 0.1));
  });
});

describe("frameModel", () => {
  it("centres x/z, puts feet at y=0 and scales height to 1", () => {
    const { scale, offset } = frameModel({ min: [1, 2, -3], max: [3, 4, -1] });
    close(scale, 0.5);
    close(offset[0], -1); // centre x = 2 → −2 × 0.5
    close(offset[1], -1); // min y = 2 → −2 × 0.5
    close(offset[2], 1); // centre z = −2 → 2 × 0.5
  });
  it("does not divide by zero on a flat box", () => {
    const { scale } = frameModel({ min: [0, 0, 0], max: [1, 0, 1] });
    expect(scale).toBe(1);
  });
});
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `npm test`
Expected: FAIL — `Cannot find module './facing'` (or equivalent resolution error).

- [ ] **Step 4: Implement `src/game/facing.ts`**

```ts
import type { CombatUnit } from "./combat";

/** Screen-space direction a unit faces; matches the four directional renders. */
export type Facing = "front" | "back" | "east" | "west";

function target(u: CombatUnit, units: CombatUnit[]): CombatUnit | undefined {
  return u.targetUid ? units.find((x) => x.uid === u.targetUid) : undefined;
}

/** Four-way facing: face the current target; with no target, face the enemy side. */
export function facing(u: CombatUnit, units: CombatUnit[]): Facing {
  const t = target(u, units);
  if (t) {
    const dx = t.x - u.x;
    const dy = t.y - u.y;
    if (Math.abs(dx) > Math.abs(dy)) return dx > 0 ? "east" : "west";
    if (dy !== 0) return dy < 0 ? "back" : "front";
  }
  return u.team === "player" ? "back" : "front";
}

/**
 * Continuous facing for 3D models, as a rotation about the unit's own up axis.
 * 0 faces the viewer (down-screen, +y), π faces away, +π/2 screen-right, −π/2 screen-left.
 */
export function facingYaw(u: CombatUnit, units: CombatUnit[]): number {
  const t = target(u, units);
  if (t && (t.x !== u.x || t.y !== u.y)) return Math.atan2(t.x - u.x, t.y - u.y);
  return u.team === "player" ? Math.PI : 0;
}

/** Wraps an angle into (−π, π]. */
export function normalizeAngle(a: number): number {
  const TAU = 2 * Math.PI;
  let r = a % TAU;
  if (r <= -Math.PI) r += TAU;
  else if (r > Math.PI) r -= TAU;
  return r;
}

/** Turn speed in radians per second. */
export const YAW_SPEED = 10;
/** Longest frame the tracker will integrate; a hidden tab must not turn the unit all at once. */
export const MAX_DT = 0.1;

/** Eases a yaw toward a target along the shortest arc. The first `set` snaps, so a fresh view never spins in from 0. */
export class YawTracker {
  current = 0;
  target = 0;
  private started = false;

  set(target: number) {
    this.target = normalizeAngle(target);
    if (!this.started) {
      this.current = this.target;
      this.started = true;
    }
  }

  /** Advances by `dtSeconds` and returns the new current yaw. */
  step(dtSeconds: number): number {
    const delta = normalizeAngle(this.target - this.current);
    const max = YAW_SPEED * Math.min(Math.max(dtSeconds, 0), MAX_DT);
    const move = Math.max(-max, Math.min(max, delta));
    this.current = normalizeAngle(this.current + move);
    return this.current;
  }
}

export type Box = { min: [number, number, number]; max: [number, number, number] };

/**
 * Scale and translation that centre a bounding box on x/z, put its bottom at y = 0
 * and make it one unit tall. Apply as `group.scale = scale; group.position = offset`.
 */
export function frameModel(box: Box): { scale: number; offset: [number, number, number] } {
  const height = box.max[1] - box.min[1];
  const scale = height > 0 ? 1 / height : 1;
  const cx = (box.min[0] + box.max[0]) / 2;
  const cz = (box.min[2] + box.max[2]) / 2;
  return { scale, offset: [-cx * scale, -box.min[1] * scale, -cz * scale] };
}
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `npm test`
Expected: all tests in `src/game/facing.test.ts` PASS.

- [ ] **Step 6: Verify types and lint**

Run: `npx tsc --noEmit && npm run lint`
Expected: clean. If ESLint complains about the test file, it is because `vitest` globals are not used (they are imported explicitly, so it should not).

---

### Task 3: Renderer service

**Files:**
- Create: `src/three/modelRenderer.ts`
- Modify: `package.json` (dependencies)

**Interfaces:**
- Consumes: `frameModel`, `YawTracker` from `@/game/facing`.
- Produces (used by Tasks 5 and 6):
  - `createView(url: string, canvas: HTMLCanvasElement, onReady: () => void): ViewHandle`
  - `interface ViewHandle { setYaw(yaw: number): void; dispose(): void }`
  - `preloadModel(url: string): void`
  - `SIZE = 256`

- [ ] **Step 1: Install three**

Run:
```bash
npm install three && npm install --save-dev @types/three
```
Expected: `three` in dependencies, `@types/three` in devDependencies. Note the installed `three` version in the task report.

- [ ] **Step 2: Write the service**

Create `src/three/modelRenderer.ts`:
```ts
/**
 * Draws GLB models onto small per-unit 2D canvases from one shared offscreen WebGL renderer.
 * `three` is imported lazily, so a game with no 3D unit on the arena never downloads it.
 * Callers get a ViewHandle; the loop runs only while views exist and the tab is visible.
 */
import { frameModel, YawTracker } from "@/game/facing";
import type * as THREE from "three";

/** Backing resolution of every view canvas; matches the 256 px PNG renders. */
export const SIZE = 256;

export interface ViewHandle {
  setYaw(yaw: number): void;
  dispose(): void;
}

type ThreeMod = typeof import("three");

interface Engine {
  T: ThreeMod;
  renderer: THREE.WebGLRenderer;
  scene: THREE.Scene;
  camera: THREE.PerspectiveCamera;
  loader: import("three/addons/loaders/GLTFLoader.js").GLTFLoader;
}

interface View {
  url: string;
  canvas: HTMLCanvasElement;
  ctx: CanvasRenderingContext2D | null;
  yaw: YawTracker;
  onReady: (() => void) | null;
  /** The clone placed in the scene once its template is loaded. */
  object: THREE.Group | null;
  live: boolean;
}

let enginePromise: Promise<Engine | null> | null = null;
let engine: Engine | null = null;
/** Model templates by URL: a pending promise while loading, and the resolved group once ready. */
const templates = new Map<string, Promise<THREE.Group>>();
const resolved = new Map<string, THREE.Group>();
const views = new Set<View>();
let raf = 0;
let lastFrame = 0;

async function initEngine(): Promise<Engine | null> {
  try {
    const T = await import("three");
    const { GLTFLoader } = await import("three/addons/loaders/GLTFLoader.js");
    const { MeshoptDecoder } = await import("three/addons/libs/meshopt_decoder.module.js");

    const canvas = document.createElement("canvas");
    canvas.width = SIZE;
    canvas.height = SIZE;
    const renderer = new T.WebGLRenderer({ canvas, alpha: true, antialias: true });
    renderer.setPixelRatio(1);
    renderer.setSize(SIZE, SIZE, false);
    renderer.setClearColor(0x000000, 0);
    renderer.outputColorSpace = T.SRGBColorSpace;

    const scene = new T.Scene();
    scene.add(new T.HemisphereLight(0xffffff, 0x3a4658, 1.4));
    const key = new T.DirectionalLight(0xffffff, 1.8);
    key.position.set(-1.2, 2.2, 2.4);
    scene.add(key);

    // Slightly above the front, framed so a 1-unit-tall model fills ~90% of the canvas with feet near the bottom.
    const camera = new T.PerspectiveCamera(28, 1, 0.1, 20);
    camera.position.set(0, 0.8, 2.35);
    camera.lookAt(0, 0.5, 0);

    const loader = new GLTFLoader();
    loader.setMeshoptDecoder(MeshoptDecoder);

    return { T, renderer, scene, camera, loader };
  } catch (err) {
    console.warn("3D units disabled:", err);
    return null;
  }
}

function ensureEngine(): Promise<Engine | null> {
  if (!enginePromise) {
    enginePromise = initEngine().then((e) => {
      engine = e;
      return e;
    });
  }
  return enginePromise;
}

/** Loads and normalises a model once per URL. A failed load stays failed until the page reloads. */
function loadModel(url: string): Promise<THREE.Group> {
  let p = templates.get(url);
  if (!p) {
    p = ensureEngine().then(async (e) => {
      if (!e) throw new Error("WebGL unavailable");
      const gltf = await e.loader.loadAsync(url);
      const inner = gltf.scene;
      const box = new e.T.Box3().setFromObject(inner);
      const { scale, offset } = frameModel({
        min: [box.min.x, box.min.y, box.min.z],
        max: [box.max.x, box.max.y, box.max.z],
      });
      inner.scale.setScalar(scale);
      inner.position.set(...offset);
      // The outer group rotates about the model's own centre line; the inner group holds the normalisation.
      const outer = new e.T.Group();
      outer.add(inner);
      resolved.set(url, outer);
      return outer;
    });
    templates.set(url, p);
    p.catch((err) => console.warn(`3D model failed: ${url}`, err));
  }
  return p;
}

/** Warms the cache during planning so a fight starts with its models ready. */
export function preloadModel(url: string) {
  loadModel(url).catch(() => {});
}

function attach(view: View, template: THREE.Group) {
  if (!view.live || !engine) return;
  const clone = template.clone();
  clone.visible = false;
  engine.scene.add(clone);
  view.object = clone;
  drawView(view, 0);
  view.onReady?.();
  view.onReady = null;
  startLoop();
}

function drawView(view: View, dt: number) {
  if (!engine || !view.object || !view.ctx) return;
  view.object.rotation.y = view.yaw.step(dt);
  view.object.visible = true;
  engine.renderer.render(engine.scene, engine.camera);
  view.object.visible = false;
  view.ctx.clearRect(0, 0, SIZE, SIZE);
  view.ctx.drawImage(engine.renderer.domElement, 0, 0);
}

function frame(now: number) {
  raf = 0;
  const dt = lastFrame ? (now - lastFrame) / 1000 : 0;
  lastFrame = now;
  for (const v of views) drawView(v, dt);
  if (views.size > 0 && document.visibilityState === "visible") raf = requestAnimationFrame(frame);
}

function startLoop() {
  if (raf || views.size === 0 || document.visibilityState !== "visible") return;
  lastFrame = 0;
  raf = requestAnimationFrame(frame);
}

if (typeof document !== "undefined") {
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") startLoop();
  });
}

/**
 * Registers a canvas to show `url`. Until the model is ready nothing is drawn; `onReady` fires once
 * after the first frame (synchronously if the model is already cached), never if the load fails.
 */
export function createView(url: string, canvas: HTMLCanvasElement, onReady: () => void): ViewHandle {
  canvas.width = SIZE;
  canvas.height = SIZE;
  const view: View = {
    url,
    canvas,
    ctx: canvas.getContext("2d"),
    yaw: new YawTracker(),
    onReady,
    object: null,
    live: true,
  };
  views.add(view);

  const cached = resolved.get(url);
  if (cached && engine) attach(view, cached);
  else loadModel(url).then((t) => attach(view, t)).catch(() => {});

  return {
    setYaw(yaw: number) {
      view.yaw.set(yaw);
    },
    dispose() {
      view.live = false;
      views.delete(view);
      if (view.object && engine) engine.scene.remove(view.object);
      view.object = null;
      if (views.size === 0 && raf) {
        cancelAnimationFrame(raf);
        raf = 0;
      }
    },
  };
}
```

- [ ] **Step 3: Type-check**

Run: `npx tsc --noEmit`
Expected: clean. If `three/addons/...` fails to resolve types, check `node_modules/@types/three/package.json` `exports` for the `./addons/*` entry; if it is absent in the installed version, change the two addon imports to `three/examples/jsm/loaders/GLTFLoader.js` and `three/examples/jsm/libs/meshopt_decoder.module.js` (same modules, older path).

- [ ] **Step 4: Lint**

Run: `npm run lint`
Expected: clean. If `@typescript-eslint/consistent-type-imports` or `import/no-unresolved` complain about `import type * as THREE from "three"`, keep it as a type-only import (it must never become a static value import).

---

### Task 4: `model` on `UnitDef`, set on Kim

**Files:**
- Modify: `src/game/types.ts` (inside `UnitDef`, after `splash`)
- Modify: `src/game/data/units.ts` (the `moss` / Kim Petras entry, around lines 132–144)

**Interfaces:**
- Produces: `UnitDef.model?: string` (read by Tasks 5 and 6).

- [ ] **Step 1: Add the field**

In `src/game/types.ts`, after the `splash?: string;` line inside `UnitDef`, add:
```ts
  /** Baked GLB shown as a live 3D model during combat. `art` stays as the fallback and the planning image. */
  model?: string;
```

- [ ] **Step 2: Set it on Kim**

In `src/game/data/units.ts`, wrap the existing `moss` entry so it reads:
```ts
  {
    ...def(
      "moss",
      "Kim Petras",
      "🎤",
      1,
      "Forest",
      "Support",
      { hp: 520, ad: 40, atkSpeed: 0.65, range: 3, armor: 20, mana: 80 },
      ability("heal", "Heart to Break", 3.0),
      "/units/kim-petras",
      "/units/kim-petras/photo.png",
      "/units/kim-petras/splash.png",
    ),
    model: "/units/kim-petras/model.glb",
  },
```
Nothing else in the file changes.

- [ ] **Step 3: Verify**

Run: `npx tsc --noEmit && npm run lint && npm test`
Expected: clean; existing tests still pass.

---

### Task 5: `UnitModel` component

**Files:**
- Create: `src/components/UnitModel.tsx`

**Interfaces:**
- Consumes: `createView`, `ViewHandle` from `@/three/modelRenderer`; `UnitArtFacing`, `ArtView` from `./UnitArt`; `UnitDef`.
- Produces: `UnitModel({ def, yaw, fallbackView, className?, emojiClass? })` (used by Task 6).

- [ ] **Step 1: Write the component**

Create `src/components/UnitModel.tsx`:
```tsx
"use client";

import { useEffect, useRef, useState } from "react";
import type { UnitDef } from "@/game/types";
import { createView, type ViewHandle } from "@/three/modelRenderer";
import { UnitArtFacing, type ArtView } from "./UnitArt";

interface Props {
  def: UnitDef;
  /** Continuous facing, see facingYaw. */
  yaw: number;
  /** Four-way view for the PNG shown until the model is ready (or if it never is). */
  fallbackView: ArtView;
  className?: string;
  emojiClass?: string;
}

/**
 * A live 3D billboard for units with `model`. It occupies exactly the slot the directional
 * PNG occupies, so every wrapper (stand, lunge, hit, hop, die) applies unchanged.
 * Shows the PNG until the first frame is drawn; if WebGL or the load fails, the PNG stays.
 */
export function UnitModel({ def, yaw, fallbackView, className = "h-10 w-10", emojiClass = "text-2xl" }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const handleRef = useRef<ViewHandle | null>(null);
  const yawRef = useRef(yaw);
  yawRef.current = yaw;
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !def.model) return;
    const handle = createView(def.model, canvas, () => setReady(true));
    handle.setYaw(yawRef.current);
    handleRef.current = handle;
    return () => {
      handle.dispose();
      handleRef.current = null;
    };
  }, [def.model]);

  useEffect(() => {
    handleRef.current?.setYaw(yaw);
  }, [yaw]);

  return (
    <>
      {!ready && <UnitArtFacing def={def} view={fallbackView} className={className} emojiClass={emojiClass} />}
      <canvas
        ref={canvasRef}
        aria-label={def.name}
        hidden={!ready}
        className={`pointer-events-none max-w-none select-none drop-shadow-[0_0_6px_rgba(255,255,255,0.35)] ${className}`}
      />
    </>
  );
}
```
Note: `hidden` uses the reset's `[hidden]{display:none}`; the canvas stays mounted so the ref exists before the model is ready. The first `setYaw` happens before the model loads, so the tracker snaps to the correct facing and the unit never spins in from 0.

- [ ] **Step 2: Verify**

Run: `npx tsc --noEmit && npm run lint`
Expected: clean.

---

### Task 6: Wire `Fighter` and preload

**Files:**
- Modify: `src/components/Arena.tsx` (imports; remove local `facing`; `Fighter`)
- Modify: `src/components/Game.tsx` (imports; add a preload effect after the tick-loop effect, around line 92)

**Interfaces:**
- Consumes: `facing`, `facingYaw` from `@/game/facing`; `UnitModel` from `./UnitModel`; `preloadModel` from `@/three/modelRenderer`.

- [ ] **Step 1: Move `facing` out of `Arena.tsx`**

In `src/components/Arena.tsx`:
- Delete the local `facing` function (the block starting `/** Face the current target; with no target, face the enemy side. */`).
- Add the import `import { facing, facingYaw } from "@/game/facing";`.
- Add the import `import { UnitModel } from "./UnitModel";`.
- `LUNGE` is keyed by `ArtView`; it stays as is (a `Facing` is assignable to `ArtView`).

- [ ] **Step 2: Swap the art slot in `Fighter`**

In `Fighter`, after `const view = facing(u, units);` add `const yaw = facingYaw(u, units);`. Replace the single `<UnitArtFacing ... />` element with:
```tsx
                {def.model ? (
                  <UnitModel def={def} yaw={yaw} fallbackView={view} className="h-24 w-24 sm:h-[7.5rem] sm:w-[7.5rem]" emojiClass="text-2xl sm:text-3xl" />
                ) : (
                  <UnitArtFacing def={def} view={view} className={def.art ? "h-24 w-24 sm:h-[7.5rem] sm:w-[7.5rem]" : "h-11 w-11 sm:h-14 sm:w-14"} emojiClass="text-2xl sm:text-3xl" />
                )}
```
Every wrapper around it is untouched.

- [ ] **Step 3: Preload during planning**

In `src/components/Game.tsx`, add `import { preloadModel } from "@/three/modelRenderer";` and, after the tick-loop `useEffect` (the one that ends with `return () => clearInterval(id);`), add:
```tsx
  // Warm the 3D model cache while planning, so a fight starts with every model on either board ready.
  useEffect(() => {
    if (state.phase !== "planning") return;
    for (const slot of [...state.board, ...state.enemyBoard]) {
      const model = slot && UNIT_BY_ID[slot.defId]?.model;
      if (model) preloadModel(model);
    }
  }, [state.phase, state.board, state.enemyBoard]);
```
`UNIT_BY_ID` is already imported in `Game.tsx`.

- [ ] **Step 4: Verify**

Run: `npx tsc --noEmit && npm run lint && npm test && npm run build`
Expected: all clean. The build output should show `three` in a separate chunk (it is only reached through `import()`), not in the main page chunk.

---

### Task 7: Browser verification and docs

**Files:**
- Modify: `CLAUDE.md` (Architecture bullet list; Skills section untouched)
- Possibly modify: `scripts/bake-model.sh` invocation (yaw) and re-generate `public/units/kim-petras/model.glb`
- Possibly tune: camera constants in `src/three/modelRenderer.ts`

- [ ] **Step 1: Start the app**

Run: `npm run dev` (background) and open `http://localhost:3000` in Chrome. If a save exists, start a new game from the UI so the board is empty.

- [ ] **Step 2: Get Kim on the board**

Reroll until "Kim Petras" appears in the shop (1-cost, Forest/Support, 🎤), buy her, and place her on the front row. Confirm the planning board still shows her PNG (no canvas during planning).

- [ ] **Step 3: Orientation and framing**

Start the fight. Within a second Kim should switch from PNG to the live model. Check:
- With no target she faces away (up-screen, you see her back). If you see her face or a side, the export does not face +Z: re-run the bake with a yaw argument, e.g. `scripts/bake-model.sh public/units/3d/GLB/kim-petras.glb public/units/kim-petras/model.glb 180` (try 90 or −90 for a side), reload, and re-check.
- Her feet sit near the bottom of the slot, like the PNG units beside her, and she is about the same height. If not, adjust `camera.position` / `camera.lookAt` in `initEngine` (raise `z` to shrink, lower `y` to look more head-on) and reload.
- She turns smoothly toward her target once combat starts, rather than snapping.
- Toggle to the flat view (button reads "▦ Flat" once flat): she stands upright, screen-facing, not viewed from above, and the arena alone went flat. Toggle back: only the ground leans; she stays upright like the PNG units next to her.

- [ ] **Step 4: Animations still apply**

Watch a full fight: lunge on attack, white flash on hit, hop on move, cast ring when her mana fills, shrink-and-fade on death, and the death linger. Toggle the tilt/flat button and repeat. Set speed ×4 and confirm no stutter.

- [ ] **Step 5: Fallbacks**

- DevTools → Network → block `model.glb`, reload, fight: Kim uses her PNGs, and the console shows only the failed request plus one `3D model failed` warning.
- Unblock. Block `*.glb` again, start a fight and immediately press the skip/finish button before the request would have resolved: no console errors (Review Focus 5).
- Two Kims: buy a second copy without merging (keep it on the bench until the fight; if two copies are fielded they must each turn independently) — with two 1★ Kims on the board, confirm each faces her own target (Review Focus 4).

- [ ] **Step 6: Performance spot-check**

Temporarily set `model: "/units/kim-petras/model.glb"` on eight other units in `units.ts`, field a full board, fight at ×1: the fight should stay smooth on a laptop. Revert those edits afterwards and confirm with `git diff`-equivalent: `grep -c model.glb src/game/data/units.ts` prints `1`.

- [ ] **Step 7: Document**

In `CLAUDE.md`, Architecture list, add after the "Unit pictures" bullet:
```
- 3D models: a unit may set `model` to a baked GLB under `public/units/<id>/`; `src/three/modelRenderer.ts` renders it onto a per-unit canvas during combat only (one shared offscreen WebGL renderer, `three` loaded on demand), and `src/components/UnitModel.tsx` shows the PNG until the first frame or on failure. Continuous facing comes from `facingYaw` in `src/game/facing.ts`. Bake sources with `scripts/bake-model.sh` (gltf-transform: simplify, 1K WebP, meshopt); raw exports live git-ignored in `public/units/3d/`.
```
And in Commands, add `npm test         # vitest (pure game math only)`.

- [ ] **Step 8: Final verification**

Run: `npx tsc --noEmit && npm run lint && npm test && npm run build`
Expected: all clean. Stop the dev server.
