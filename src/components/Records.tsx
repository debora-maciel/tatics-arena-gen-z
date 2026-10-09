"use client";

import { useState } from "react";
import type { Stats } from "@/game/types";

interface Props {
  stats: Stats | null;
  onNewGame: () => void;
  onReset: () => void;
  onShowRoster: () => void;
}

export function Records({ stats, onNewGame, onReset, onShowRoster }: Props) {
  const [confirm, setConfirm] = useState<"new" | "reset" | null>(null);
  const ask = (which: "new" | "reset", go: () => void) => {
    if (confirm === which) {
      setConfirm(null);
      go();
    } else {
      setConfirm(which);
      setTimeout(() => setConfirm((c) => (c === which ? null : c)), 2500);
    }
  };
  return (
    <section className="rounded-xl border border-white/10 bg-[var(--panel)] p-3 text-xs">
      <h2 className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-400">Records</h2>
      <dl className="grid grid-cols-2 gap-x-4 gap-y-1">
        <dt className="text-slate-400">Games</dt>
        <dd className="text-right font-mono text-slate-100">{stats?.games ?? 0}</dd>
        <dt className="text-slate-400">Wins</dt>
        <dd className="text-right font-mono text-slate-100">{stats?.wins ?? 0}</dd>
        <dt className="text-slate-400">Best round</dt>
        <dd className="text-right font-mono text-slate-100">{stats?.bestRound ?? 0}</dd>
        <dt className="text-slate-400">Best level</dt>
        <dd className="text-right font-mono text-slate-100">{stats?.bestLevel ?? 0}</dd>
      </dl>
      <div className="mt-3 flex gap-2">
        <button className="btn flex-1" onClick={() => ask("new", onNewGame)}>
          {confirm === "new" ? "Sure? Click again" : "New game"}
        </button>
        <button className="btn flex-1 text-slate-400" onClick={() => ask("reset", onReset)}>
          {confirm === "reset" ? "Sure?" : "Reset records"}
        </button>
      </div>
      <button className="btn mt-2 w-full" onClick={onShowRoster}>
        📖 All characters
      </button>
      <p className="mt-2 text-[10px] text-slate-500">Progress is saved in this browser automatically.</p>
    </section>
  );
}
