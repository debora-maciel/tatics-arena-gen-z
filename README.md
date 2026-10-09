# Tactics Arena

A small Teamfight-Tactics-style auto-battler built with Next.js (App Router), React, Tailwind CSS v4 and TypeScript. Progress and records live in `localStorage`, so there is no backend.

## Play

```bash
npm install
npm run dev     # http://localhost:3000
```

- Buy units from the shop (5 cards, odds scale with your level). Reroll for 2 gold, buy XP for 4.
- Drag or click-to-move units between the bench and your half of the board. You can field as many units as your level.
- Three copies of the same unit merge into a stronger star level (up to 3★).
- Units share an **origin** (Forest, Ember, Tide, Storm, Void, Iron) and a **role** (Warrior, Ranger, Mage, Guardian, Assassin, Support). Fielding enough different units of one trait activates a synergy.
- Each round you fight an AI board that grows stronger. Lose and you take damage per surviving enemy. Survive 20 rounds to win.
- Income each round: 5 base, +1 per 10 gold banked (max 5), plus a streak bonus.

## Unit art

Units default to an emoji. To give one real art, add a folder `public/units/<id>/` with six 256px PNGs: `portrait` (shop, bench, details), `board` (3/4 view on the planning board), and `front`, `back`, `east`, `west` (combat, chosen by the direction the unit is facing), then set `art: "/units/<id>"` on the unit in `src/game/data/units.ts`. The source renders for Liora, plus the `trimesh` script that builds her model, live in `public/assets/characters/`. A unit can instead set `photo` to a single square image, shown as a round thumbnail in every view.

## Arena maps

Each new game picks a random background from `src/game/data/maps.ts`. Maps live in `public/assets/maps/` at 1344×1152, which is one 192px tile per grid cell. To add one, drop the image there and add an entry in `maps.ts`.

## Scripts

```bash
npm run dev
npm run build
npm run start
npm run lint
```
# tatics-arena-gen-z
