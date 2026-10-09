---
name: arena-map
description: Generate a new 7×6 arena background for Tactics Arena in the painted top-down style (ground, path, pond, bushes, rocks) from a theme + seed, and register it with a matching page palette in src/game/data/maps.ts. Use when the user asks for a new map, arena, battlefield or background.
---

# Arena map generator

Every game picks a random map from `MAPS` in `src/game/data/maps.ts`. This skill adds one: a 1344×1152 PNG (one 192 px tile per grid cell) painted procedurally, plus the `palette` entry that tints the page around it.

## Files

- `scripts/mapgen.py` — generator + registrar. Ten themes with ground, foliage, rock, path, water and accent colours and a page palette each. Features: winding path, pond with stones, border and scattered bushes, rocks, accent sprinkles, soft vignette.
- `.venv/` — numpy, Pillow. Recreate with `python3 -m venv .venv && .venv/bin/pip install numpy pillow`.

```bash
cd .claude/skills/arena-map
.venv/bin/python scripts/mapgen.py --id <slug> --name "Display Name" --theme <theme> --seed <n>
```

Themes: `forest autumn darkwoods ember tide storm void iron snow desert neon`. Flags: `--bushes N --rocks N --sprinkles N --no-path --no-pond --no-register`.

Styles: `--style nature` (default, painted clearing) or `--style stage` (concert floor: LED dance tiles, neon edge strips, a raised stage across the enemy end with truss lights, speaker stacks, spotlight cones `--spots N`, confetti). Use `stage` with the `neon` theme for the pop-star roster; any theme's colours work.

## Workflow

1. **Get the brief:** a name, a mood or origin (map themes are named after the six origins plus snow, desert, forest, autumn, darkwoods), and anything specific (no water, more rocks, sparse).
2. **Generate with `--no-register`** and a seed. Read the PNG. Judge it as the board it will be: the centre rows must stay readable (props are decoration, units are drawn on top with their own outlines), the border should feel enclosed, and the palette must contrast with unit thumbs (avoid busy high-contrast speckle in the middle).
3. **Iterate** on seed and feature counts. Different seeds move everything; `--bushes 14 --rocks 3` opens the field; `--no-pond` removes water for dry themes.
4. **Register** by re-running without `--no-register` (same id/name/theme). The entry gets the theme's page palette; the id must be new.
5. Start a new game on the dev server to see it, since a map is chosen per game. Check both Flat and 3D views.

## Adding a theme

Add a key to `THEMES` in `mapgen.py`: two ground tones, three bush tones (mid, dark, highlight), two rock tones, a path, water and accent colour, and the page palette (`bg`, `glow`, `panel`) that `Game.tsx` paints behind the arena. Keep `bg` very dark and `panel` around 55 % alpha so text stays readable.

## Notes

- Maps are decorative: nothing in the game reads the image, so any 7:6 picture works. Hand-painted art can replace a generated one at the same path.
- The `_grid` variants of the original maps are unused; the arena draws its own grid.
- Keep files under ~1 MB; the generator's PNGs are about 800 KB.
