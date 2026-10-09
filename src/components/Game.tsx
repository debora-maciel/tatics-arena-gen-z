"use client";

import { useCallback, useEffect, useRef, useState, type CSSProperties, type DragEvent } from "react";
import { finishCombat, setupCombat, stepCombat, type CombatState } from "@/game/combat";
import { TICK_MS } from "@/game/constants";
import { getMap } from "@/game/data/maps";
import { UNIT_BY_ID } from "@/game/data/units";
import { describeEnemy } from "@/game/enemy";
import { boardCount, sellValue } from "@/game/reducer";
import { resetStats } from "@/game/storage";
import { computeTraits } from "@/game/synergies";
import { preloadModel } from "@/three/modelRenderer";
import type { Loc } from "@/game/types";
import { useGame } from "@/hooks/useGame";
import { playSound } from "@/audio/sounds";
import { Arena } from "./Arena";
import { ProjectedArena, type PaintedMap } from "./ProjectedArena";
import { EndScreen } from "./EndScreen";
import { Records } from "./Records";
import { RosterModal } from "./RosterModal";
import { Shop } from "./Shop";
import { TopBar } from "./TopBar";
import { TraitsPanel } from "./TraitsPanel";
import { UnitDetail } from "./UnitDetail";

const SPEEDS = [1, 2, 4];
/** How long the Victory/Defeat banner stays before the next round starts. */
const RESULT_PAUSE_MS = 1500;
const SIDEBAR_KEY = "tactics-arena:ui:sidebar-collapsed";
const TILT_KEY = "tactics-arena:ui:flat-arena";

function readFlag(key: string) {
  try {
    return localStorage.getItem(key) === "1";
  } catch {
    return false;
  }
}

function writeFlag(key: string, value: boolean) {
  try {
    localStorage.setItem(key, value ? "1" : "0");
  } catch {
    // Storage unavailable: the toggle still works for this page view.
  }
}

