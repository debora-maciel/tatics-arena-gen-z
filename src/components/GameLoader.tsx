"use client";

import dynamic from "next/dynamic";

const Loading = () => <div className="flex min-h-screen items-center justify-center text-sm text-slate-500">Loading your arena…</div>;

export const GameLoader = dynamic(() => import("./Game").then((m) => m.Game), { ssr: false, loading: Loading });
