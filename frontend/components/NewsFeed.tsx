"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { Article, Sentiment } from "@/lib/types";
import { ArticleCard } from "./ArticleCard";
import { ErrorState, Skeleton, EmptyState } from "./ui";

const FILTERS: { label: string; value: Sentiment | "all" }[] = [
  { label: "All", value: "all" },
  { label: "Bullish", value: "bullish" },
  { label: "Bearish", value: "bearish" },
  { label: "Neutral", value: "neutral" },
];

const PAGE_SIZE = 15;

export function NewsFeed({
  liveArticle,
}: {
  /** most recent article pushed over the websocket, or null */
  liveArticle: (Partial<Article> & { id: string; title: string }) | null;
}) {
  const [filter, setFilter] = useState<Sentiment | "all">("all");
  const [items, setItems] = useState<Article[]>([]);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [status, setStatus] = useState<"loading" | "ready" | "error" | "more">("loading");
  const [error, setError] = useState("");
  const seen = useRef<Set<string>>(new Set());
  const [freshIds, setFreshIds] = useState<Set<string>>(new Set());

  const load = useCallback(
    async (nextPage: number, replace: boolean) => {
      setStatus(replace ? "loading" : "more");
      setError("");
      try {
        const res = await api.getFeed({
          page: nextPage,
          pageSize: PAGE_SIZE,
          sentiment: filter === "all" ? undefined : filter,
        });
        setTotal(res.meta.total);
        setPage(res.meta.page);
        if (replace) {
          seen.current = new Set(res.items.map((a) => a.id));
          setItems(res.items);
        } else {
          const add = res.items.filter((a) => !seen.current.has(a.id));
          add.forEach((a) => seen.current.add(a.id));
          setItems((prev) => [...prev, ...add]);
        }
        setStatus("ready");
      } catch (e) {
        setError(e instanceof ApiError ? e.message : "Failed to load the feed");
        setStatus("error");
      }
    },
    [filter],
  );

  // (re)load page 1 whenever the filter changes
  useEffect(() => {
    load(1, true);
  }, [load]);

  // prepend a websocket-pushed article if it matches the current filter
  useEffect(() => {
    if (!liveArticle) return;
    const a = liveArticle as Article;
    if (seen.current.has(a.id)) return;
    if (filter !== "all" && a.sentiment !== filter) return;
    seen.current.add(a.id);
    setItems((prev) => [a, ...prev]);
    setTotal((t) => t + 1);
    setFreshIds((prev) => new Set(prev).add(a.id));
    const id = a.id;
    setTimeout(() => {
      setFreshIds((prev) => {
        const n = new Set(prev);
        n.delete(id);
        return n;
      });
    }, 6000);
  }, [liveArticle, filter]);

  return (
    <section>
      <div className="mb-3 flex items-center justify-between gap-3">
        <div className="flex flex-wrap gap-1.5">
          {FILTERS.map((f) => (
            <button
              key={f.value}
              onClick={() => setFilter(f.value)}
              className={`rounded-full px-3 py-1 text-xs font-medium transition ${
                filter === f.value
                  ? "bg-foreground text-background"
                  : "border border-border text-muted hover:text-foreground"
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
        {status === "ready" && (
          <span className="shrink-0 text-xs text-muted tabular-nums">
            {total} article{total === 1 ? "" : "s"}
          </span>
        )}
      </div>

      {status === "loading" && (
        <div className="space-y-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="rounded-xl border border-border bg-surface p-4">
              <Skeleton className="h-3 w-32" />
              <Skeleton className="mt-2 h-4 w-3/4" />
              <Skeleton className="mt-2 h-3 w-full" />
              <Skeleton className="mt-1 h-3 w-2/3" />
            </div>
          ))}
        </div>
      )}

      {status === "error" && <ErrorState message={error} onRetry={() => load(1, true)} />}

      {status !== "loading" && status !== "error" && items.length === 0 && (
        <EmptyState>No articles match this filter yet.</EmptyState>
      )}

      {items.length > 0 && (
        <div className="space-y-3">
          {items.map((a) => (
            <ArticleCard key={a.id} article={a} highlight={freshIds.has(a.id)} />
          ))}
        </div>
      )}

      {items.length > 0 && items.length < total && (
        <button
          onClick={() => load(page + 1, false)}
          disabled={status === "more"}
          className="mt-4 w-full rounded-lg border border-border bg-surface py-2.5 text-sm font-medium text-muted transition hover:text-foreground disabled:opacity-50"
        >
          {status === "more" ? "Loading…" : `Load more (${total - items.length} left)`}
        </button>
      )}
    </section>
  );
}
