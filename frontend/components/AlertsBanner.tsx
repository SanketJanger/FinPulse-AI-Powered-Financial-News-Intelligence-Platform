"use client";

import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { AlertsResponse } from "@/lib/types";
import { relativeTime } from "@/lib/format";

export function AlertsBanner() {
  const [data, setData] = useState<AlertsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    let alive = true;
    api
      .getAlerts(6)
      .then((d) => alive && setData(d))
      .catch((e: ApiError) => alive && setError(e.message));
    return () => {
      alive = false;
    };
  }, []);

  if (error || dismissed || !data || data.count === 0) return null;

  return (
    <div className="border-b border-amber-500/30 bg-amber-500/10">
      <div className="mx-auto flex max-w-6xl items-start gap-3 px-4 py-2.5">
        <span className="mt-0.5 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-amber-600 dark:text-amber-400">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4">
            <path d="M12 9v4M12 17h.01M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z" />
          </svg>
          {data.count} high-impact
        </span>
        <ul className="flex-1 space-y-0.5 text-sm">
          {data.alerts.slice(0, 3).map((a) => (
            <li key={a.id} className="truncate">
              <a
                href={a.url}
                target="_blank"
                rel="noopener noreferrer"
                className="hover:underline"
              >
                <span className="font-medium tabular-nums text-amber-600 dark:text-amber-400">
                  {a.impact_score}
                </span>{" "}
                {a.title}
              </a>
              <span className="ml-1 text-xs text-muted">
                · {a.source} · {relativeTime(a.published_at || a.fetched_at)}
              </span>
            </li>
          ))}
        </ul>
        <button
          onClick={() => setDismissed(true)}
          aria-label="Dismiss alerts"
          className="text-muted hover:text-foreground"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M18 6 6 18M6 6l12 12" />
          </svg>
        </button>
      </div>
    </div>
  );
}
