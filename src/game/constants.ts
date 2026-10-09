import type { Cost } from "./types";

export const COLS = 7;
export const ROWS_PER_SIDE = 3;
export const ROWS = ROWS_PER_SIDE * 2;
export const SIDE_CELLS = COLS * ROWS_PER_SIDE;
export const BENCH_SIZE = 8;
export const SHOP_SIZE = 5;

export const START_GOLD = 8;
export const START_HP = 100;
export const START_LEVEL = 2;
export const MAX_LEVEL = 9;
export const FINAL_ROUND = 20;

export const REROLL_COST = 2;
export const XP_COST = 4;
export const XP_PER_BUY = 4;
export const XP_PER_ROUND = 2;
export const BASE_INCOME = 5;
export const MAX_INTEREST = 5;

/** XP needed to go from `level` to `level + 1`. */
export const XP_TO_NEXT: Record<number, number> = { 2: 2, 3: 6, 4: 10, 5: 20, 6: 36, 7: 56, 8: 80 };

export const POOL_SIZE: Record<Cost, number> = { 1: 29, 2: 22, 3: 18, 4: 12, 5: 10 };

/** Shop odds per level, as percentages for cost 1..5. */
export const SHOP_ODDS: Record<number, [number, number, number, number, number]> = {
  1: [100, 0, 0, 0, 0],
  2: [100, 0, 0, 0, 0],
  3: [75, 25, 0, 0, 0],
  4: [55, 30, 15, 0, 0],
  5: [45, 33, 20, 2, 0],
  6: [25, 40, 30, 5, 0],
  7: [19, 30, 35, 15, 1],
  8: [16, 20, 35, 25, 4],
  9: [9, 15, 30, 30, 16],
};

export const TICK_MS = 100;
/** Hard cap on a fight. Overtime kicks in before this so fights rarely reach it. */
export const MAX_TICKS = 450;
/** From this tick, healing is halved and every unit bleeds a growing share of max HP each second. */
export const OVERTIME_TICK = 300;
export const STAR_HP = 1.8;
export const STAR_AD = 1.5;

/** Tier colours: 1 red, 2 green, 3 blue, 4 gold, 5 magenta (legendary). Used for card borders and name text. */
export const COST_COLOR: Record<Cost, string> = {
  1: "border-red-500 text-red-300",
  2: "border-emerald-500 text-emerald-300",
  3: "border-sky-500 text-sky-300",
  4: "border-yellow-400 text-yellow-300",
  5: "border-fuchsia-400 text-fuchsia-300"
};

/** Name bar at the bottom of a shop card. */
export const COST_BAR: Record<Cost, string> = {
  1: "bg-red-900/90",
  2: "bg-emerald-900/90",
  3: "bg-sky-900/90",
  4: "bg-yellow-700/90",
  5: "bg-fuchsia-900/90"
};

export const COST_BG: Record<Cost, string> = {
  1: "bg-red-500",
  2: "bg-emerald-500",
  3: "bg-sky-500",
  4: "bg-yellow-400",
  5: "bg-fuchsia-500"
};
