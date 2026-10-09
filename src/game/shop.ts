import { POOL_SIZE, SHOP_ODDS, SHOP_SIZE } from "./constants";
import { UNITS } from "./data/units";
import type { Cost } from "./types";

export function initialPool(): Record<string, number> {
  return Object.fromEntries(UNITS.map((u) => [u.id, POOL_SIZE[u.cost]]));
}

function rollCost(level: number): Cost {
  const odds = SHOP_ODDS[Math.min(9, Math.max(1, level))];
  let r = Math.random() * 100;
  for (let i = 0; i < odds.length; i++) {
    r -= odds[i];
    if (r < 0) return (i + 1) as Cost;
  }
  return 1;
}

function pickFromPool(pool: Record<string, number>, cost: Cost): string | null {
  const candidates = UNITS.filter((u) => u.cost === cost && (pool[u.id] ?? 0) > 0);
  const total = candidates.reduce((s, u) => s + pool[u.id], 0);
  if (total === 0) return null;
  let r = Math.random() * total;
  for (const u of candidates) {
    r -= pool[u.id];
    if (r < 0) return u.id;
  }
  return candidates[candidates.length - 1].id;
}

/** Rolls a fresh shop. Copies stay in the pool until bought. */
export function rollShop(pool: Record<string, number>, level: number): (string | null)[] {
  const shop: (string | null)[] = [];
  for (let i = 0; i < SHOP_SIZE; i++) {
    let cost = rollCost(level);
    let id = pickFromPool(pool, cost);
    // If that cost tier is sold out, walk down to cheaper tiers.
    while (id === null && cost > 1) {
      cost = (cost - 1) as Cost;
      id = pickFromPool(pool, cost);
    }
    shop.push(id);
  }
  return shop;
}
