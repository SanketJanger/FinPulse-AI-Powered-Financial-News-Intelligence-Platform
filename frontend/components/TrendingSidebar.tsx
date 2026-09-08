"use client";

import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { TrendingResponse } from "@/lib/types";
import { Card, SectionTitle, Skeleton, ErrorState, EmptyState } from "./ui";

export function TrendingSidebar() {
  const [data, setData] = useState<TrendingResponse | null>(null);
  const [error, setError] = useState("");

  const load = () => {
    setError("");
    setData(null);
    api
      .getTrending(24, 8)
      .then(setData)
      .catch((e: ApiError) => setError(e.message));
  };

  useEffect(load, []);

  const max = data?.top_sources[0]?.count ?? 1;

  return (
    <Card className="p-4">
      <div className="mb-3 flex items-baseline justify-between">
        <SectionTitle>Trending sources</SectionTitle>
        <span className="text-[11px] text-muted">24h</span>
      </div>

      {!data && !error && (
        <div className="space-y-2.5">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-6 w-full" />
          ))}
        </div>
      )}

      {error && <ErrorState message={error} onRetry={load} />}

      {data && data.top_sources.length === 0 && (
        <EmptyState>No articles in the last 24h.</EmptyState>
      )}

      {data && data.top_sources.length > 0 && (
        <ol className="space-y-2">
          {data.top_sources.map((s) => (
            <li key={s.source}>
              <div className="mb-1 flex items-center justify-between gap-2 text-sm">
                <span className="truncate">{s.source}</span>
                <span className="shrink-0 tabular-nums text-muted">{s.count}</span>
              </div>
              <div className="h-1.5 overflow-hidden rounded-full bg-border">
                <div
                  className="h-full rounded-full bg-accent"
                  style={{ width: `${Math.max(6, (s.count / max) * 100)}%` }}
                />
              </div>
            </li>
          ))}
        </ol>
      )}
    </Card>
  );
}
