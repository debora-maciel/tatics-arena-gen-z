import { describe, expect, it } from "vitest";
import type { CombatUnit } from "./combat";
import { facing, facingYaw, frameModel, normalizeAngle, TrackerPool, YawTracker, YAW_SPEED } from "./facing";

/** Minimal CombatUnit for facing tests; only position, team and target matter. */
const mk = (p: Partial<CombatUnit>): CombatUnit =>
  ({ uid: "a", team: "player", x: 3, y: 3, targetUid: null, alive: true, ...p }) as CombatUnit;

const PI = Math.PI;
const close = (a: number, b: number) => expect(a).toBeCloseTo(b, 6);

describe("facingYaw", () => {
  const me = mk({ uid: "me", x: 3, y: 3, targetUid: "t" });
  it("target below (toward the viewer) → 0", () => close(facingYaw(me, [me, mk({ uid: "t", x: 3, y: 5 })]), 0));
  it("target above → π", () => close(Math.abs(facingYaw(me, [me, mk({ uid: "t", x: 3, y: 1 })])), PI));
  it("target to the right → +π/2", () => close(facingYaw(me, [me, mk({ uid: "t", x: 6, y: 3 })]), PI / 2));
  it("target to the left → −π/2", () => close(facingYaw(me, [me, mk({ uid: "t", x: 0, y: 3 })]), -PI / 2));
  it("diagonal → atan2(dx, dy)", () => close(facingYaw(me, [me, mk({ uid: "t", x: 5, y: 4 })]), Math.atan2(2, 1)));
  it("no target: player faces away (π), enemy faces viewer (0)", () => {
    close(Math.abs(facingYaw(mk({ team: "player" }), [])), PI);
    close(facingYaw(mk({ team: "enemy" }), []), 0);
  });
  it("target uid not present → same as no target", () => {
    close(Math.abs(facingYaw(mk({ team: "player", targetUid: "ghost" }), [])), PI);
  });
});

describe("facing (four-way, unchanged behaviour)", () => {
  const me = mk({ uid: "me", x: 3, y: 3, targetUid: "t" });
  it("prefers the axis with the larger distance", () => {
    expect(facing(me, [me, mk({ uid: "t", x: 5, y: 4 })])).toBe("east");
    expect(facing(me, [me, mk({ uid: "t", x: 2, y: 5 })])).toBe("front");
  });
  it("defaults by team", () => {
    expect(facing(mk({ team: "player" }), [])).toBe("back");
    expect(facing(mk({ team: "enemy" }), [])).toBe("front");
  });
});

describe("normalizeAngle", () => {
  it("wraps into (−π, π]", () => {
    close(normalizeAngle(3 * PI), PI);
    close(normalizeAngle(-3 * PI), PI);
    close(normalizeAngle(PI / 2 + 2 * PI), PI / 2);
    close(normalizeAngle(-PI / 2 - 2 * PI), -PI / 2);
  });
});

describe("YawTracker", () => {
  it("first set snaps current to target (a remounted view starts facing the right way)", () => {
    const t = new YawTracker();
    t.set(1.2);
    expect(t.current).toBe(1.2);
    expect(t.step(0.016)).toBe(1.2);
  });
  it("turns the short way round: −0.9π → +0.9π passes through π, never through 0", () => {
    const t = new YawTracker();
    t.set(-0.9 * PI);
    t.set(0.9 * PI);
    const y = t.step(0.01); // 0.1 rad step
    expect(y).toBeLessThan(-0.9 * PI + 1e-9); // moved further negative, toward −π
    expect(Math.abs(y)).toBeGreaterThan(0.9 * PI);
  });
  it("never overshoots the target", () => {
    const t = new YawTracker();
    t.set(0);
    t.set(0.05);
    close(t.step(1), 0.05);
    close(t.step(1), 0.05);
  });
  it("clamps a long frame so a hidden tab does not snap the whole way", () => {
    const t = new YawTracker();
    t.set(0);
    t.set(PI);
    const y = t.step(5);
    close(Math.abs(y), Math.min(PI, YAW_SPEED * 0.1));
  });
});

describe("frameModel", () => {
  it("centres x/z, puts feet at y=0 and scales height to 1", () => {
    const { scale, offset } = frameModel({ min: [1, 2, -3], max: [3, 4, -1] });
    close(scale, 0.5);
    close(offset[0], -1); // centre x = 2 → −2 × 0.5
    close(offset[1], -1); // min y = 2 → −2 × 0.5
    close(offset[2], 1); // centre z = −2 → 2 × 0.5
  });
  it("does not divide by zero on a flat box", () => {
    const { scale } = frameModel({ min: [0, 0, 0], max: [1, 0, 1] });
    expect(scale).toBe(1);
  });
});

describe("YawTracker.settled", () => {
  it("is true only when current has reached target", () => {
    const t = new YawTracker();
    t.set(0);
    expect(t.settled).toBe(true);
    t.set(1);
    expect(t.settled).toBe(false);
    t.step(1);
    expect(t.settled).toBe(true);
  });
});

describe("TrackerPool", () => {
  it("returns the same tracker for the same id, so a remounted view resumes mid-turn", () => {
    const pool = new TrackerPool(8);
    const a = pool.get("u1");
    a.set(0);
    a.set(2);
    a.step(0.05); // partway through the turn
    expect(pool.get("u1")).toBe(a);
    expect(pool.get("u1").current).toBeCloseTo(0.5, 6);
    expect(pool.get("u2")).not.toBe(a);
  });
  it("evicts the oldest ids beyond its capacity", () => {
    const pool = new TrackerPool(2);
    const a = pool.get("a");
    pool.get("b");
    pool.get("c");
    expect(pool.get("a")).not.toBe(a);
  });
});
