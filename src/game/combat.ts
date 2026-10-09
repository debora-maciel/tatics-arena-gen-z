import { COLS, MAX_TICKS, OVERTIME_TICK, ROWS, ROWS_PER_SIDE, STAR_AD, STAR_HP, TICK_MS } from "./constants";
import { UNIT_BY_ID } from "./data/units";
import { enemyScale } from "./enemy";
import { teamMods } from "./synergies";
import type { Ability, GameState, Slot, Star, StatMods, Unit } from "./types";

export type Team = "player" | "enemy";

export interface CombatUnit {
  uid: string;
  defId: string;
  name: string;
  emoji: string;
  team: Team;
  star: Star;
  x: number;
  y: number;
  hp: number;
  maxHp: number;
  ad: number;
  atkSpeed: number;
  ap: number;
  range: number;
  armor: number;
  mana: number;
  maxMana: number;
  regen: number;
  trueDmg: number;
  crit: number;
  manaRegen: number;
  ability: Ability;
  attackT: number;
  moveT: number;
  targetUid: string | null;
  alive: boolean;
  /** Tick stamps of the last event of each kind (-1 = never); the UI keys animations on them. */
  attackedAt: number;
  hitAt: number;
  castAt: number;
  movedAt: number;
  diedAt: number;
}

export interface CombatState {
  units: CombatUnit[];
  tick: number;
  log: string[];
  winner: Team | null;
}

const cheb = (a: { x: number; y: number }, b: { x: number; y: number }) => Math.max(Math.abs(a.x - b.x), Math.abs(a.y - b.y));
const key = (x: number, y: number) => y * COLS + x;

function makeUnit(u: Unit, team: Team, x: number, y: number, mods: StatMods, scale: number): CombatUnit {
  const def = UNIT_BY_ID[u.defId];
  const starHp = Math.pow(STAR_HP, u.star - 1);
  const starAd = Math.pow(STAR_AD, u.star - 1);
  const maxHp = Math.round(def.hp * starHp * (1 + mods.hpPct / 100) * scale);
  return {
    uid: u.uid,
    defId: u.defId,
    name: def.name,
    emoji: def.emoji,
    team,
    star: u.star,
    x,
    y,
    hp: maxHp,
    maxHp,
    ad: def.ad * starAd * (1 + mods.adPct / 100) * scale,
    atkSpeed: def.atkSpeed * (1 + mods.asPct / 100),
    ap: mods.apPct / 100,
    range: def.range,
    armor: def.armor + mods.armor,
    mana: mods.mana,
    maxMana: def.mana,
    regen: (mods.regenPct / 100) * maxHp,
    trueDmg: mods.trueDmg,
    crit: mods.crit / 100,
    manaRegen: mods.manaRegen,
    ability: def.ability,
    attackT: 0,
    moveT: 0,
    targetUid: null,
    alive: true,
    attackedAt: -1,
    hitAt: -1,
    castAt: -1,
    movedAt: -1,
    diedAt: -1,
  };
}

/** Player index → grid (x, y). Player rows sit at the bottom; index row 0 is the front line. */
export function playerCell(index: number) {
  return { x: index % COLS, y: ROWS_PER_SIDE + Math.floor(index / COLS) };
}
/** Enemy index → grid (x, y). Mirrored so the enemy's front line faces the player's. */
export function enemyCell(index: number) {
  return { x: COLS - 1 - (index % COLS), y: ROWS_PER_SIDE - 1 - Math.floor(index / COLS) };
}

function leapAssassins(units: CombatUnit[]) {
  const occupied = new Set(units.map((u) => key(u.x, u.y)));
  for (const u of units) {
    if (UNIT_BY_ID[u.defId].role !== "Assassin") continue;
    const targetRow = u.team === "player" ? 0 : ROWS - 1;
    // Nearest free cell in the far row, scanning outward from the unit's column.
    for (let d = 0; d < COLS; d++) {
      for (const x of [u.x - d, u.x + d]) {
        if (x < 0 || x >= COLS) continue;
        const k = key(x, targetRow);
        if (occupied.has(k)) continue;
        occupied.delete(key(u.x, u.y));
        occupied.add(k);
        u.x = x;
        u.y = targetRow;
        d = COLS;
        break;
      }
    }
  }
}

