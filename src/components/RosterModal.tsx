"use client";

import { useEffect } from "react";
import { COST_BAR, COST_COLOR, STAR_AD, STAR_HP } from "@/game/constants";
import { ABILITY_TEXT, UNITS } from "@/game/data/units";
import type { Cost } from "@/game/types";
import { TraitIcon } from "./TraitIcons";
import { UnitArt } from "./UnitArt";

const COSTS: Cost[] = [1, 2, 3, 4, 5];

/** Every unit in the game, grouped by cost. */
export function RosterModal({ onClose }: { onClose: () => void }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/70 p-4 backdrop-blur-sm sm:p-8" onClick={onClose}>
      <div
        role="dialog"
        aria-modal
        aria-label="All characters"
        className="w-full max-w-5xl rounded-2xl border border-white/10 bg-slate-950/95 p-4 shadow-2xl sm:p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center justify-between">
          <div>
            <h2 className="text-lg font-bold text-white">Characters</h2>
            <p className="text-xs text-slate-400">{UNITS.length} units across five cost tiers. Stats shown at 1★; each star multiplies HP ×{STAR_HP} and damage ×{STAR_AD}.</p>
          </div>
          <button className="btn" onClick={onClose}>
            Close ✕
          </button>
        </div>

        {COSTS.map((cost) => {
          const tier = UNITS.filter((u) => u.cost === cost);
          if (tier.length === 0) return null;
          return (
            <section key={cost} className="mb-5">
              <h3 className={`mb-2 inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-semibold text-white ${COST_BAR[cost]}`}>
                {cost}-cost · {tier.length}
              </h3>
              <ul className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                {tier.map((def) => (
                  <li key={def.id} className={`flex gap-3 rounded-xl border-2 bg-slate-900/70 p-2 ${COST_COLOR[def.cost]}`}>
                    <span className="flex h-16 w-16 shrink-0 items-center justify-center overflow-hidden rounded-lg bg-slate-950">
                      <UnitArt def={def} view="portrait" className="h-14 w-14" emojiClass="text-4xl" />
                    </span>
                    <div className="min-w-0 flex-1 text-xs">
                      <div className="truncate text-sm font-semibold text-white">{def.name}</div>
                      <div className="flex flex-wrap gap-x-2 text-slate-400">
                        <span className="inline-flex items-center gap-1">
                          <TraitIcon trait={def.origin} className="h-3 w-3" />
                          {def.origin}
                        </span>
                        <span className="inline-flex items-center gap-1">
                          <TraitIcon trait={def.role} className="h-3 w-3" />
                          {def.role}
                        </span>
                      </div>
                      <div className="mt-1 font-mono text-[10px] text-slate-300">
                        {def.hp} HP · {def.ad} AD · {def.atkSpeed.toFixed(2)} AS · {def.range} range · {def.armor} armor
                      </div>
                      <div className="mt-1 text-[11px] text-sky-200" title={ABILITY_TEXT[def.ability.kind]}>
                        {def.ability.name} <span className="text-slate-500">· {Math.round(def.ability.ratio * 100)}%</span>
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
            </section>
          );
        })}
      </div>
    </div>
  );
}
