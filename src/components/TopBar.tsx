import { FINAL_ROUND, MAX_LEVEL, START_HP } from "@/game/constants";
import { boardCount, xpToNext } from "@/game/reducer";
import type { GameState } from "@/game/types";

/** Player status: lives in the right sidebar so the arena gets the full page height. */
export function TopBar({ state }: { state: GameState }) {
  const need = xpToNext(state.level);
  const streakText = state.streak === 0 ? "—" : `${state.streak > 0 ? "W" : "L"}${Math.abs(state.streak)}`;
  return (
    <section className="rounded-xl border border-white/10 bg-[var(--panel)] p-3 text-sm">
      <div className="mb-3 flex items-center gap-2">
        <div className="bg-red-600 text-[10px]">ICON</div>
        <div className="bg-red-600">
          <h1 className="text-base font-bold leading-tight tracking-tight text-white">Tactics Arena</h1>
          <p className="text-[11px] text-slate-500">Auto-battler</p>
        </div>
      </div>

      <div>
        <div className="flex justify-between text-xs">
          <span className="text-slate-400">Health</span>
          <span className="font-mono text-slate-100">{state.hp}</span>
        </div>
        <div className="mt-1 h-2 overflow-hidden rounded bg-slate-800">
          <div className={`h-full transition-[width] ${state.hp > 40 ? "bg-emerald-400" : "bg-rose-400"}`} style={{ width: `${(state.hp / START_HP) * 100}%` }} />
        </div>
      </div>

      <div className="mt-3">
        <div className="flex justify-between text-xs">
          <span className="text-slate-400">Level {state.level}</span>
          <span className="font-mono text-slate-300">{state.level >= MAX_LEVEL ? "max" : `${state.xp}/${need}`}</span>
        </div>
        <div className="mt-1 h-2 overflow-hidden rounded bg-slate-800">
          <div className="h-full bg-sky-400 transition-[width]" style={{ width: `${need ? (state.xp / need) * 100 : 100}%` }} />
        </div>
      </div>

      <dl className="mt-3 grid grid-cols-3 gap-2 text-center">
        <div className="rounded-lg bg-slate-950/40 py-1.5">
          <dt className="text-[10px] uppercase tracking-wider text-slate-500">Round</dt>
          <dd className="font-mono text-base font-bold text-slate-100">
            {state.round}
            <span className="text-[10px] font-normal text-slate-500">/{FINAL_ROUND}</span>
          </dd>
        </div>
        <div className="rounded-lg bg-slate-950/40 py-1.5">
          <dt className="text-[10px] uppercase tracking-wider text-slate-500">Board</dt>
          <dd className="font-mono text-base font-bold text-slate-100">
            {boardCount(state.board)}
            <span className="text-[10px] font-normal text-slate-500">/{state.level}</span>
          </dd>
        </div>
        <div className="rounded-lg bg-slate-950/40 py-1.5">
          <dt className="text-[10px] uppercase tracking-wider text-slate-500">Streak</dt>
          <dd className={`font-mono text-base font-bold ${state.streak > 0 ? "text-emerald-300" : state.streak < 0 ? "text-rose-300" : "text-slate-300"}`}>{streakText}</dd>
        </div>
      </dl>

      {state.history.length > 0 && (
        <div className="mt-3 flex items-center gap-1" title="Recent rounds">
          {state.history.slice(-12).map((won, i) => (
            <span key={i} className={`h-2 w-2 rounded-full ${won ? "bg-emerald-400" : "bg-rose-500"}`} />
          ))}
        </div>
      )}
    </section>
  );
}
