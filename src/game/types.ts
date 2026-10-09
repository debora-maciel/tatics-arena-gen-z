export type Origin = "Forest" | "Ember" | "Tide" | "Storm" | "Void" | "Iron";
export type Role = "Warrior" | "Ranger" | "Mage" | "Guardian" | "Assassin" | "Support";
export type Trait = Origin | Role;
export type Cost = 1 | 2 | 3 | 4 | 5;
export type Star = 1 | 2 | 3;
export type AbilityKind = "strike" | "pierce" | "aoe" | "heal";

export interface Ability {
  kind: AbilityKind;
  name: string;
  /** Multiplier on attack damage (or on heal amount for `heal`). */
  ratio: number;
}

export interface UnitDef {
  id: string;
  name: string;
  emoji: string;
  cost: Cost;
  origin: Origin;
  role: Role;
  hp: number;
  ad: number;
  atkSpeed: number;
  range: number;
  armor: number;
  mana: number;
  ability: Ability;
  /**
   * Folder under /public holding this unit's renders: portrait, board, front, back, east, west (.png).
   * Units without art render their emoji instead.
   */
  art?: string;
  /** A single square picture for shop/bench/board thumbs (drawn round). With `art` too, the renders are used in combat. */
  photo?: string;
  /** Wide picture for the shop card background (about 3:2). Falls back to `photo`. */
  splash?: string;
  /** Baked GLB shown as a live 3D model during combat. `art` stays as the fallback and the planning image. */
  model?: string;
  /** Short clip played when the unit is placed from the bench onto the board. */
  sound?: string;
}

export interface Unit {
  uid: string;
  defId: string;
  star: Star;
}
export type Slot = Unit | null;

export type Area = "bench" | "board";
export interface Loc {
  area: Area;
  index: number;
}

export type Phase = "planning" | "combat" | "gameover" | "victory";

export interface RoundResult {
  round: number;
  won: boolean;
  damage: number;
  survivors: number;
}

export interface GameState {
  gameId: string;
  /** Arena background for this game; see data/maps.ts. */
  mapId: string;
  phase: Phase;
  round: number;
  hp: number;
  gold: number;
  level: number;
  xp: number;
  /** Positive = win streak, negative = loss streak. */
  streak: number;
  shop: (string | null)[];
  locked: boolean;
  bench: Slot[];
  /** Player half of the arena: 3 rows × 7 columns, row 0 is the front line. */
  board: Slot[];
  enemyBoard: Slot[];
  /** Remaining copies of each unit in the shared shop pool. */
  pool: Record<string, number>;
  history: boolean[];
  lastResult: RoundResult | null;
  nextUid: number;
}

export interface StatMods {
  hpPct: number;
  adPct: number;
  asPct: number;
  apPct: number;
  armor: number;
  mana: number;
  regenPct: number;
  trueDmg: number;
  crit: number;
  manaRegen: number;
}

export interface TraitDef {
  name: Trait;
  kind: "origin" | "role";
  thresholds: number[];
  description: string;
  tiers: string[];
  mods: (tier: number) => Partial<StatMods>;
}

export interface Stats {
  games: number;
  wins: number;
  bestRound: number;
  bestLevel: number;
  lastGameId: string | null;
}