export function setupCombat(state: GameState): CombatState {
  const pMods = teamMods(state.board);
  const eMods = teamMods(state.enemyBoard);
  const scale = enemyScale(state.round);
  const units: CombatUnit[] = [];
  const add = (slots: Slot[], team: Team, mods: StatMods, s: number, cell: (i: number) => { x: number; y: number }) => {
    slots.forEach((u, i) => {
      if (!u) return;
      const { x, y } = cell(i);
      units.push(makeUnit(u, team, x, y, mods, s));
    });
  };
  add(state.board, "player", pMods, 1, playerCell);
  add(state.enemyBoard, "enemy", eMods, scale, enemyCell);
  leapAssassins(units);
  return { units, tick: 0, log: [`Round ${state.round}: fight!`], winner: null };
}

function findTarget(u: CombatUnit, units: CombatUnit[]): CombatUnit | null {
  const current = u.targetUid ? units.find((t) => t.uid === u.targetUid) : null;
  if (current && current.alive && cheb(u, current) <= u.range) return current;
  let best: CombatUnit | null = null;
  let bestD = Infinity;
  for (const t of units) {
    if (!t.alive || t.team === u.team) continue;
    const d = cheb(u, t);
    if (d < bestD) {
      bestD = d;
      best = t;
    }
  }
  u.targetUid = best?.uid ?? null;
  return best;
}

function moveToward(u: CombatUnit, target: CombatUnit, occupied: Set<number>, tick: number) {
  let best: { x: number; y: number } | null = null;
  let bestScore = cheb(u, target) * 10 + Math.hypot(u.x - target.x, u.y - target.y);
  for (let dy = -1; dy <= 1; dy++) {
    for (let dx = -1; dx <= 1; dx++) {
      if (dx === 0 && dy === 0) continue;
      const x = u.x + dx;
      const y = u.y + dy;
      if (x < 0 || x >= COLS || y < 0 || y >= ROWS || occupied.has(key(x, y))) continue;
      const score = cheb({ x, y }, target) * 10 + Math.hypot(x - target.x, y - target.y);
      if (score < bestScore) {
        bestScore = score;
        best = { x, y };
      }
    }
  }
  if (best) {
    occupied.delete(key(u.x, u.y));
    occupied.add(key(best.x, best.y));
    u.x = best.x;
    u.y = best.y;
    u.movedAt = tick;
  }
}

function hurt(cs: CombatState, attacker: CombatUnit, target: CombatUnit, amount: number) {
  if (!target.alive) return;
  target.hp -= amount;
  target.mana += 5;
  target.hitAt = cs.tick;
  if (target.hp <= 0) {
    target.hp = 0;
    target.alive = false;
    target.diedAt = cs.tick;
    cs.log.unshift(`${attacker.emoji} ${attacker.name} defeated ${target.emoji} ${target.name}`);
  }
}

function attack(cs: CombatState, u: CombatUnit, target: CombatUnit) {
  const crit = Math.random() < u.crit ? 1.5 : 1;
  const physical = (u.ad * crit * 100) / (100 + target.armor);
  hurt(cs, u, target, physical + u.trueDmg);
  u.mana += 10;
  u.attackedAt = cs.tick;
}

