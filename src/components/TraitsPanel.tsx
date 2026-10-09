import { COST_COLOR } from "@/game/constants";
import { UNITS } from "@/game/data/units";
import type { ActiveTrait } from "@/game/synergies";
import type { Slot } from "@/game/types";
import { TraitBadge } from "./TraitIcons";
import { UnitArt } from "./UnitArt";

/** Hexagon rim + icon colour per tier: inactive, bronze, silver, gold. */
const TIER_RIM = ["bg-slate-600 text-slate-400", "bg-amber-700 text-amber-300", "bg-slate-300 text-slate-100", "bg-yellow-400 text-yellow-200"];

interface Props {
  traits: ActiveTrait[];
  title: string;
  emptyText: string;
  /** The player's board, so the hover card can mark which champions of a trait are fielded. */
  board: Slot[];
}

export function TraitsPanel({ traits, title, emptyText, board }: Props) {
  const fielded = new Set(board.flatMap((u) => (u ? [u.defId] : [])));

  return (
    <section aria-label={title} className="p-1">
      {traits.length === 0 ? (
        <p className="px-2 py-1 text-xs text-slate-500">{emptyText}</p>
      ) : (
        <ul className="w-fit space-y-1">
          {traits.map(({ def, count, tier }) => {
            const next = def.thresholds.find((th) => th > count) ?? def.thresholds[def.thresholds.length - 1];
            const style = TIER_RIM[Math.min(tier, 3)];
            return (
              <li key={def.name} className="group relative flex items-center gap-2.5 rounded-lg py-1 pl-1 pr-3 hover:bg-white/5">
                <TraitBadge trait={def.name} className={`h-10 w-10 ${style}`} iconClass="h-5 w-5" rimClass="" />
                <div className="leading-tight">
                  <div className={`text-sm font-semibold ${tier > 0 ? "text-white" : "text-slate-400"}`}>{def.name}</div>
                  <div className={`font-mono text-xs ${tier > 0 ? "text-amber-200" : "text-slate-500"}`}>
                    {count} / {next}
                  </div>
                </div>
                {/* Hover card with the bonus details. */}
                <div className="pointer-events-none absolute left-full top-0 z-30 ml-2 hidden w-64 rounded-lg border border-white/15 bg-slate-950/95 p-2 text-[11px] text-slate-200 shadow-xl group-hover:block">
                  <p className="font-semibold text-white">{def.name}</p>
                  <p className="mt-0.5 text-slate-300">{def.description}</p>
                  <ul className="mt-1.5 space-y-0.5">
                    {def.thresholds.map((th, i) => (
                      <li key={th} className={i + 1 === tier ? "font-semibold text-amber-200" : "text-slate-400"}>
                        ({th}) {def.tiers[i]}
                      </li>
                    ))}
                  </ul>
                  {/* Every champion with this trait, cheapest first; fielded ones are lit up. */}
                  <ul className="mt-2 flex flex-wrap gap-1 border-t border-white/10 pt-2">
                    {UNITS.filter((u) => u.origin === def.name || u.role === def.name)
                      .sort((a, b) => a.cost - b.cost || a.name.localeCompare(b.name))
                      .map((u) => (
                        <li
                          key={u.id}
                          className={`flex h-9 w-9 items-center justify-center overflow-hidden rounded-md border bg-slate-900 ${COST_COLOR[u.cost]} ${
                            fielded.has(u.id) ? "" : "opacity-40 grayscale"
                          }`}
                          title={`${u.name} (${u.cost}-cost)`}
                        >
                          <UnitArt def={u} view="portrait" className="h-8 w-8" emojiClass="text-xl" />
                        </li>
                      ))}
                  </ul>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
