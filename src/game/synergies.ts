import { TRAITS } from "./data/traits";
import { UNIT_BY_ID } from "./data/units";
import type { Slot, StatMods, Trait, TraitDef } from "./types";

export interface ActiveTrait {
  def: TraitDef;
  count: number;
  /** 0 = not yet active, 1..n = which threshold is reached. */
  tier: number;
}

export const EMPTY_MODS: StatMods = {
  hpPct: 0, adPct: 0, asPct: 0, apPct: 0, armor: 0, mana: 0, regenPct: 0, trueDmg: 0, crit: 0, manaRegen: 0,
};

/** Trait counts for a board. Duplicates of the same unit only count once, as in TFT. */
export function computeTraits(board: Slot[]): ActiveTrait[] {
  const seen = new Set<string>();
  const counts = new Map<Trait, number>();
  for (const u of board) {
    if (!u || seen.has(u.defId)) continue;
    seen.add(u.defId);
    const d = UNIT_BY_ID[u.defId];
    for (const t of [d.origin, d.role]) counts.set(t, (counts.get(t) ?? 0) + 1);
  }
  return TRAITS.map((def) => {
    const count = counts.get(def.name) ?? 0;
    let tier = 0;
    def.thresholds.forEach((th, i) => {
      if (count >= th) tier = i + 1;
    });
    return { def, count, tier };
  })
    .filter((t) => t.count > 0)
    .sort((a, b) => b.tier - a.tier || b.count - a.count || a.def.name.localeCompare(b.def.name));
}

export function teamMods(board: Slot[]): StatMods {
  const mods: StatMods = { ...EMPTY_MODS };
  for (const t of computeTraits(board)) {
    if (t.tier === 0) continue;
    const m = t.def.mods(t.tier);
    for (const key of Object.keys(m) as (keyof StatMods)[]) mods[key] += m[key] ?? 0;
  }
  return mods;
}
