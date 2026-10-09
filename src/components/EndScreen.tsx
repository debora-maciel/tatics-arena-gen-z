import type { GameState } from "@/game/types";

export function EndScreen({ state, onNewGame }: { state: GameState; onNewGame: () => void }) {
  const won = state.phase === "victory";
  const wins = state.history.filter(Boolean).length;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm">
      <div className="w-full max-w-md rounded-2xl border border-slate-700 bg-slate-900 p-6 text-center shadow-2xl">
        <div className="text-5xl">{won ? "🏆" : "💀"}</div>
        <h2 className="mt-3 text-2xl font-bold text-white">{won ? "Arena champion!" : "Defeated"}</h2>
        <p className="mt-2 text-sm text-slate-300">
          {won
            ? `You cleared all ${state.round} rounds at level ${state.level}.`
            : `You fell on round ${state.round} at level ${state.level}.`}
        </p>
        <dl className="mt-4 grid grid-cols-3 gap-2 text-xs">
          <div className="rounded-lg bg-slate-950/60 p-2">
            <dt className="text-slate-500">Rounds won</dt>
            <dd className="font-mono text-lg text-emerald-300">{wins}</dd>
          </div>
          <div className="rounded-lg bg-slate-950/60 p-2">
            <dt className="text-slate-500">Rounds lost</dt>
            <dd className="font-mono text-lg text-rose-300">{state.history.length - wins}</dd>
          </div>
          <div className="rounded-lg bg-slate-950/60 p-2">
            <dt className="text-slate-500">Gold left</dt>
            <dd className="font-mono text-lg text-amber-300">{state.gold}</dd>
          </div>
        </dl>
        <button className="btn mt-6 w-full border-sky-400 bg-sky-500/20 text-sky-100 hover:bg-sky-500/30" onClick={onNewGame}>
          Play again
        </button>
      </div>
    </div>
  );
}