function cast(cs: CombatState, u: CombatUnit, target: CombatUnit, units: CombatUnit[]) {
  u.mana = 0;
  u.castAt = cs.tick;
  const power = u.ad * u.ability.ratio * (1 + u.ap);
  const enemies = units.filter((t) => t.alive && t.team !== u.team);
  switch (u.ability.kind) {
    case "strike":
      hurt(cs, u, target, power);
      break;
    case "pierce": {
      hurt(cs, u, target, power);
      const next = enemies.filter((t) => t !== target).sort((a, b) => cheb(target, a) - cheb(target, b))[0];
      if (next) hurt(cs, u, next, power * 0.7);
      break;
    }
    case "aoe":
      for (const t of enemies) if (cheb(t, target) <= 1) hurt(cs, u, t, t === target ? power : power * 0.6);
      break;
    case "heal": {
      const allies = units.filter((t) => t.alive && t.team === u.team);
      const wounded = allies.sort((a, b) => a.hp / a.maxHp - b.hp / b.maxHp)[0] ?? u;
      // Overtime: healing is halved so stalemates between healers can't last forever.
      wounded.hp = Math.min(wounded.maxHp, wounded.hp + power * (cs.tick >= OVERTIME_TICK ? 0.5 : 1));
      break;
    }
  }
  cs.log.unshift(`${u.emoji} ${u.name} casts ${u.ability.name}`);
}

/** Advances the fight by one tick. Mutates `cs` in place and returns it. */
export function stepCombat(cs: CombatState): CombatState {
  if (cs.winner) return cs;
  cs.tick++;
  const dt = TICK_MS / 1000;
  const units = cs.units;
  const occupied = new Set(units.filter((u) => u.alive).map((u) => key(u.x, u.y)));

  // Overtime: after OVERTIME_TICK every unit bleeds a growing fraction of its max HP each second,
  // so a fight that neither side can close still ends decisively.
  const overtime = cs.tick >= OVERTIME_TICK ? (cs.tick - OVERTIME_TICK) / (MAX_TICKS - OVERTIME_TICK) : 0;
  if (cs.tick === OVERTIME_TICK) cs.log.unshift("Overtime! Healing weakens and everyone starts bleeding.");

  for (const u of units) {
    if (!u.alive) continue;
    if (u.regen) u.hp = Math.min(u.maxHp, u.hp + u.regen * dt * (overtime ? 0.5 : 1));
    if (overtime) {
      u.hp -= u.maxHp * (0.02 + 0.1 * overtime) * dt;
      if (u.hp <= 0) {
        u.hp = 0;
        u.alive = false;
        u.diedAt = cs.tick;
        cs.log.unshift(`${u.emoji} ${u.name} collapsed in overtime`);
        continue;
      }
    }
    if (u.manaRegen) u.mana += u.manaRegen * dt;

    const target = findTarget(u, units);
    if (!target) continue;

    if (cheb(u, target) <= u.range) {
      u.moveT = 0;
      u.attackT += u.atkSpeed * dt;
      while (u.attackT >= 1 && target.alive) {
        u.attackT -= 1;
        attack(cs, u, target);
      }
    } else {
      u.moveT += dt / 0.4;
      if (u.moveT >= 1) {
        u.moveT = 0;
        moveToward(u, target, occupied, cs.tick);
      }
    }
    if (u.mana >= u.maxMana && target.alive) cast(cs, u, target, units);
  }

  if (cs.log.length > 40) cs.log.length = 40;

  const pAlive = units.some((u) => u.alive && u.team === "player");
  const eAlive = units.some((u) => u.alive && u.team === "enemy");
  if (!pAlive || !eAlive) {
    cs.winner = eAlive ? "enemy" : "player";
  } else if (cs.tick >= MAX_TICKS) {
    const sum = (team: Team) => units.filter((u) => u.alive && u.team === team).reduce((s, u) => s + u.hp / u.maxHp, 0);
    cs.winner = sum("player") >= sum("enemy") ? "player" : "enemy";
    cs.log.unshift("Time! The side with more health left wins.");
  }
  if (cs.winner) cs.log.unshift(cs.winner === "player" ? "Victory!" : "Defeat.");
  return cs;
}

/** Runs the remaining fight to completion synchronously (used by the skip button). */
export function finishCombat(cs: CombatState): CombatState {
  while (!cs.winner) stepCombat(cs);
  return cs;
}
