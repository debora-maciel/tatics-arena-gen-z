import type { CombatUnit } from "./combat";

/** Screen-space direction a unit faces; matches the four directional renders. */
export type Facing = "front" | "back" | "east" | "west";

function target(u: CombatUnit, units: CombatUnit[]): CombatUnit | undefined {
  return u.targetUid ? units.find((x) => x.uid === u.targetUid) : undefined;
}

/** Four-way facing: face the current target; with no target, face the enemy side. */
export function facing(u: CombatUnit, units: CombatUnit[]): Facing {
  const t = target(u, units);
  if (t) {
    const dx = t.x - u.x;
    const dy = t.y - u.y;
    if (Math.abs(dx) > Math.abs(dy)) return dx > 0 ? "east" : "west";
    if (dy !== 0) return dy < 0 ? "back" : "front";
  }
  return u.team === "player" ? "back" : "front";
}

/**
 * Continuous facing for 3D models, as a rotation about the unit's own up axis.
 * 0 faces the viewer (down-screen, +y), π faces away, +π/2 screen-right, −π/2 screen-left.
 */
export function facingYaw(u: CombatUnit, units: CombatUnit[]): number {
  const t = target(u, units);
  if (t && (t.x !== u.x || t.y !== u.y)) return Math.atan2(t.x - u.x, t.y - u.y);
  return u.team === "player" ? Math.PI : 0;
}

/** Wraps an angle into (−π, π]. */
export function normalizeAngle(a: number): number {
  const TAU = 2 * Math.PI;
  let r = a % TAU;
  if (r <= -Math.PI) r += TAU;
  else if (r > Math.PI) r -= TAU;
  return r;
}

/** Turn speed in radians per second. */
export const YAW_SPEED = 10;
/** Longest frame the tracker will integrate; a hidden tab must not turn the unit all at once. */
export const MAX_DT = 0.1;

/** Eases a yaw toward a target along the shortest arc. The first `set` snaps, so a fresh view never spins in from 0. */
export class YawTracker {
  current = 0;
  target = 0;
  private started = false;

  set(target: number) {
    this.target = normalizeAngle(target);
    if (!this.started) {
      this.current = this.target;
      this.started = true;
    }
  }

  /** True when there is nothing left to turn. */
  get settled(): boolean {
    return this.current === this.target;
  }

  /** Advances by `dtSeconds` and returns the new current yaw. */
  step(dtSeconds: number): number {
    const delta = normalizeAngle(this.target - this.current);
    const max = YAW_SPEED * Math.min(Math.max(dtSeconds, 0), MAX_DT);
    const move = Math.max(-max, Math.min(max, delta));
    this.current = Math.abs(move) >= Math.abs(delta) ? this.target : normalizeAngle(this.current + move);
    return this.current;
  }
}

/**
 * Trackers keyed by unit id, so a view that is torn down and rebuilt (combat wrappers remount on
 * every hit, lunge and hop) resumes its turn instead of snapping. Oldest ids are evicted past `cap`.
 */
export class TrackerPool {
  private readonly pool = new Map<string, YawTracker>();
  constructor(private readonly cap = 256) {}

  get(id: string): YawTracker {
    let t = this.pool.get(id);
    if (!t) {
      t = new YawTracker();
      this.pool.set(id, t);
      while (this.pool.size > this.cap) this.pool.delete(this.pool.keys().next().value as string);
    }
    return t;
  }
}

export type Box = { min: [number, number, number]; max: [number, number, number] };

/**
 * Scale and translation that centre a bounding box on x/z, put its bottom at y = 0
 * and make it one unit tall. Apply as `group.scale = scale; group.position = offset`.
 */
export function frameModel(box: Box): { scale: number; offset: [number, number, number] } {
  const height = box.max[1] - box.min[1];
  const scale = height > 0 ? 1 / height : 1;
  const cx = (box.min[0] + box.max[0]) / 2;
  const cz = (box.min[2] + box.max[2]) / 2;
  return { scale, offset: [-cx * scale, -box.min[1] * scale, -cz * scale] };
}
