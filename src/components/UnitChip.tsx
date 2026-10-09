import { COST_COLOR, STAR_HP } from "@/game/constants";
import { UNIT_BY_ID } from "@/game/data/units";
import type { Unit } from "@/game/types";
import { TraitBadge } from "./TraitIcons";
import { UnitArt, type ArtView } from "./UnitArt";
import { UnitModel } from "./UnitModel";

/** HP per divider on a health bar, as on the official TFT bars. */
export const HP_SEGMENT = 200;

/** A stat bar. With `segment`, thin dark dividers mark every `segment` points of `max`. */
export function Bar({ value, max, className, segment }: { value: number; max: number; className: string; segment?: number }) {
  const pct = Math.max(0, Math.min(100, (value / max) * 100));
  const step = segment && max > 0 ? (segment / max) * 100 : 0;
  return (
    <div className={`relative w-full overflow-hidden rounded bg-black/60 ${segment ? "h-1.5" : "h-1"}`}>
      <div className={`h-full transition-[width] duration-150 ${className}`} style={{ width: `${pct}%` }} />
      {step > 0 && step < 100 && (
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0"
          style={{ background: `repeating-linear-gradient(90deg, transparent 0, transparent calc(${step}% - 1px), rgba(0,0,0,0.75) calc(${step}% - 1px), rgba(0,0,0,0.75) ${step}%)` }}
        />
      )}
    </div>
  );
}

export function Stars({ star, className = "" }: { star: number; className?: string }) {
  return (
    <span className={`text-[10px] leading-none tracking-tighter text-amber-300 ${className}`} aria-label={`${star} star`}>
      {"★".repeat(star)}
    </span>
  );
}

interface ChipProps {
  unit: Unit;
  selected?: boolean;
  dim?: boolean;
  /** Which render to show for units with art. Bench/shop use the portrait; the board uses the 3/4 view. */
  view?: ArtView;
  /** Show the hover card below the unit instead of above (for the top rows, so it is not clipped). */
  tipBelow?: boolean;
  /** Art size in px for arenas that size units per row; omitted → responsive size classes. */
  size?: number;
  /** Show full HP and starting mana bars, as during combat (board and bench units). */
  bars?: boolean;
}

/**
 * A unit on the planning board or bench. The character stands on a `.stand` plate whose
 * bottom edge sits at the cell's centre, so in the perspective view its feet touch the ground
 * there. Hovering shows a card with name, traits and ability.
 */
export function UnitChip({ unit, selected = false, dim = false, view = "portrait", tipBelow = false, size, bars = false }: ChipProps) {
  const def = UNIT_BY_ID[unit.defId];
  const fade = dim ? "opacity-70" : "";
  // Base max HP for the planning bar (star multiplier only; synergies apply in combat).
  const maxHp = Math.round(def.hp * Math.pow(STAR_HP, unit.star - 1));
  const modelStyle = size ? { width: size, height: size } : undefined;
  const artStyle = size ? { width: size * 0.5, height: size * 0.5 } : undefined;
  const modelClass = size ? "" : "h-40 w-40 sm:h-52 sm:w-52";
  const artClass = size ? "" : def.art && view !== "portrait" ? "h-24 w-24 sm:h-[7.5rem] sm:w-[7.5rem]" : "h-9 w-9 sm:h-11 sm:w-11";
  return (
    <div className="p3d group relative h-full w-full">
      <div className="stand absolute inset-x-0 bottom-1/2 flex h-full flex-col items-center justify-end gap-0.5">
        <span className={`flex flex-col items-center gap-0.5 ${fade}`}>
          {/* Badges sit just above the head: the render leaves ~20% empty canvas above it, so they overlap that space. */}
          <div className="relative z-10 flex flex-col items-center gap-0.5" style={size && def.model ? { marginBottom: -size * 0.2 } : undefined}>
            <Stars star={unit.star} />
            {bars && (
              <div className="w-3/4 space-y-0.5" style={size ? { width: size * 0.45 } : undefined}>
                <Bar value={maxHp} max={maxHp} segment={HP_SEGMENT} className={dim ? "bg-rose-400" : "bg-emerald-400"} />
                <Bar value={0} max={1} className="bg-sky-300" />
              </div>
            )}
          </div>
          {def.model && view !== "portrait" ? (
            // Live model facing the viewer, from the camera angle that matches the arena view.
            <UnitModel id={unit.uid} def={def} yaw={0} fallbackView={view} pose={view === "board" ? "board" : "front"} selected={selected} className={modelClass} style={modelStyle} emojiClass="text-2xl sm:text-3xl" />
          ) : (
            <UnitArt def={def} view={view} selected={selected} className={artClass} style={artStyle} emojiClass="text-2xl sm:text-3xl" />
          )}
        </span>
        {/* Hover card. Lives on the stand plate so it stays upright in the perspective view. */}
        <div
          role="tooltip"
          className={`pointer-events-none absolute left-1/2 z-30 hidden w-40 -translate-x-1/2 flex-col gap-1 rounded-lg border border-white/15 bg-slate-950/95 p-2 text-left text-[11px] text-slate-200 shadow-xl group-hover:flex ${
            tipBelow ? "top-full mt-1" : "bottom-full mb-1"
          }`}
        >
          <div className="flex items-center justify-between gap-2">
            <span className={`truncate font-semibold ${COST_COLOR[def.cost]}`}>{def.name}</span>
            <Stars star={unit.star} />
          </div>
          <div className="flex items-center gap-1.5 text-slate-300">
            <TraitBadge trait={def.origin} className="h-5 w-5" iconClass="h-3 w-3" />
            {def.origin}
            <TraitBadge trait={def.role} className="ml-1 h-5 w-5" iconClass="h-3 w-3" />
            {def.role}
          </div>
          <div className="text-sky-200">
            {def.ability.name} <span className="text-slate-500">· {def.cost}-cost</span>
          </div>
        </div>
      </div>
    </div>
  );
}
