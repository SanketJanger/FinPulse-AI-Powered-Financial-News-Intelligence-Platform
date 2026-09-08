"use client";

import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { SentimentDayStats, SentimentStatsResponse } from "@/lib/types";
import { Card, SectionTitle, Skeleton, ErrorState, EmptyState } from "./ui";
import { shortDate } from "@/lib/format";

const SERIES = [
  { key: "bullish", label: "Bullish", color: "rgb(var(--bullish))" },
  { key: "bearish", label: "Bearish", color: "rgb(var(--bearish))" },
  { key: "neutral", label: "Neutral", color: "rgb(var(--neutral))" },
] as const;

type Hover = { day: string; label: string; count: number; pct: number; color: string } | null;

export function SentimentStats() {
  const [data, setData] = useState<SentimentStatsResponse | null>(null);
  const [error, setError] = useState("");
  const [hover, setHover] = useState<Hover>(null);

  const load = () => {
    setError("");
    setData(null);
    api
      .getSentimentStats(7)
      .then(setData)
      .catch((e: ApiError) => setError(e.message));
  };
  useEffect(load, []);

  const days = data?.days ?? [];

  return (
    <Card className="p-4">
      <div className="mb-1 flex items-baseline justify-between">
        <SectionTitle>Sentiment by day</SectionTitle>
        <span className="text-[11px] text-muted">7d · scored articles</span>
      </div>

      {/* legend — identity is never colour-alone */}
      <div className="mb-3 flex gap-3 text-[11px] text-muted">
        {SERIES.map((s) => (
          <span key={s.key} className="inline-flex items-center gap-1">
            <span className="h-2 w-2 rounded-sm" style={{ background: s.color }} />
            {s.label}
          </span>
        ))}
      </div>

      {!data && !error && (
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-7 w-full" />
          ))}
        </div>
      )}

      {error && <ErrorState message={error} onRetry={load} />}
      {data && days.length === 0 && (
        <EmptyState>No scored articles in the last 7 days.</EmptyState>
      )}

      {days.length > 0 && (
        <>
          <div className="relative space-y-2.5">
            {days.map((d) => (
              <DayRow key={d.date} d={d} onHover={setHover} />
            ))}
            {hover && (
              <div className="pointer-events-none absolute right-0 top-0 z-10 rounded-md border border-border bg-surface px-2 py-1 text-xs shadow-sm">
                <span
                  className="mr-1 inline-block h-2 w-2 rounded-sm align-middle"
                  style={{ background: hover.color }}
                />
                {hover.label}: <span className="font-medium tabular-nums">{hover.count}</span>{" "}
                <span className="text-muted">({hover.pct.toFixed(0)}%)</span>
              </div>
            )}
          </div>

          <details className="mt-3 text-xs text-muted">
            <summary className="cursor-pointer select-none hover:text-foreground">
              Table view
            </summary>
            <table className="mt-2 w-full border-collapse text-left tabular-nums">
              <thead>
                <tr className="text-[11px] uppercase tracking-wide">
                  <th className="py-1 pr-2 font-medium">Day</th>
                  <th className="py-1 px-2 font-medium">Bull</th>
                  <th className="py-1 px-2 font-medium">Bear</th>
                  <th className="py-1 px-2 font-medium">Neut</th>
                  <th className="py-1 pl-2 font-medium">Total</th>
                </tr>
              </thead>
              <tbody>
                {days.map((d) => (
                  <tr key={d.date} className="border-t border-border">
                    <td className="py-1 pr-2">{shortDate(d.date)}</td>
                    <td className="py-1 px-2">{d.bullish}</td>
                    <td className="py-1 px-2">{d.bearish}</td>
                    <td className="py-1 px-2">{d.neutral}</td>
                    <td className="py-1 pl-2 font-medium text-foreground">{d.total}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </details>
        </>
      )}
    </Card>
  );
}

function DayRow({
  d,
  onHover,
}: {
  d: SentimentDayStats;
  onHover: (h: Hover) => void;
}) {
  const total = d.total || 1;
  return (
    <div>
      <div className="mb-1 flex justify-between text-[11px] text-muted">
        <span>{shortDate(d.date)}</span>
        <span className="tabular-nums">{d.total}</span>
      </div>
      <div
        className="flex h-5 gap-0.5 overflow-hidden rounded"
        onMouseLeave={() => onHover(null)}
      >
        {SERIES.map((s) => {
          const count = d[s.key];
          if (count === 0) return null;
          const pct = (count / total) * 100;
          return (
            <div
              key={s.key}
              className="grid place-items-center text-[10px] font-medium text-white/95"
              style={{ width: `${pct}%`, background: s.color, minWidth: count > 0 ? 3 : 0 }}
              onMouseEnter={() =>
                onHover({ day: d.date, label: s.label, count, pct, color: s.color })
              }
            >
              {pct > 12 ? count : ""}
            </div>
          );
        })}
      </div>
    </div>
  );
}
