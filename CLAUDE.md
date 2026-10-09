# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
npm run dev      # next dev — http://localhost:3000
npm run build    # next build (type-checks too)
npm run lint     # eslint (eslint-config-next core-web-vitals + typescript)
npx tsc --noEmit # type-check only
npm test         # vitest: pure game math only (src/**/*.test.ts)
``` The project is not a git repository.

## Architecture

Next.js 16 App Router, React 19, Tailwind v4 (no `tailwind.config`; the `.btn`, `.stand`, `.art-selected` helpers and the combat `animate-*` keyframes live in `src/app/globals.css`). The whole app is one client component tree under `src/components/Game.tsx`. `src/app/page.tsx` renders `GameLoader`, which imports `Game` through `next/dynamic` with `ssr: false`, so everything below it may read `localStorage` synchronously and there is no hydration step to worry about.

The game logic is framework-free and lives in `src/game/`:

- `types.ts` — `GameState`, `Unit`, `UnitDef`, `TraitDef`, `StatMods`.
- `constants.ts` — every tunable number: grid size, economy, XP curve, shop odds per level, pool sizes, star multipliers, combat tick length and the overtime/cap ticks. Also the per-cost Tailwind colour classes.
- `data/units.ts` and `data/traits.ts` — the roster and synergy definitions. Every unit has exactly one origin and one role; traits map a tier to a partial `StatMods`. Many units are "skinned" as real artists: the `id`, traits and stats stay (e.g. `sprout` is PinkPantheress) and only name/emoji/ability name/pictures change. Never rename an id for a skin; `storage.ts` has a `LEGACY_UNIT_IDS` map for ids that were briefly separate roster entries.
- Unit pictures, three optional fields on `UnitDef`: `art` (a folder under `public/units/<id>/` with `portrait`, `board`, `front`, `back`, `east`, `west` 256px PNGs; east/west = the direction the character faces), `photo` (one square image drawn as a round thumb) and `splash` (wide shop-card background). `src/components/UnitArt.tsx` is the only place that resolves these: a photo wins for the portrait view, directional renders win in combat, emoji is the fallback. Source photos/renders and build scripts live in `public/assets/characters/`.
- 3D models: a unit may set `model` to a baked GLB under `public/units/<id>/`. `src/three/modelRenderer.ts` draws it onto a per-unit `<canvas>` from one shared offscreen WebGL renderer (`three` is loaded on demand); `src/components/UnitModel.tsx` is the billboard that shows the PNG until the first frame or on failure, and is used by `Fighter` (combat, continuous facing from `facingYaw` in `src/game/facing.ts`) and `UnitChip` (planning board and bench, facing the viewer). Two camera poses: `front` on the tilted arena, `board` (45° down) on the flat one. Bake sources with `scripts/bake-model.sh <src.glb> public/units/<id>/model.glb [yaw]` (gltf-transform: ~40k tris, 1K WebP, meshopt); raw exports live git-ignored in `public/units/3d/`.
- `shop.ts` — `rollShop` draws from the shared pool by level odds; copies stay in the pool until bought, and a sold-out cost tier walks down to cheaper tiers.
- `reducer.ts` — pure `reducer(state, action)` for the planning phase: buy/sell/reroll/XP/move, three-copy merging (`mergeUnits`, prefers keeping the board copy), and `RESOLVE_COMBAT`, which applies damage, income, XP, rolls the next enemy and shop, and moves to `planning`, `gameover` or `victory`. Outside the planning phase every action except `NEW_GAME`, `LOAD` and `RESOLVE_COMBAT` is ignored.
- `combat.ts` — `setupCombat` turns both half-boards into `CombatUnit`s (stars × synergies × enemy scale, assassins leap to the far row) and `stepCombat` advances one 100 ms tick in place. From `OVERTIME_TICK` healing is halved and everyone bleeds until `MAX_TICKS`. `Game.tsx` owns the `CombatState` and the interval; the reducer never sees it.
- `enemy.ts` — AI board generation per round (unit count, max cost, star odds, one biased origin so the AI also gets synergies; round 20 is a fixed boss board) and `enemyScale`.
- `data/maps.ts` — arena backgrounds with a page palette. A map with `platform` (the floor's four corners in the square image, plus `focus`/`zoom`) is a painted perspective scene: `src/components/ProjectedArena.tsx` fills the window with it, projects the 7×6 grid onto the quad with a homography (`src/game/projection.ts`, tested) and places units as upright billboards at projected cell centres, sized per row; the bench is the row below the board and the HUD floats over the scene. A map without `platform` uses the flat/tilted grid in `Arena.tsx` (the plain `stage` fallback, out of rotation). `newGame` stores `mapId`; saves on a map out of rotation are re-rolled on load.
- `synergies.ts` — trait counting (unique units only) and `teamMods`.
- `storage.ts` — `localStorage` save (`tactics-arena:save:v1`) and records (`tactics-arena:stats:v1`). `loadGame` migrates old saves (mid-fight → that round's planning phase, missing/unknown `mapId`, legacy unit ids). Records are a tiny external store read through `useSyncExternalStore`; `recordGame` dedupes on `gameId`.

`src/hooks/useGame.ts` wraps the reducer: the initial state comes from the save (or `newGame`) in the reducer initializer, and a save is written on every non-combat state change. Persistence side effects live there, not in the reducer.

Grid conventions: the arena is 7 columns × 6 rows. Each side's board is a flat 21-slot array where index row 0 is that side's front line. `playerCell`/`enemyCell` in `combat.ts` and `cellOwner` in `Arena.tsx` are the only places that convert between slot index and grid (x, y); the enemy half is mirrored so both front lines meet in the middle.

# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` (resolved from this file's directory; in monorepos the `next` package may not be visible from the repo root) before writing any code. Heed deprecation notices.

This block is written and re-added by `next dev` — verify at `node_modules/next/dist/server/lib/generate-agent-files.js`. Removing it from a diff only re-creates the uncommitted change; committing it with your work keeps the tree clean.

## Skills

Project skills (each has its own git-ignored `.venv` under its folder):

- `.claude/skills/photo-skin/` turns a photo in `public/assets/characters/` into a unit skin: face-aware splash + thumb crops and a `units.ts` patch that re-skins an existing unit (name, emoji, ability name, pictures) without touching stats. `roster.py --unskinned` lists free slots.
- `.claude/skills/arena-map/` generates a 7×6 painted arena PNG from a theme + seed and registers it with a page palette in `maps.ts`.
- `.claude/skills/character-3d/` builds 3D characters from a JSON spec (see its `specs/`) on the MakeHuman base mesh (CC0, bundled in the skill; real face, hands, rig and skin weights), dressing and posing it procedurally, and renders the six in-game views into `public/units/<id>/`. A procedural chibi engine remains for mascots. Use it for any request to create or restyle a unit's 3D art; see its SKILL.md for the workflow and design rules.

`.claude/skills/3d/` and `.claude/skills/game-development/` are generic third-party Three.js skill bundles. This project does not use Three.js; only reach for them if a task genuinely calls for one.

<!-- BEGIN:nextjs-agent-rules -->

# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` (resolved from this file's directory; in monorepos the `next` package may not be visible from the repo root) before writing any code. Heed deprecation notices.

This block is written and re-added by `next dev` — verify at `node_modules/next/dist/server/lib/generate-agent-files.js`. Removing it from a diff only re-creates the uncommitted change; committing it with your work keeps the tree clean.

<!-- END:nextjs-agent-rules -->
