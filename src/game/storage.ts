import { inRotation, randomMapId } from "./data/maps";
import type { GameState, Stats } from "./types";

const SAVE_KEY = "tactics-arena:save:v1";
const STATS_KEY = "tactics-arena:stats:v1";

export const EMPTY_STATS: Stats = { games: 0, wins: 0, bestRound: 0, bestLevel: 0, lastGameId: null };

function read<T>(key: string): T | null {
  try {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : null;
  } catch {
    return null;
  }
}

function write(key: string, value: unknown) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // Storage may be unavailable (private mode, quota). The game keeps running in memory.
  }
}

export function loadGame(): GameState | null {
  const s = read<GameState>(SAVE_KEY);
  if (!s || typeof s.round !== "number" || !Array.isArray(s.board)) return null;
  // A save taken mid-fight resumes at the planning phase for that round.
  if (s.phase === "combat") s.phase = "planning";
  // Saves from before arenas had backgrounds, or on a map that is no longer in rotation, get one now.
  if (!inRotation(s.mapId)) s.mapId = randomMapId();
  migrateUnitIds(s);
  return s;
}

/** Units that were briefly separate roster entries and now skin an existing unit. */
const LEGACY_UNIT_IDS: Record<string, string> = { kim: "moss", kesha: "whelp", lana: "mite" };

function migrateUnitIds(s: GameState) {
  const fix = (id: string) => LEGACY_UNIT_IDS[id] ?? id;
  for (const slots of [s.board, s.bench, s.enemyBoard]) {
    slots.forEach((u, i) => {
      if (u) slots[i] = { ...u, defId: fix(u.defId) };
    });
  }
  s.shop = s.shop.map((id) => (id ? fix(id) : id));
  for (const [legacy, current] of Object.entries(LEGACY_UNIT_IDS)) {
    if (legacy in s.pool) delete s.pool[legacy];
    if (!(current in s.pool)) s.pool[current] = 0;
  }
}

export function saveGame(s: GameState) {
  write(SAVE_KEY, s);
}

// ─── Records: a tiny external store so components can subscribe with useSyncExternalStore ───

let statsCache: Stats | null = null;
const listeners = new Set<() => void>();

function setStats(next: Stats) {
  statsCache = next;
  write(STATS_KEY, next);
  listeners.forEach((l) => l());
}

export function getStats(): Stats {
  if (!statsCache) statsCache = { ...EMPTY_STATS, ...(read<Partial<Stats>>(STATS_KEY) ?? {}) };
  return statsCache;
}

export function getServerStats(): Stats {
  return EMPTY_STATS;
}

export function subscribeStats(listener: () => void) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

/** Records a finished game once; a page reload on the end screen must not double count. */
export function recordGame(s: GameState) {
  const stats = getStats();
  if (stats.lastGameId === s.gameId) return;
  setStats({
    games: stats.games + 1,
    wins: stats.wins + (s.phase === "victory" ? 1 : 0),
    bestRound: Math.max(stats.bestRound, s.round),
    bestLevel: Math.max(stats.bestLevel, s.level),
    lastGameId: s.gameId,
  });
}

export function resetStats() {
  setStats({ ...EMPTY_STATS });
}
