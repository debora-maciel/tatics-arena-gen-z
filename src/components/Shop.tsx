"use client";

import Image from "next/image";

import { useState, type DragEvent } from "react";
import {
  COST_BAR,
  COST_COLOR,
  MAX_LEVEL,
  REROLL_COST,
  XP_COST,
  XP_PER_BUY,
} from "@/game/constants";
import { UNIT_BY_ID } from "@/game/data/units";
import { projectedIncome, xpToNext } from "@/game/reducer";
import type { GameState } from "@/game/types";
import { CoinIcon } from "./Icons";
import { TraitBadge } from "./TraitIcons";
import { UnitArt } from "./UnitArt";

interface Props {
  state: GameState;
  disabled: boolean;
  sellLabel: string | null;
  onBuy: (slot: number) => void;
  onReroll: () => void;
  onBuyXp: () => void;
  onToggleLock: () => void;
  onSellSelected: () => void;
  onDropSell: (e: DragEvent) => void;
  /** While a unit is being dragged: the label for the sell bin that covers the shop. */
  sellDrag: string | null;
}

export function Shop({
  state,
  disabled,
  sellLabel,
  onBuy,
  onReroll,
  onBuyXp,
  onToggleLock,
  onSellSelected,
  onDropSell,
  sellDrag,
}: Props) {
  const [over, setOver] = useState(false);
  const maxed = state.level >= MAX_LEVEL;
  const income = projectedIncome(state);
  const nextGold = income.base + income.interest + income.streak;
  return (
    <section
      aria-label="Shop"
      className="relative rounded-xl border border-white/10 bg-[var(--panel)] pb-2 px-2"
      onDragOver={(e) => {
        if (disabled) return;
        e.preventDefault();
        setOver(true);
      }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => {
        setOver(false);
        if (!disabled) onDropSell(e);
      }}
    >
      {/* Sell bin: covers the shop while a unit is dragged, like TFT. */}
      {sellDrag && (
        <div
          className={`pointer-events-none absolute inset-0 z-10 flex flex-col items-center justify-center gap-1 rounded-xl border-2 border-dashed transition ${
            over ? "border-rose-300 bg-rose-900/80" : "border-rose-500/70 bg-slate-950/85"
          }`}
        >
          <span className={`text-4xl transition-transform ${over ? "scale-125" : ""}`} aria-hidden>
            🗑️
          </span>
          <span className="text-sm font-semibold text-rose-100">{sellDrag}</span>
          <span className="text-[11px] text-rose-200/70">Drop here to sell</span>
        </div>
      )}
      <div className="flex w-full items-end justify-center">
        <span
          className="flex h-8 min-w-14 items-center justify-center gap-1 rounded-t-full bg-yellow-700 px-3 font-mono text-base font-bold text-amber-50 shadow-[inset_0_1px_0_rgba(255,255,255,0.25)]"
          title={`Gold. Next round: +${income.base} base, +${income.interest} interest, +${income.streak} streak`}
        >
          <CoinIcon className="h-4 w-4 text-amber-200" />
          {state.gold}
          <span className="text-[10px] font-normal text-amber-200/80">
            +{nextGold}
          </span>
        </span>
      </div>
      <div className="flex flex-col gap-2 sm:flex-row">
        <div className="flex gap-2 sm:w-40 sm:flex-col">
          <button
            className="btn flex-1 flex-col items-start gap-0 py-1.5"
            disabled={disabled || maxed || state.gold < XP_COST}
            onClick={onBuyXp}
          >
            <span>{maxed ? "Max level" : `Buy XP · ${XP_COST}g`}</span>
            <span className="text-[10px] font-normal text-slate-400">
              {maxed
                ? "Level 9"
                : `+${XP_PER_BUY} xp · ${state.xp}/${xpToNext(state.level)}`}
            </span>
          </button>
          <button
            className="btn flex-1 flex-col items-start gap-0 py-1.5"
            disabled={disabled || state.gold < REROLL_COST}
            onClick={onReroll}
          >
            <span>Reroll · {REROLL_COST}g</span>
            <span className="text-[10px] font-normal text-slate-400">
              New 5 units
            </span>
          </button>
        </div>

        <div className="grid flex-1 grid-cols-5 gap-1.5">
          {state.shop.map((defId, i) => {
            if (!defId) {
              return (
                <div
                  key={i}
                  className="min-h-28 rounded-lg border border-dashed border-slate-800 bg-slate-950/40"
                />
              );
            }
            const def = UNIT_BY_ID[defId];
            const canBuy =
              !disabled &&
              state.gold >= def.cost &&
              (state.pool[defId] ?? 0) > 0;
            return (
              <button
                key={i}
                disabled={!canBuy}
                onClick={() => onBuy(i)}
                className={`group relative flex min-h-28 flex-col justify-end overflow-hidden rounded-lg border-2 bg-slate-950/80 text-left transition enabled:hover:-translate-y-0.5 disabled:opacity-45 ${COST_COLOR[def.cost]}`}
                title={`${def.name}: ${def.origin} / ${def.role}`}
              >
                <span className="absolute inset-0">
                  {def.splash || def.photo ? (
                    <Image
                      src={def.splash ?? def.photo!}
                      alt=""
                      fill
                      sizes="240px"
                      draggable={false}
                      className="object-cover object-center transition group-enabled:group-hover:scale-105"
                    />
                  ) : (
                    <span className="flex h-full w-full items-start justify-center pt-2">
                      <UnitArt
                        def={def}
                        view="portrait"
                        className="h-20 w-20"
                        emojiClass="text-6xl"
                      />
                    </span>
                  )}
                  <span className="absolute inset-0 bg-gradient-to-t from-slate-950 via-slate-950/30 via-45% to-transparent" />
                </span>
                <span className="relative flex flex-col items-start gap-0.5 px-1.5 pb-1 text-[9px] text-slate-200 drop-shadow">
                  <span className="inline-flex items-center gap-1 text-sm font-semibold">
                    <TraitBadge trait={def.origin} />
                    {def.origin}
                  </span>
                  <span className="inline-flex items-center gap-0.5">
                    <TraitBadge trait={def.role} />
                    {def.role}
                  </span>
                </span>
                <span
                  className={`relative flex w-full items-center justify-between gap-1 px-1.5 py-1 text-[11px] font-semibold text-white ${COST_BAR[def.cost]}`}
                >
                  <span className="truncate">{def.name}</span>
                  <span className="inline-flex shrink-0 items-center gap-0.5 font-mono text-[10px] text-amber-200">
                    <CoinIcon className="h-3 w-3" />
                    {def.cost}
                  </span>
                </span>
              </button>
            );
          })}
        </div>

        <div className="flex gap-2 sm:w-28 sm:flex-col">
          <button
            className={`btn flex-1 ${state.locked ? "border-amber-400 text-amber-300" : ""}`}
            disabled={disabled}
            onClick={onToggleLock}
          >
            {state.locked ? "🔒 Locked" : "🔓 Lock"}
          </button>
          <button
            className="btn flex-1 border-rose-500/60 text-rose-200 enabled:hover:bg-rose-950/60"
            disabled={disabled || !sellLabel}
            onClick={onSellSelected}
          >
            {sellLabel ?? "Sell"}
          </button>
        </div>
      </div>
      {!disabled && (
        <p className="mt-1.5 text-center text-[10px] text-slate-500">
          Drag a unit here (or select it and press Sell) to sell it back to the
          pool.
        </p>
      )}
    </section>
  );
}
