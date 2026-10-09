"use client";

import { useEffect, useReducer, useSyncExternalStore } from "react";
import { newGame, reducer } from "@/game/reducer";
import { getServerStats, getStats, loadGame, recordGame, saveGame, subscribeStats } from "@/game/storage";

/**
 * Game state with localStorage persistence. Must only be used in a client-only tree
 * (see GameLoader), because the initial state is read from localStorage synchronously.
 */
export function useGame() {
  const [state, dispatch] = useReducer(reducer, null, () => loadGame() ?? newGame());
  const stats = useSyncExternalStore(subscribeStats, getStats, getServerStats);

  // Persist every planning-phase change; a finished game is also written to the records.
  useEffect(() => {
    if (state.phase === "combat") return;
    saveGame(state);
    if (state.phase === "gameover" || state.phase === "victory") recordGame(state);
  }, [state]);

  return { state, dispatch, stats };
}
