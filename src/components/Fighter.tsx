"use client";

import type { CSSProperties } from "react";
import type { CombatUnit } from "@/game/combat";
import { UNIT_BY_ID } from "@/game/data/units";
import { facing, facingYaw } from "@/game/facing";
import type { Pose } from "@/three/modelRenderer";
import { UnitArtFacing, type ArtView } from "./UnitArt";
import { Bar, HP_SEGMENT, Stars } from "./UnitChip";
import { UnitModel } from "./UnitModel";

/** Pixel offset of the attack lunge for each facing. */
const LUNGE: Record<ArtView, [string, string]> = {
  back: ["0px", "-7px"],
  front: ["0px", "7px"],
  east: ["7px", "0px"],
  west: ["-7px", "0px"],
  portrait: ["0px", "0px"],
  board: ["0px", "0px"],
};

/** Stable per-unit phase so idle bobs don't march in lockstep. */
function idleDelay(uid: string) {
  let h = 0;
  for (const c of uid) h = (h * 31 + c.charCodeAt(0)) % 1000;
  return `-${h}ms`;
}

/** Soft ellipse at a unit's feet (the box centre) so it reads as standing on the floor. */
export function GroundShadow({ size, cw }: { size: number; cw: number }) {
  const w = cw * 0.72;
  const h = cw * 0.26;
  return (
    <div
      aria-hidden
      className="pointer-events-none absolute rounded-[50%]"
      style={{
        left: (size - w) / 2,
        top: size / 2 - h / 2,
        width: w,
        height: h,
        background: "radial-gradient(ellipse at center, rgba(0,0,0,0.5) 0%, rgba(0,0,0,0.25) 45%, rgba(0,0,0,0) 72%)",
      }}
    />
  );
}

interface Props {
  u: CombatUnit;
  units: CombatUnit[];
  pose: Pose;
  /** The box the unit stands in; its feet sit at the box's centre (`.stand` is anchored at bottom-1/2). */
  box: CSSProperties;
  /** Art size in px for arenas that size units per row; omitted → responsive size classes. */
  size?: number;
}

/**
 * One unit on the arena during combat. Each event (attack, hit, cast, move) is a tick stamp on the
 * CombatUnit; wrapping the art in an element keyed by that stamp remounts it, which restarts the
 * CSS animation exactly once per event.
 */
export function Fighter({ u, units, pose, box, size }: Props) {
  const def = UNIT_BY_ID[u.defId];
  const view = facing(u, units);
  const yaw = facingYaw(u, units);
  const [lx, ly] = LUNGE[view];
  const modelStyle = size ? { width: size, height: size } : undefined;
  const artStyle = size ? { width: size * 0.5, height: size * 0.5 } : undefined;
  const modelClass = size ? "" : "h-40 w-40 sm:h-52 sm:w-52";
  const artClass = size ? "" : def.art ? "h-24 w-24 sm:h-[7.5rem] sm:w-[7.5rem]" : "h-11 w-11 sm:h-14 sm:w-14";
  return (
    // Closer to the camera (larger y) paints on top, so a front-row unit is never hidden behind one further back.
    // z-index is in the transition too, so a moving unit's depth follows it between rows.
    <div className="p3d absolute p-[3px] transition-[left,top,z-index] duration-300 ease-out" style={{ zIndex: 10 + u.y * 10, ...box }}>
      {size && u.alive && <GroundShadow size={size} cw={size / 1.6} />}
      <div key={`hop-${u.movedAt}`} className={`p3d relative h-full w-full ${u.movedAt >= 0 ? "animate-hop" : ""}`}>
        {/* Cast ring lies flat on the ground under the unit. */}
        {u.castAt >= 0 && (
          <div key={`cast-${u.castAt}`} className={`animate-cast pointer-events-none absolute rounded-lg ${size ? "inset-[30%] rounded-full" : "inset-0"}`} />
        )}
        {/* The character stands on a plate whose bottom edge is the cell centre, so its feet touch the ground there. */}
        <div className={`stand absolute inset-x-0 bottom-1/2 flex h-full flex-col items-center justify-end gap-0.5 ${u.alive ? "" : "animate-die"}`}>
          {/* Badges sit just above the head: the render leaves ~20% empty canvas above it, so they overlap that space. */}
          <div className="relative z-10 flex flex-col items-center gap-0.5" style={size && def.model ? { marginBottom: -size * 0.2 } : undefined}>
            <Stars star={u.star} />
            <div className="w-3/4 space-y-0.5" style={size ? { width: size * 0.45 } : undefined}>
              <Bar value={u.hp} max={u.maxHp} segment={HP_SEGMENT} className={u.team === "player" ? "bg-emerald-400" : "bg-rose-400"} />
              <Bar value={u.mana} max={u.maxMana} className="bg-sky-300" />
            </div>
          </div>
          <div key={`atk-${u.attackedAt}`} className={u.attackedAt >= 0 ? "animate-lunge" : ""} style={{ "--lx": lx, "--ly": ly } as CSSProperties}>
            <div className="animate-idle" style={{ animationDelay: idleDelay(u.uid) }}>
              <div key={`hit-${u.hitAt}`} className={`flex ${u.hitAt >= 0 ? "animate-hit" : ""}`}>
                {def.model ? (
                  <UnitModel id={u.uid} def={def} yaw={yaw} fallbackView={view} pose={pose} className={modelClass} style={modelStyle} emojiClass="text-2xl sm:text-3xl" />
                ) : (
                  <UnitArtFacing def={def} view={view} className={artClass} style={artStyle} emojiClass="text-2xl sm:text-3xl" />
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
