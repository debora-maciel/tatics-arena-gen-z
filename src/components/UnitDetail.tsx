import { COST_COLOR, STAR_AD, STAR_HP } from "@/game/constants";
import { ABILITY_TEXT, UNIT_BY_ID } from "@/game/data/units";
import { sellValue } from "@/game/reducer";
import type { Unit } from "@/game/types";
import { TraitIcon } from "./TraitIcons";
import { UnitArt } from "./UnitArt";
import { Stars } from "./UnitChip";

export function UnitDetail({ unit, onSell, disabled }: { unit: Unit | null; onSell: () => void; disabled: boolean }) {
  if (!unit) {
    return (
      <section className="rounded-xl border border-white/10 bg-[var(--panel)] p-3 text-xs text-slate-500">
        <h2 className="mb-1 text-xs font-semibold uppercase tracking-wider text-slate-400">Unit</h2>
        Click a unit on the bench or board to inspect it. Click a second slot to move it, or drag it.
      </section>
    );
  }
  const def = UNIT_BY_ID[unit.defId];
  const hp = Math.round(def.hp * Math.pow(STAR_HP, unit.star - 1));
  const ad = Math.round(def.ad * Math.pow(STAR_AD, unit.star - 1));
  const row = (label: string, value: string | number) => (
    <div className="flex justify-between">
      <dt className="text-slate-400">{label}</dt>
      <dd className="font-mono text-slate-100">{value}</dd>
    </div>
  );
  return (
    <section className="rounded-xl border border-white/10 bg-[var(--panel)] p-3 text-xs">
      <div className="flex items-center gap-3">
        <span className={`flex h-12 w-12 items-center justify-center overflow-hidden rounded-lg border-2 bg-slate-950 ${COST_COLOR[def.cost]}`}>
          <UnitArt def={def} view="portrait" className="h-11 w-11" emojiClass="text-3xl" />
        </span>
        <div>
          <div className="text-sm font-semibold text-white">
            {def.name} <Stars star={unit.star} className="ml-1 text-xs" />
          </div>
          <div className="flex flex-wrap items-center gap-x-2 text-slate-400">
            <span className="inline-flex items-center gap-1">
              <TraitIcon trait={def.origin} />
              {def.origin}
            </span>
            <span className="inline-flex items-center gap-1">
              <TraitIcon trait={def.role} />
              {def.role}
            </span>
            <span>{def.cost}-cost</span>
          </div>
        </div>
      </div>
      <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1">
        {row("Health", hp)}
        {row("Damage", ad)}
        {row("Atk speed", def.atkSpeed.toFixed(2))}
        {row("Range", def.range)}
        {row("Armor", def.armor)}
        {row("Mana", def.mana)}
      </dl>
      <div className="mt-3 rounded-lg border border-slate-800 bg-slate-950/60 p-2">
        <div className="font-semibold text-sky-200">{def.ability.name}</div>
        <p className="mt-0.5 text-slate-400">
          {ABILITY_TEXT[def.ability.kind]} Power: {Math.round(def.ability.ratio * 100)}% of damage.
        </p>
      </div>
      <button className="btn mt-3 w-full border-rose-500/60 text-rose-200 enabled:hover:bg-rose-950/60" disabled={disabled} onClick={onSell}>
        Sell for {sellValue(unit)}g
      </button>
    </section>
  );
}