export function Game() {
  const { state, dispatch, stats } = useGame();
  const [selected, setSelected] = useState<Loc | null>(null);
  // The live simulation is mutated in a ref; `combat` is a snapshot published for rendering.
  const combatRef = useRef<CombatState | null>(null);
  const [combat, setCombat] = useState<CombatState | null>(null);
  const [speed, setSpeed] = useState(1);
  const [sideCollapsed, setSideCollapsed] = useState(() => readFlag(SIDEBAR_KEY));
  const [showRoster, setShowRoster] = useState(false);
  /** Unit currently being dragged (drag and drop only, not click-select). */
  const [dragging, setDragging] = useState<Loc | null>(null);
  // Perspective view is the default; the flag stores the opt-out.
  const [tilted, setTilted] = useState(() => !readFlag(TILT_KEY));
  const toggleTilt = () => {
    setTilted((t) => {
      writeFlag(TILT_KEY, t);
      return !t;
    });
  };
  const toggleSide = () => {
    setSideCollapsed((c) => {
      writeFlag(SIDEBAR_KEY, !c);
      return !c;
    });
  };

  // Tick loop. Simulation time follows the wall clock: however long a render takes, the fight
  // advances by the elapsed real time (× speed), so a slow frame never slows the battle.
  const fighting = !!combat && !combat.winner;
  useEffect(() => {
    if (!fighting) return;
    let last = performance.now();
    let carry = 0;
    const id = setInterval(() => {
      const cs = combatRef.current;
      if (!cs || cs.winner) return;
      const now = performance.now();
      carry += (now - last) * speed;
      last = now;
      let n = Math.floor(carry / TICK_MS);
      if (n <= 0) return;
      carry -= n * TICK_MS;
      n = Math.min(n, 10); // after a background-tab pause, catch up gradually rather than all at once
      for (let i = 0; i < n && !cs.winner; i++) stepCombat(cs);
      setCombat({ ...cs });
    }, 50);
    return () => clearInterval(id);
  }, [fighting, speed]);

  // Warm the 3D model cache for every unit on the arena or bench, so the model is ready wherever it shows.
  useEffect(() => {
    for (const slot of [...state.board, ...state.bench, ...state.enemyBoard]) {
      const model = slot && UNIT_BY_ID[slot.defId]?.model;
      if (model) preloadModel(model);
    }
  }, [state.board, state.bench, state.enemyBoard]);

  const startCombat = () => {
    setSelected(null);
    combatRef.current = setupCombat(state);
    setCombat({ ...combatRef.current });
    dispatch({ type: "START_COMBAT" });
  };

  const skipCombat = () => {
    const cs = combatRef.current;
    if (!cs) return;
    finishCombat(cs);
    setCombat({ ...cs });
  };

  const resolve = useCallback(() => {
    if (!combat?.winner) return;
    const survivors = combat.units.filter((u) => u.alive && u.team === "enemy").map((u) => ({ star: u.star }));
    dispatch({ type: "RESOLVE_COMBAT", won: combat.winner === "player", survivors });
    combatRef.current = null;
    setCombat(null);
  }, [combat, dispatch]);

  // Once a fight is decided, move on by itself after a short pause so the result can be read;
  // the Continue button just skips the pause.
  const winner = combat?.winner ?? null;
  useEffect(() => {
    if (!winner) return;
    const id = setTimeout(resolve, RESULT_PAUSE_MS);
    return () => clearTimeout(id);
  }, [winner, resolve]);

  const planning = state.phase === "planning";
  const selectedUnit = selected ? (selected.area === "bench" ? state.bench : state.board)[selected.index] : null;

  /** Dispatches a move and, when it lands a unit from the bench onto the board, plays that unit's cue. */
  const moveUnit = (from: Loc, to: Loc) => {
    const unit = (from.area === "bench" ? state.bench : state.board)[from.index];
    const target = (to.area === "bench" ? state.bench : state.board)[to.index];
    dispatch({ type: "MOVE", from, to });
    const placed = from.area === "bench" && to.area === "board" && unit && (target || boardCount(state.board) < state.level);
    const sound = placed ? UNIT_BY_ID[unit.defId].sound : undefined;
    if (sound) playSound(sound);
  };

  const onCellClick = (loc: Loc) => {
    if (!planning) return;
    const unit = (loc.area === "bench" ? state.bench : state.board)[loc.index];
    if (!selected) {
      if (unit) setSelected(loc);
      return;
    }
    if (selected.area === loc.area && selected.index === loc.index) {
      setSelected(null);
      return;
    }
    moveUnit(selected, loc);
    setSelected(null);
  };

  const onDragStart = (loc: Loc, e: DragEvent) => {
    e.dataTransfer.setData("text/plain", JSON.stringify(loc));
    e.dataTransfer.effectAllowed = "move";
    setSelected(loc);
    setDragging(loc);
  };
  const onDragEnd = () => setDragging(null);
  const draggingUnit = dragging ? (dragging.area === "bench" ? state.bench : state.board)[dragging.index] : null;

  const readLoc = (e: DragEvent): Loc | null => {
    try {
      return JSON.parse(e.dataTransfer.getData("text/plain")) as Loc;
    } catch {
      return null;
    }
  };

  const onDrop = (to: Loc, e: DragEvent) => {
    e.preventDefault();
    const from = readLoc(e);
    if (from) moveUnit(from, to);
    setSelected(null);
    setDragging(null);
  };

  const onDropSell = (e: DragEvent) => {
    e.preventDefault();
    const loc = readLoc(e);
    if (loc) dispatch({ type: "SELL", loc });
    setSelected(null);
    setDragging(null);
  };

  const sellSelected = () => {
    if (!selected || !selectedUnit) return;
    dispatch({ type: "SELL", loc: selected });
    setSelected(null);
  };

  const newGame = () => {
    setSelected(null);
    combatRef.current = null;
    setCombat(null);
    dispatch({ type: "NEW_GAME" });
  };

  const traits = computeTraits(state.board);
  const canFight = planning && boardCount(state.board) > 0;
  const map = getMap(state.mapId);
  const { palette } = map;
  // Painted maps fix their own camera, so the tilt toggle only applies to the plain grid.
  const painted = map.platform ? (map as PaintedMap) : null;

  return (
    <div
      className={`mx-auto flex min-h-screen w-full max-w-7xl flex-col gap-3 p-3 pb-56 sm:p-4 sm:pb-56 ${dragging ? "is-dragging" : ""}`}
      style={{ "--panel": palette.panel } as CSSProperties}
      onDragEnd={onDragEnd}
    >
      {/* Page backdrop in the current map's colours. */}
      <div
        aria-hidden
        className="pointer-events-none fixed inset-0 -z-10 transition-[background] duration-700"
        style={{ background: `radial-gradient(ellipse 80% 60% at 50% 30%, ${palette.glow}, transparent 70%), ${palette.bg}` }}
      />

      {/* Painted maps: the scene fills the window and everything below floats over it as a HUD. */}
      {painted && (
        <ProjectedArena
          state={state}
          bench={state.bench}
          map={painted}
          combat={combat}
          selected={selected}
          dragging={dragging}
          onCellClick={onCellClick}
          onDragStart={onDragStart}
          onDrop={onDrop}
        />
      )}

      <div
        className={`relative z-10 grid gap-3 ${painted ? "pointer-events-none" : ""} ${sideCollapsed ? "lg:grid-cols-[44px_minmax(0,1fr)_250px]" : "lg:grid-cols-[max-content_minmax(0,1fr)_250px]"}`}
      >
        {sideCollapsed ? (
          <button
            type="button"
            onClick={toggleSide}
            title="Show synergies"
            aria-label="Show synergies"
            className="pointer-events-auto order-2 flex items-center justify-between gap-2 rounded-xl border border-white/10 bg-[var(--panel)] px-3 py-2 text-xs text-slate-400 backdrop-blur-sm hover:text-slate-200 lg:order-1 lg:flex-col lg:justify-start lg:px-0 lg:py-3"
          >
            <span aria-hidden>▸</span>
            <span className="font-semibold uppercase tracking-wider lg:[writing-mode:vertical-rl]">Synergies</span>
            <span className="rounded-full bg-slate-800 px-1.5 font-mono text-[10px] text-amber-200" title="Your active synergies">
              {traits.filter((t) => t.tier > 0).length}
            </span>
          </button>
        ) : (
          <div className="pointer-events-auto order-2 space-y-3 lg:order-1">
            <button
              type="button"
              onClick={toggleSide}
              className="flex w-full items-center justify-end gap-1 px-1 text-[11px] text-slate-500 hover:text-slate-300"
              title="Hide synergies and widen the arena"
            >
              <span aria-hidden>◂</span> Hide
            </button>
            <TraitsPanel traits={traits} title="Your synergies" emptyText="Place units on the board to activate synergies." board={state.board} />
          </div>
        )}

        {/* The plain arena is capped so arena + fight bar + the fixed shop fit in one viewport height.
            On a painted map this column is empty space over the scene, with the fight bar pushed to the bottom. */}
        <div
          className={`order-1 mx-auto flex w-full flex-col gap-2 lg:order-2 ${painted ? "relative min-h-[calc(100vh-206px)] justify-start lg:self-start" : "justify-end"}`}
          style={painted ? { maxWidth: "56rem" } : { maxWidth: "calc((100vh - 330px) / 0.97)" }}
        >
          {!painted && (
            <Arena
              state={state}
              bench={state.bench}
              tilted={tilted}
              combat={combat}
              selected={selected}
              onCellClick={onCellClick}
              onDragStart={onDragStart}
              onDrop={onDrop}
            />
          )}

          <div className="pointer-events-auto flex flex-wrap items-center gap-2 rounded-xl border border-white/10 bg-[var(--panel)] px-3 py-2 text-xs backdrop-blur-sm">
            {!painted && (
              <button className="btn px-2" onClick={toggleTilt} title={tilted ? "Switch to flat top-down view" : "Switch to perspective view"}>
                {tilted ? "◈ 3D" : "▦ Flat"}
              </button>
            )}
            {planning && (
              <>
                <span className="text-slate-400">
                  Next opponent: <span className="text-slate-200">{describeEnemy(state.enemyBoard)}</span>
                </span>
                {state.lastResult && (
                  <span className={`rounded-full px-2 py-0.5 ${state.lastResult.won ? "bg-emerald-950 text-emerald-300" : "bg-rose-950 text-rose-300"}`}>
                    Round {state.lastResult.round}: {state.lastResult.won ? "won" : `lost, −${state.lastResult.damage} HP`}
                  </span>
                )}
                <button
                  className="btn ml-auto border-emerald-400 bg-emerald-500/20 px-5 text-emerald-100 enabled:hover:bg-emerald-500/30"
                  disabled={!canFight}
                  onClick={startCombat}
                  title={canFight ? "Start the fight" : "Place at least one unit on the board"}
                >
                  ⚔️ Fight round {state.round}
                </button>
              </>
            )}
            {combat && (
              <>
                <span className="font-mono text-slate-400">{(combat.tick / 10).toFixed(1)}s</span>
                <span className="text-slate-400">
                  {combat.units.filter((u) => u.alive && u.team === "player").length} vs {combat.units.filter((u) => u.alive && u.team === "enemy").length}
                </span>
                {!combat.winner ? (
                  <>
                    <div className="ml-auto flex overflow-hidden rounded-lg border border-slate-700">
                      {SPEEDS.map((s) => (
                        <button key={s} className={`px-2.5 py-1 ${speed === s ? "bg-slate-700 text-white" : "text-slate-400 hover:bg-slate-800"}`} onClick={() => setSpeed(s)}>
                          {s}×
                        </button>
                      ))}
                    </div>
                    <button className="btn" onClick={skipCombat}>
                      Skip ⏭
                    </button>
                  </>
                ) : (
                  <>
                    <span className={`font-semibold ${combat.winner === "player" ? "text-emerald-300" : "text-rose-300"}`}>
                      {combat.winner === "player" ? "Victory!" : "Defeat"}
                    </span>
                    <button className="btn ml-auto border-sky-400 bg-sky-500/20 px-5 text-sky-100 hover:bg-sky-500/30" onClick={resolve}>
                      Continue →
                    </button>
                  </>
                )}
              </>
            )}
          </div>

          {combat && (
            <div
              className={`pointer-events-auto overflow-y-auto rounded-xl border border-white/10 bg-[var(--panel)] p-2 font-mono text-[11px] leading-relaxed text-slate-400 backdrop-blur-sm ${
                painted ? "absolute inset-x-0 bottom-0 max-h-20" : "max-h-28"
              }`}
            >
              {combat.log.map((line, i) => (
                <div key={`${combat.tick}-${i}`} className={i === 0 ? "text-slate-200" : ""}>
                  {line}
                </div>
              ))}
            </div>
          )}
        </div>

        <aside className="pointer-events-auto order-3 space-y-3">
          <TopBar state={state} />
          <UnitDetail unit={selectedUnit} onSell={sellSelected} disabled={!planning} />
          <Records stats={stats} onNewGame={newGame} onReset={resetStats} onShowRoster={() => setShowRoster(true)} />
        </aside>
      </div>

      {!painted && (
        <p className="text-center text-[11px] text-slate-600">
          Buy units, place up to <span className="text-slate-400">level</span> of them on the board, and collect three copies to star them up. Shared traits unlock synergies.
        </p>
      )}

      {/* Shop stays pinned to the bottom of the viewport; the page reserves room for it below. */}
      <div className="fixed inset-x-0 bottom-0 z-40 px-3 pb-3 sm:px-4">
        <div className="mx-auto w-full max-w-7xl rounded-xl shadow-[0_-12px_32px_rgba(0,0,0,0.45)] backdrop-blur-md">
          <Shop
            state={state}
            disabled={!planning}
            sellLabel={selectedUnit ? `Sell · ${sellValue(selectedUnit)}g` : null}
            onBuy={(slot) => dispatch({ type: "BUY", slot })}
            onReroll={() => dispatch({ type: "REROLL" })}
            onBuyXp={() => dispatch({ type: "BUY_XP" })}
            onToggleLock={() => dispatch({ type: "TOGGLE_LOCK" })}
            onSellSelected={sellSelected}
            onDropSell={onDropSell}
            sellDrag={draggingUnit ? `Sell ${UNIT_BY_ID[draggingUnit.defId].name} for ${sellValue(draggingUnit)}g` : null}
          />
        </div>
      </div>


      {showRoster && <RosterModal onClose={() => setShowRoster(false)} />}
      {(state.phase === "gameover" || state.phase === "victory") && <EndScreen state={state} onNewGame={newGame} />}
    </div>
  );
}
