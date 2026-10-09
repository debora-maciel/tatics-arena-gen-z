import { COLS, FINAL_ROUND, SIDE_CELLS } from "./constants";
import { UNITS, UNIT_BY_ID } from "./data/units";
import type { Cost, Origin, Slot, Star, Unit, UnitDef } from "./types";

const ORIGINS: Origin[] = ["Forest", "Ember", "Tide", "Storm", "Void", "Iron"];
const FRONT_ROLES = new Set(["Warrior", "Guardian", "Assassin"]);

const rand = <T,>(arr: T[]): T => arr[Math.floor(Math.random() * arr.length)];

/** Roughly tracks the level a player reaches by that round. */
function unitCount(round: number) {
  if (round >= FINAL_ROUND) return 9;
  if (round <= 2) return 2;
  return Math.min(8, 2 + Math.floor((round + 1) / 3));
}

function maxCost(round: number): Cost {
  if (round <= 3) return 1;
  if (round <= 6) return 2;
  if (round <= 10) return 3;
  if (round <= 15) return 4;
  return 5;
}

function starFor(round: number): Star {
  if (round >= 15 && Math.random() < (round - 14) * 0.05) return 3;
  if (round >= 6 && Math.random() < Math.min(0.75, (round - 5) * 0.1)) return 2;
  return 1;
}

/** Enemy stat multiplier, on top of stars and synergies. Early "creep" rounds are gentle. */
export function enemyScale(round: number) {
  if (round <= 3) return 0.85;
  if (round >= FINAL_ROUND) return 1.08;
  return 1 + 0.025 * (round - 4);
}

/** Places units so tanks and assassins hold the front row and ranged units the back rows. */
function place(defs: { def: UnitDef; star: Star }[], nextUid: number): { board: Slot[]; nextUid: number } {
  const board: Slot[] = Array(SIDE_CELLS).fill(null);
  const front = defs.filter((d) => FRONT_ROLES.has(d.def.role) || d.def.range === 1);
  const back = defs.filter((d) => !front.includes(d));
  // Centre-out column order so small squads sit in the middle of the row.
  const order = [3, 2, 4, 1, 5, 0, 6];
  const fill = (rows: number[], units: typeof defs) => {
    let i = 0;
    for (const row of rows) {
      for (const col of order) {
        if (i >= units.length) return;
        const idx = row * COLS + col;
        if (board[idx]) continue;
        board[idx] = { uid: `e${nextUid++}`, defId: units[i].def.id, star: units[i].star };
        i++;
      }
    }
  };
  fill([0, 1], front);
  fill([2, 1, 0], back);
  return { board, nextUid };
}

export function generateEnemyBoard(round: number, nextUid: number): { board: Slot[]; nextUid: number } {
  const count = unitCount(round);
  const cap = maxCost(round);
  const theme = rand(ORIGINS);
  const picks: { def: UnitDef; star: Star }[] = [];
  const used = new Set<string>();

  if (round >= FINAL_ROUND) {
    // Boss board: strong units of one theme, all 2★, at most two legendaries.
    const pool = UNITS.filter((u) => u.cost >= 3).sort((a, b) => b.cost - a.cost);
    const themed = pool.filter((u) => u.origin === theme);
    const rest = pool.filter((u) => u.origin !== theme);
    let legendaries = 0;
    for (const def of [...themed, ...rest]) {
      if (picks.length >= count) break;
      if (def.cost === 5 && legendaries >= 2) continue;
      if (def.cost === 5) legendaries++;
      picks.push({ def, star: 2 });
    }
  } else {
    // Bias toward one origin so the AI also gets synergies.
    for (let i = 0; i < count; i++) {
      const wantTheme = Math.random() < 0.6;
      const cost = Math.max(1, Math.min(cap, Math.round(cap * (0.5 + Math.random() * 0.6)))) as Cost;
      let candidates = UNITS.filter((u) => u.cost <= cost && !used.has(u.id) && (!wantTheme || u.origin === theme));
      if (candidates.length === 0) candidates = UNITS.filter((u) => u.cost <= cost && !used.has(u.id));
      if (candidates.length === 0) candidates = UNITS.filter((u) => u.cost <= cost);
      const def = rand(candidates);
      used.add(def.id);
      picks.push({ def, star: starFor(round) });
    }
  }
  return place(picks, nextUid);
}

export function describeEnemy(board: Slot[]): string {
  const units = board.filter((u): u is Unit => !!u);
  const best = units.reduce((m, u) => Math.max(m, UNIT_BY_ID[u.defId].cost), 0);
  return `${units.length} units · up to ${best}-cost`;
}
