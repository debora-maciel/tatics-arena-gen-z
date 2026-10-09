import {
  BASE_INCOME, BENCH_SIZE, FINAL_ROUND, MAX_INTEREST, MAX_LEVEL, REROLL_COST, SIDE_CELLS,
  START_GOLD, START_HP, START_LEVEL, XP_COST, XP_PER_BUY, XP_PER_ROUND, XP_TO_NEXT,
} from "./constants";
import { randomMapId } from "./data/maps";
import { UNIT_BY_ID } from "./data/units";
import { generateEnemyBoard } from "./enemy";
import { initialPool, rollShop } from "./shop";
import type { GameState, Loc, RoundResult, Slot, Star, Unit } from "./types";

export type Action =
  | { type: "NEW_GAME" }
  | { type: "LOAD"; state: GameState }
  | { type: "BUY"; slot: number }
  | { type: "SELL"; loc: Loc }
  | { type: "REROLL" }
  | { type: "BUY_XP" }
  | { type: "MOVE"; from: Loc; to: Loc }
  | { type: "TOGGLE_LOCK" }
  | { type: "START_COMBAT" }
  | { type: "RESOLVE_COMBAT"; won: boolean; survivors: { star: Star }[] };

export function sellValue(u: Unit) {
  return UNIT_BY_ID[u.defId].cost * Math.pow(3, u.star - 1);
}

export function boardCount(board: Slot[]) {
  return board.filter(Boolean).length;
}

export function newGame(): GameState {
  const pool = initialPool();
  const enemy = generateEnemyBoard(1, 1);
  return {
    gameId: `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 7)}`,
    mapId: randomMapId(),
    phase: "planning",
    round: 1,
    hp: START_HP,
    gold: START_GOLD,
    level: START_LEVEL,
    xp: 0,
    streak: 0,
    shop: rollShop(pool, START_LEVEL),
    locked: false,
    bench: Array(BENCH_SIZE).fill(null),
    board: Array(SIDE_CELLS).fill(null),
    enemyBoard: enemy.board,
    pool,
    history: [],
    lastResult: null,
    nextUid: enemy.nextUid,
  };
}

const get = (s: GameState, loc: Loc) => (loc.area === "bench" ? s.bench : s.board)[loc.index];
const set = (s: GameState, loc: Loc, u: Slot) => {
  (loc.area === "bench" ? s.bench : s.board)[loc.index] = u;
};

/** Combines three identical units of the same star into one of the next star, preferring to keep the board copy. */
function mergeUnits(s: GameState) {
  for (;;) {
    const groups = new Map<string, Loc[]>();
    const scan = (area: "board" | "bench", slots: Slot[]) =>
      slots.forEach((u, index) => {
        if (!u || u.star >= 3) return;
        const k = `${u.defId}:${u.star}`;
        groups.set(k, [...(groups.get(k) ?? []), { area, index }]);
      });
    scan("board", s.board);
    scan("bench", s.bench);
    const trio = [...groups.values()].find((locs) => locs.length >= 3);
    if (!trio) return;
    const keep = get(s, trio[0])!;
    set(s, trio[0], { ...keep, star: (keep.star + 1) as Star });
    set(s, trio[1], null);
    set(s, trio[2], null);
  }
}

function copiesOwned(s: GameState, defId: string, star: Star) {
  return [...s.board, ...s.bench].filter((u) => u && u.defId === defId && u.star === star).length;
}

function addXp(s: GameState, amount: number) {
  s.xp += amount;
  while (s.level < MAX_LEVEL && s.xp >= XP_TO_NEXT[s.level]) {
    s.xp -= XP_TO_NEXT[s.level];
    s.level++;
  }
  if (s.level >= MAX_LEVEL) s.xp = 0;
}

function streakBonus(streak: number) {
  const n = Math.abs(streak);
  if (n >= 5) return 3;
  if (n >= 3) return 2;
  if (n >= 2) return 1;
  return 0;
}

function clone(s: GameState): GameState {
  return { ...s, shop: [...s.shop], bench: [...s.bench], board: [...s.board], enemyBoard: [...s.enemyBoard], pool: { ...s.pool }, history: [...s.history] };
}

