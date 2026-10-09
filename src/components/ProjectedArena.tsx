"use client";

import { useLayoutEffect, useRef, useState, type CSSProperties, type DragEvent } from "react";
import type { CombatState } from "@/game/combat";
import { BENCH_SIZE, COLS, ROWS, ROWS_PER_SIDE } from "@/game/constants";
import { boardCount } from "@/game/reducer";
import type { ArenaMap } from "@/game/data/maps";
import { homography, project, toMatrix3d, type Point, type Quad } from "@/game/projection";
import type { GameState, Loc, Slot } from "@/game/types";
import { Fighter, GroundShadow } from "./Fighter";
import { UnitChip } from "./UnitChip";

export type PaintedMap = ArenaMap & { platform: Quad };

/** Where the platform's centre sits vertically in the window; the shop takes the bottom. */
const FOCUS_Y = 0.44;

interface Props {
  state: GameState;
  bench: Slot[];
  map: PaintedMap;
  combat: CombatState | null;
  selected: Loc | null;
  /** Unit currently being dragged; valid drop slots light up while it is set. */
  dragging: Loc | null;
  onCellClick: (loc: Loc) => void;
  onDragStart: (loc: Loc, e: DragEvent) => void;
  onDrop: (loc: Loc, e: DragEvent) => void;
}

/** Grid (x, y) → index into the owning half-board. Same convention as Arena. */
function cellOwner(x: number, y: number): { side: "enemy" | "player"; index: number } {
  if (y < ROWS_PER_SIDE) return { side: "enemy", index: (ROWS_PER_SIDE - 1 - y) * COLS + (COLS - 1 - x) };
  return { side: "player", index: (y - ROWS_PER_SIDE) * COLS + x };
}

/** Source plane: CELL px per grid cell; the bench is one extra row under the board. */
const CELL = 100;
const BENCH_ROW = ROWS;
/** Sprite box, as a multiple of the projected cell width at that row (units stand ~1.2 cells tall, inside their cell like TFT). */
const UNIT_BOX = 1.6;
/** Ticks a defeated unit stays on the arena so its death animation can play. */
const DEATH_LINGER = 6;

/**
 * A painted arena: the map image fills the window (the HUD floats over it) and the grid is
 * projected onto the floor's quad, so cells follow the painting's perspective. Units are upright
 * billboards placed at projected cell centres and sized by the cell width at their row, so the
 * back rows are smaller.
 */
