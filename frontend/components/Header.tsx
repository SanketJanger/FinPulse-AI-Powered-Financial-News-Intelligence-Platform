"use client";

import { ThemeToggle } from "./ThemeToggle";
import type { SocketStatus } from "@/hooks/useFeedSocket";

const LABEL: Record<SocketStatus, string> = {
  open: "live",
  connecting: "connecting…",
  closed: "offline",
};

const DOT: Record<SocketStatus, string> = {
  open: "bg-bullish",
  connecting: "bg-neutral animate-pulse-soft",
  closed: "bg-bearish",
};

export function Header({ socket }: { socket: SocketStatus }) {
  return (
    <header className="sticky top-0 z-20 border-b border-border bg-background/80 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3">
        <div className="flex items-center gap-2.5">
          <span className="grid h-8 w-8 place-items-center rounded-lg bg-accent/15 text-accent">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
              <path d="M3 17l6-6 4 4 8-8" />
              <path d="M17 7h4v4" />
            </svg>
          </span>
          <div className="leading-tight">
            <p className="text-sm font-semibold">FinPulse</p>
            <p className="text-[11px] text-muted">Real-Time Financial News Intelligence</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <span className="hidden items-center gap-1.5 text-xs text-muted sm:flex">
            <span className={`h-2 w-2 rounded-full ${DOT[socket]}`} />
            {LABEL[socket]}
          </span>
          <ThemeToggle />
        </div>
      </div>
    </header>
  );
}
