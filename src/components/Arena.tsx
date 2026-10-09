"use client";

import type { CSSProperties, DragEvent } from "react";
import { COLS, ROWS, ROWS_PER_SIDE } from "@/game/constants";
import type { CombatState } from "@/game/combat";
import { getMap } from "@/game/data/maps";
import type { GameState, Loc, Slot } from "@/game/types";
import { Fighter } from "./Fighter";
import { UnitChip } from "./UnitChip";

interface Props {
  state: GameState;
  /** Bench slots, drawn as a strip along the bottom edge of the arena. */
  bench: Slot[];
  /** Perspective view (true) or flat top-down (false). */
  tilted: boolean;
  combat: CombatState | null;
  selected: Loc | null;
  onCellClick: (loc: Loc) => void;
  onDragStart: (loc: Loc, e: DragEvent) => void;
  onDrop: (loc: Loc, e: DragEvent) => void;
}

/** Grid (x, y) → index into the owning half-board. */
function cellOwner(x: number, y: number): { side: "enemy" | "player"; index: number } {
  if (y < ROWS_PER_SIDE) return { side: "enemy", index: (ROWS_PER_SIDE - 1 - y) * COLS + (COLS - 1 - x) };
  return { side: "player", index: (y - ROWS_PER_SIDE) * COLS + x };
}


/** Ticks a defeated unit stays on the arena so its death animation can play. */
const DEATH_LINGER = 6;

export function Arena({ state, bench, tilted, combat, selected, onCellClick, onDragStart, onDrop }: Props) {
  const fighting = !!combat;
  const cells = [];
  for (let y = 0; y < ROWS; y++) {
    for (let x = 0; x < COLS; x++) {
      const { side, index } = cellOwner(x, y);
      const unit = side === "player" ? state.board[index] : state.enemyBoard[index];
      const loc: Loc = { area: "board", index };
      const isSel = selected?.area === "board" && selected.index === index && side === "player";
      const playerSide = side === "player";
      cells.push(
        <div
          key={`${x}-${y}`}
          className={`p3d relative aspect-square border border-white/10 p-[3px] ${
            playerSide ? "bg-sky-950/25" : "bg-rose-950/25"
          } ${y === ROWS_PER_SIDE ? "border-t-2 border-t-white/40" : ""} ${
            playerSide && !fighting ? "cursor-pointer hover:bg-sky-900/50" : ""
          }`}
          onClick={() => playerSide && !fighting && onCellClick(loc)}
          onDragOver={(e) => playerSide && !fighting && e.preventDefault()}
          onDrop={(e) => playerSide && !fighting && onDrop(loc, e)}
        >
          {!fighting && unit && (
            <div
              draggable={playerSide}
              onDragStart={(e) => playerSide && onDragStart(loc, e)}
              className="p3d h-full w-full"
            >
              <UnitChip unit={unit} selected={isSel} dim={!playerSide} view={tilted ? "front" : "board"} tipBelow={y < 2} bars />
            </div>
          )}
        </div>,
      );
    }
  }

  const map = getMap(state.mapId);
  return (
    // The tilted plane is shorter on screen than its layout box; the negative margin pulls the
    // header in to match. Tune together with --tilt.
    <div className={tilted ? "-mt-[9%]" : "arena-flat"} style={{ "--tilt": tilted ? "28deg" : "0deg" } as CSSProperties}>
    <div className={`select-none ${tilted ? "arena-tilted" : ""}`}>
    <div
      className={`rounded-t-xl border border-b-0 border-slate-700 bg-slate-950 bg-cover bg-top ${tilted ? "" : "overflow-hidden"}`}
      style={map.file ? { backgroundImage: `linear-gradient(rgba(2, 6, 23, 0.35), rgba(2, 6, 23, 0.35)), url(${map.file})` } : undefined}
    >
      {/* Battlefield: the fighters overlay is positioned against this box, not the bench below it. */}
      <div className="p3d relative">
        <div className="p3d grid grid-cols-7">{cells}</div>
        {combat && (
          <div className="p3d pointer-events-none absolute inset-0">
            {combat.units
              .filter((u) => u.alive || combat.tick - u.diedAt < DEATH_LINGER)
              .map((u) => (
                <Fighter
                  key={u.uid}
                  u={u}
                  units={combat.units}
                  pose={tilted ? "front" : "board"}
                  box={{ left: `${(u.x * 100) / COLS}%`, top: `${(u.y * 100) / ROWS}%`, width: `${100 / COLS}%`, height: `${100 / ROWS}%` }}
                />
              ))}
          </div>
        )}
        {!fighting && (
          <>
            <span className="pointer-events-none absolute left-2 top-1 text-[10px] font-semibold uppercase tracking-wider text-rose-300/80 drop-shadow">Enemy · next round</span>
            <span className="pointer-events-none absolute bottom-1 left-2 text-[10px] font-semibold uppercase tracking-wider text-sky-300/80 drop-shadow">Your board</span>
          </>
        )}
        {map.name && (
          <span className="pointer-events-none absolute bottom-1 right-2 text-[10px] font-semibold uppercase tracking-wider text-white/50 drop-shadow">{map.name}</span>
        )}
      </div>

      </div>

      {/* Bench: a stone walkway under the board, like TFT's. Units stand on the ledge and may rise over the board edge. */}
      <div className="bench p3d relative z-20 rounded-b-xl border border-t-0 border-slate-700">
        <div className="p3d grid grid-cols-8">
          {bench.map((unit, index) => {
            const loc: Loc = { area: "bench", index };
            const isSel = selected?.area === "bench" && selected.index === index;
            return (
              <div
                key={index}
                className={`bench-slot p3d relative aspect-[8/7] border-x border-white/10 p-[3px] first:border-l-0 last:border-r-0 ${fighting ? "" : "cursor-pointer hover:bg-white/10"}`}
                onClick={() => !fighting && onCellClick(loc)}
                onDragOver={(e) => !fighting && e.preventDefault()}
                onDrop={(e) => !fighting && onDrop(loc, e)}
              >
                {unit && (
                  <div draggable={!fighting} onDragStart={(e) => onDragStart(loc, e)} className="p3d h-full w-full">
                    <UnitChip unit={unit} selected={isSel} view={tilted ? "front" : "board"} bars />
                  </div>
                )}
              </div>
            );
          })}
        </div>
        <span className="pointer-events-none absolute bottom-1 right-2 text-[10px] font-semibold uppercase tracking-wider text-white/40 drop-shadow">Bench</span>
      </div>
    </div>
    </div>
  );
}