export function ProjectedArena({ state, bench, map, combat, selected, dragging, onCellClick, onDragStart, onDrop }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ w: 0, h: 0 });
  // Slot under the pointer during a drag (hover styles do not apply during native drag and drop).
  const [hover, setHover] = useState<Loc | null>(null);
  const spriteEls = useRef<Record<string, HTMLDivElement | null>>({});
  // Hovered unit: raised above every neighbour so its hover card is never covered.
  const [hoverKey, setHoverKey] = useState<string | null>(null);
  const hovered = (loc: Loc) => !!dragging && hover?.area === loc.area && hover.index === loc.index;
  // A bench unit cannot be dropped on an empty board cell once the board is full; swaps are still fine.
  const boardFull = boardCount(state.board) >= state.level;
  const canDropOn = (loc: Loc, occupied: boolean) => !!dragging && (loc.area === "bench" || occupied || dragging.area === "board" || !boardFull);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver(([entry]) => setSize({ w: entry.contentRect.width, h: entry.contentRect.height }));
    ro.observe(el);
    setSize({ w: el.clientWidth, h: el.clientHeight });
    return () => ro.disconnect();
  }, []);

  const { platform, aspect = 1, focus = [0.5, 0.5], zoom = 1 } = map;
  const fighting = !!combat;
  // The image covers the window, enlarged by `zoom`, with `focus` pinned near the centre.
  const imgW = Math.max(size.w, size.h * aspect) * zoom;
  const imgH = imgW / aspect;
  const offX = size.w / 2 - focus[0] * imgW;
  const offY = size.h * FOCUS_Y - focus[1] * imgH;
  const toPx = ([fx, fy]: Point): Point => [fx * imgW + offX, fy * imgH + offY];
  const quad: Quad = { tl: toPx(platform.tl), tr: toPx(platform.tr), br: toPx(platform.br), bl: toPx(platform.bl) };
  const H = size.w > 0 ? homography(COLS * CELL, ROWS * CELL, quad) : null;
  const P = (gx: number, gy: number): Point => (H ? project(H, gx * CELL, gy * CELL) : [0, 0]);

  /** Box for a sprite whose feet stand at grid point (gx, gy), plus the cell width there. */
  const boxAt = (gx: number, gy: number) => {
    const [cx, cy] = P(gx, gy);
    const cw = Math.abs(P(gx + 0.5, gy)[0] - P(gx - 0.5, gy)[0]);
    const s = cw * UNIT_BOX;
    // Stacking follows the feet's screen position: closer to the camera paints on top.
    return { box: { left: cx - s / 2, top: cy - s / 2, width: s, height: s, zIndex: 10 + Math.round(cy) } as CSSProperties, size: s, cw };
  };

  const cells = [];
  for (let y = 0; y < ROWS; y++) {
    for (let x = 0; x < COLS; x++) {
      const { side, index } = cellOwner(x, y);
      const loc: Loc = { area: "board", index };
      const playerSide = side === "player";
      const occupied = !fighting && !!(playerSide ? state.board[index] : state.enemyBoard[index]);
      const target = playerSide && !fighting && canDropOn(loc, occupied);
      const fill = hovered(loc)
        ? "bg-sky-200/50 ring-2 ring-inset ring-white/80"
        : target
          ? "bg-sky-300/30 ring-1 ring-inset ring-sky-100/60"
          : occupied
            ? playerSide
              ? "bg-sky-300/25"
              : "bg-rose-300/20"
            : playerSide
              ? "bg-sky-400/5"
              : "bg-rose-400/5";
      cells.push(
        <div
          key={`${x}-${y}`}
          style={{ width: CELL, height: CELL }}
          className={`border border-white/10 transition-colors ${y === ROWS_PER_SIDE ? "border-t-2 border-t-white/40" : ""} ${fill} ${
            playerSide && !fighting ? "cursor-pointer hover:bg-sky-300/30" : ""
          }`}
          onClick={() => playerSide && !fighting && onCellClick(loc)}
          onDragEnter={() => playerSide && !fighting && setHover(loc)}
          onDragOver={(e) => playerSide && !fighting && e.preventDefault()}
          onDrop={(e) => {
            if (!playerSide || fighting) return;
            setHover(null);
            onDrop(loc, e);
          }}
        />,
      );
    }
  }
  const benchCells = [];
  for (let i = 0; i < BENCH_SIZE; i++) {
    const loc: Loc = { area: "bench", index: i };
    const fill = hovered(loc) ? "bg-white/50 ring-2 ring-inset ring-white/80" : dragging && !fighting ? "bg-white/25 ring-1 ring-inset ring-white/50" : bench[i] ? "bg-white/20" : "bg-white/5";
    benchCells.push(
      <div
        key={i}
        style={{ width: (COLS * CELL) / BENCH_SIZE, height: CELL }}
        className={`border border-white/15 transition-colors ${fill} ${fighting ? "" : "cursor-pointer hover:bg-white/25"}`}
        onClick={() => !fighting && onCellClick(loc)}
        onDragEnter={() => !fighting && setHover(loc)}
        onDragOver={(e) => !fighting && e.preventDefault()}
        onDrop={(e) => {
          if (fighting) return;
          setHover(null);
          onDrop(loc, e);
        }}
      />,
    );
  }

  /** Planning-phase sprites in draw order (back rows first), with a cell-sized hit area at their feet. */
  const sprites = [];
  if (!fighting && H) {
    for (let y = 0; y < ROWS; y++) {
      for (let x = 0; x < COLS; x++) {
        const { side, index } = cellOwner(x, y);
        const unit = side === "player" ? state.board[index] : state.enemyBoard[index];
        if (!unit) continue;
        const playerSide = side === "player";
        const loc: Loc = { area: "board", index };
        const isSel = selected?.area === "board" && selected.index === index && playerSide;
        sprites.push({ key: unit.uid, unit, loc, isSel, dim: !playerSide, interactive: playerSide, tipBelow: y < 2, ...boxAt(x + 0.5, y + 0.5) });
      }
    }
    bench.forEach((unit, i) => {
      if (!unit) return;
      const loc: Loc = { area: "bench", index: i };
      const isSel = selected?.area === "bench" && selected.index === i;
      sprites.push({ key: unit.uid, unit, loc, isSel, dim: false, interactive: true, tipBelow: false, ...boxAt(((i + 0.5) * COLS) / BENCH_SIZE, BENCH_ROW + 0.5) });
    });
  }

  const label = (gx: number, gy: number, text: string, cls: string, extra: CSSProperties = {}) => {
    const [x, y] = P(gx, gy);
    return (
      <span className={`pointer-events-none absolute text-[10px] font-semibold uppercase tracking-wider drop-shadow ${cls}`} style={{ left: x, top: y, ...extra }}>
        {text}
      </span>
    );
  };

  return (
    <div ref={ref} className="select-none fixed inset-0 z-0 overflow-hidden bg-slate-950" style={{ "--tilt": "0deg" } as CSSProperties}>
      {/* Backdrop: the same image blown up, blurred and darkened, so a zoomed-out map has no hard edges. */}
      <div
        aria-hidden
        className="pointer-events-none absolute -inset-8 bg-cover bg-center"
        style={{ backgroundImage: `url(${map.file})`, filter: "blur(28px) brightness(0.45)" }}
      />
      {/* The scene itself, placed by focus/zoom. */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 bg-no-repeat"
        style={{
          backgroundImage: `url(${map.file})`,
          backgroundSize: `${imgW}px ${imgH}px`,
          backgroundPosition: `${offX}px ${offY}px`,
          // Fade the scene into the backdrop instead of ending in a hard rectangle.
          maskImage: `radial-gradient(ellipse ${imgW * 0.62}px ${imgH * 0.6}px at ${offX + imgW / 2}px ${offY + imgH / 2}px, black 62%, transparent 100%)`,
        }}
      />
      {H && (
        <>
          {/* The floor: board cells plus the bench row, projected onto the painting. */}
          <div className="absolute left-0 top-0" style={{ width: COLS * CELL, height: (ROWS + 1) * CELL, transform: toMatrix3d(H), transformOrigin: "0 0" }}>
            <div className="grid grid-cols-7">{cells}</div>
            <div className="flex">{benchCells}</div>
          </div>

          {/* Side labels stand along the left edge of each half, rotated so they do not sit on the back rows. */}
          {!fighting && label(0, ROWS_PER_SIDE / 2, "Enemy · next round", "text-rose-300/80", { transform: "translate(calc(-100% - 14px), -50%) rotate(-90deg)", transformOrigin: "100% 50%" })}
          {!fighting && label(0, ROWS_PER_SIDE * 1.5, "Your board", "text-sky-300/80", { transform: "translate(calc(-100% - 14px), -50%) rotate(-90deg)", transformOrigin: "100% 50%" })}
          {label(COLS, BENCH_ROW + 1, "Bench", "text-white/50", { transform: "translate(-100%, 10%)" })}

          {/* Upright sprites over the floor. Boxes are transparent to the pointer; only the footprint at the feet is interactive. */}
          <div className="p3d pointer-events-none absolute inset-0">
            {sprites.map((sp) => (
              <div
                key={sp.key}
                className={`p3d group absolute transition-opacity ${dragging?.area === sp.loc.area && dragging.index === sp.loc.index ? "opacity-30" : ""}`}
                style={hoverKey === sp.key ? { ...sp.box, zIndex: 1000 } : sp.box}
              >
                <GroundShadow size={sp.size} cw={sp.cw} />
                {/* Visual, kept in a sibling so the drag ghost is the whole sprite, not just the hit area. */}
                <div className="absolute inset-0" ref={(el) => void (spriteEls.current[sp.key] = el)}>
                  <UnitChip unit={sp.unit} selected={sp.isSel} dim={sp.dim} view="board" tipBelow={sp.tipBelow} size={sp.size} bars />
                </div>
                <div
                  className={`pointer-events-auto absolute ${sp.interactive ? "cursor-grab active:cursor-grabbing" : ""}`}
                  style={{ left: (sp.size - sp.cw) / 2, top: sp.size / 2 - sp.cw * 0.8, width: sp.cw, height: sp.cw * 0.8 }}
                  draggable={sp.interactive}
                  onDragStart={(e) => {
                    if (!sp.interactive) return;
                    const ghost = spriteEls.current[sp.key];
                    if (ghost) e.dataTransfer.setDragImage(ghost, sp.size / 2, sp.size / 2);
                    onDragStart(sp.loc, e);
                  }}
                  onClick={() => sp.interactive && onCellClick(sp.loc)}
                  onMouseEnter={() => setHoverKey(sp.key)}
                  onMouseLeave={() => setHoverKey((k) => (k === sp.key ? null : k))}
                  onDragEnter={() => sp.interactive && setHover(sp.loc)}
                  onDragOver={(e) => sp.interactive && e.preventDefault()}
                  onDrop={(e) => {
                    if (!sp.interactive) return;
                    setHover(null);
                    onDrop(sp.loc, e);
                  }}
                />
              </div>
            ))}
            {combat &&
              combat.units
                .filter((u) => u.alive || combat.tick - u.diedAt < DEATH_LINGER)
                .map((u) => {
                  const { box, size: s } = boxAt(u.x + 0.5, u.y + 0.5);
                  return <Fighter key={u.uid} u={u} units={combat.units} pose="board" box={box} size={s} />;
                })}
          </div>
        </>
      )}
    </div>
  );
}
