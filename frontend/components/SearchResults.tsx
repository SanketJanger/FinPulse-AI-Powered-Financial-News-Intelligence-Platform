"use client";

import type { SearchResponse } from "@/lib/types";
import { ArticleCard } from "./ArticleCard";
import { ErrorState, Skeleton, EmptyState } from "./ui";

export function SearchResults({
  query,
  data,
  status,
  error,
  onRetry,
}: {
  query: string;
  data: SearchResponse | null;
  status: "loading" | "ready" | "error";
  error: string;
  onRetry: () => void;
}) {
  return (
    <section>
      <p className="mb-3 text-sm text-muted">
        Semantic results for{" "}
        <span className="font-medium text-foreground">“{query}”</span>
        {data && ` · ${data.count} match${data.count === 1 ? "" : "es"}`}
      </p>

      {status === "loading" && (
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="rounded-xl border border-border bg-surface p-4">
              <Skeleton className="h-3 w-40" />
              <Skeleton className="mt-2 h-4 w-2/3" />
              <Skeleton className="mt-2 h-3 w-full" />
            </div>
          ))}
        </div>
      )}

      {status === "error" && <ErrorState message={error} onRetry={onRetry} />}

      {status === "ready" && data && data.hits.length === 0 && (
        <EmptyState>Nothing similar found. Try different wording.</EmptyState>
      )}

      {status === "ready" && data && data.hits.length > 0 && (
        <div className="space-y-3">
          {data.hits.map((h) => (
            <ArticleCard key={h.article.id} article={h.article} score={h.score} />
          ))}
        </div>
      )}
    </section>
  );
}
