import type { Trait, TraitDef } from "../types";

const pick = (tier: number, values: number[]) => values[Math.min(tier, values.length) - 1] ?? 0;

export const TRAITS: TraitDef[] = [
  {
    name: "Forest", kind: "origin", thresholds: [2, 4],
    description: "Allies regenerate health every second.",
    tiers: ["1% max HP / s", "2.5% max HP / s"],
    mods: (t) => ({ regenPct: pick(t, [1, 2.5]) }),
  },
  {
    name: "Ember", kind: "origin", thresholds: [2, 4],
    description: "Allies burn brighter: bonus attack damage and ability power.",
    tiers: ["+20% AD & AP", "+45% AD & AP"],
    mods: (t) => ({ adPct: pick(t, [20, 45]), apPct: pick(t, [20, 45]) }),
  },
  {
    name: "Tide", kind: "origin", thresholds: [2, 4],
    description: "Allies start combat with bonus mana.",
    tiers: ["+30 starting mana", "+60 starting mana"],
    mods: (t) => ({ mana: pick(t, [30, 60]) }),
  },
  {
    name: "Storm", kind: "origin", thresholds: [2, 4],
    description: "Allies attack faster.",
    tiers: ["+20% attack speed", "+45% attack speed"],
    mods: (t) => ({ asPct: pick(t, [20, 45]) }),
  },
  {
    name: "Void", kind: "origin", thresholds: [2, 4],
    description: "Ally attacks deal bonus true damage that ignores armor.",
    tiers: ["+12 true damage", "+30 true damage"],
    mods: (t) => ({ trueDmg: pick(t, [12, 30]) }),
  },
  {
    name: "Iron", kind: "origin", thresholds: [2, 4],
    description: "Allies gain armor.",
    tiers: ["+30 armor", "+70 armor"],
    mods: (t) => ({ armor: pick(t, [30, 70]) }),
  },
  {
    name: "Warrior", kind: "role", thresholds: [2, 4, 6],
    description: "Allies gain attack damage.",
    tiers: ["+15% AD", "+35% AD", "+65% AD"],
    mods: (t) => ({ adPct: pick(t, [15, 35, 65]) }),
  },
  {
    name: "Ranger", kind: "role", thresholds: [2, 4],
    description: "Allies gain attack speed.",
    tiers: ["+25% attack speed", "+60% attack speed"],
    mods: (t) => ({ asPct: pick(t, [25, 60]) }),
  },
  {
    name: "Mage", kind: "role", thresholds: [2, 4],
    description: "Abilities hit harder and heal more.",
    tiers: ["+30% AP", "+75% AP"],
    mods: (t) => ({ apPct: pick(t, [30, 75]) }),
  },
  {
    name: "Guardian", kind: "role", thresholds: [2, 4],
    description: "Allies gain maximum health.",
    tiers: ["+20% max HP", "+50% max HP"],
    mods: (t) => ({ hpPct: pick(t, [20, 50]) }),
  },
  {
    name: "Assassin", kind: "role", thresholds: [2, 4],
    description: "Assassins leap to the enemy back line. Allies gain critical strike chance (150% damage).",
    tiers: ["30% crit chance", "60% crit chance"],
    mods: (t) => ({ crit: pick(t, [30, 60]) }),
  },
  {
    name: "Support", kind: "role", thresholds: [2, 4],
    description: "Allies generate mana every second.",
    tiers: ["+8 mana / s", "+18 mana / s"],
    mods: (t) => ({ manaRegen: pick(t, [8, 18]) }),
  },
];

export const TRAIT_BY_NAME: Record<Trait, TraitDef> = Object.fromEntries(TRAITS.map((t) => [t.name, t])) as Record<Trait, TraitDef>;