export function reducer(state: GameState, action: Action): GameState {
  switch (action.type) {
    case "NEW_GAME":
      return newGame();
    case "LOAD":
      return action.state;
  }
  if (state.phase !== "planning" && action.type !== "RESOLVE_COMBAT") return state;
  const s = clone(state);

  switch (action.type) {
    case "BUY": {
      const defId = s.shop[action.slot];
      if (!defId) return state;
      const def = UNIT_BY_ID[defId];
      if (s.gold < def.cost || (s.pool[defId] ?? 0) <= 0) return state;
      let benchIdx = s.bench.findIndex((b) => b === null);
      // A full bench still allows a buy that completes a 3-of-a-kind.
      if (benchIdx === -1) {
        if (copiesOwned(s, defId, 1) < 2) return state;
        s.bench.push(null);
        benchIdx = s.bench.length - 1;
      }
      s.gold -= def.cost;
      s.pool[defId]--;
      s.shop[action.slot] = null;
      s.bench[benchIdx] = { uid: `p${s.nextUid++}`, defId, star: 1 };
      mergeUnits(s);
      if (s.bench.length > BENCH_SIZE) s.bench = s.bench.filter((b, i) => i < BENCH_SIZE || b !== null).slice(0, BENCH_SIZE);
      return s;
    }
    case "SELL": {
      const u = get(s, action.loc);
      if (!u) return state;
      s.gold += sellValue(u);
      s.pool[u.defId] = (s.pool[u.defId] ?? 0) + Math.pow(3, u.star - 1);
      set(s, action.loc, null);
      return s;
    }
    case "REROLL":
      if (s.gold < REROLL_COST) return state;
      s.gold -= REROLL_COST;
      s.shop = rollShop(s.pool, s.level);
      return s;
    case "BUY_XP":
      if (s.gold < XP_COST || s.level >= MAX_LEVEL) return state;
      s.gold -= XP_COST;
      addXp(s, XP_PER_BUY);
      return s;
    case "MOVE": {
      const { from, to } = action;
      if (from.area === to.area && from.index === to.index) return state;
      const a = get(s, from);
      const b = get(s, to);
      if (!a) return state;
      if (from.area === "bench" && to.area === "board" && !b && boardCount(s.board) >= s.level) return state;
      set(s, from, b);
      set(s, to, a);
      return s;
    }
    case "TOGGLE_LOCK":
      s.locked = !s.locked;
      return s;
    case "START_COMBAT":
      if (boardCount(s.board) === 0) return state;
      s.phase = "combat";
      return s;
    case "RESOLVE_COMBAT": {
      if (state.phase !== "combat") return state;
      const { won, survivors } = action;
      const damage = won ? 0 : 2 + Math.floor(s.round / 5) + survivors.reduce((sum, u) => sum + 1 + u.star, 0);
      const result: RoundResult = { round: s.round, won, damage, survivors: survivors.length };
      s.hp = Math.max(0, s.hp - damage);
      s.history.push(won);
      s.lastResult = result;
      s.streak = won ? (s.streak > 0 ? s.streak + 1 : 1) : s.streak < 0 ? s.streak - 1 : -1;

      if (s.hp <= 0) {
        s.phase = "gameover";
        return s;
      }
      if (won && s.round >= FINAL_ROUND) {
        s.phase = "victory";
        return s;
      }

      const interest = Math.min(MAX_INTEREST, Math.floor(s.gold / 10));
      s.gold += BASE_INCOME + interest + streakBonus(s.streak) + (won ? 1 : 0);
      addXp(s, XP_PER_ROUND);
      s.round++;
      const enemy = generateEnemyBoard(s.round, s.nextUid);
      s.enemyBoard = enemy.board;
      s.nextUid = enemy.nextUid;
      if (!s.locked) s.shop = rollShop(s.pool, s.level);
      s.phase = "planning";
      return s;
    }
  }
  return state;
}

/** Income the player will receive at the end of the current round, before the win bonus. */
export function projectedIncome(s: GameState) {
  const interest = Math.min(MAX_INTEREST, Math.floor(s.gold / 10));
  return { base: BASE_INCOME, interest, streak: streakBonus(s.streak) };
}

export function xpToNext(level: number) {
  return XP_TO_NEXT[level] ?? 0;
}
