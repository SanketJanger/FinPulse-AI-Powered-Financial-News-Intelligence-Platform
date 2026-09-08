"use client";

import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import type { Article, SearchResponse } from "@/lib/types";
import { useFeedSocket } from "@/hooks/useFeedSocket";
import { Header } from "@/components/Header";
import { AlertsBanner } from "@/components/AlertsBanner";
import { SearchBar } from "@/components/SearchBar";
import { NewsFeed } from "@/components/NewsFeed";
import { SearchResults } from "@/components/SearchResults";
import { TrendingSidebar } from "@/components/TrendingSidebar";
import { SentimentStats } from "@/components/SentimentStats";

type LiveArticle = (Partial<Article> & { id: string; title: string }) | null;

function Dashboard() {
  const initialQuery = useSearchParams().get("q") ?? "";

  const [live, setLive] = useState<LiveArticle>(null);
  const { status: socket } = useFeedSocket({ onArticle: (a) => setLive({ ...a }) });

  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResponse | null>(null);
  const [searchStatus, setSearchStatus] = useState<
    "idle" | "loading" | "ready" | "error"
  >("idle");
  const [searchError, setSearchError] = useState("");
  const lastQuery = useRef("");

  const runSearch = useCallback(async (q: string) => {
    lastQuery.current = q;
    setQuery(q);
    setSearchStatus("loading");
    setSearchError("");
    try {
      const res = await api.search(q, 10);
      setResults(res);
      setSearchStatus("ready");
    } catch (e) {
      setSearchError(
        e instanceof ApiError
          ? e.status === 503
            ? "Semantic search is unavailable — the V3 embedder / ChromaDB isn't running."
            : e.message
          : "Search failed",
      );
      setSearchStatus("error");
    }
  }, []);

  const clearSearch = useCallback(() => {
    setQuery("");
    setResults(null);
    setSearchStatus("idle");
    setSearchError("");
  }, []);

  // run a search from ?q= on first load
  useEffect(() => {
    if (initialQuery.trim().length >= 2) runSearch(initialQuery.trim());
  }, [initialQuery, runSearch]);

  const searching = searchStatus !== "idle";

  return (
    <div className="min-h-screen">
      <Header socket={socket} />
      <AlertsBanner />

      <main className="mx-auto max-w-6xl px-4 py-5">
        <div className="mb-5">
          <SearchBar
            key={initialQuery}
            initialValue={initialQuery}
            onSearch={runSearch}
            onClear={clearSearch}
            loading={searchStatus === "loading"}
            active={searching}
          />
        </div>

        <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
          <div className="min-w-0">
            {searching ? (
              <SearchResults
                query={query}
                data={results}
                status={searchStatus as "loading" | "ready" | "error"}
                error={searchError}
                onRetry={() => runSearch(lastQuery.current)}
              />
            ) : (
              <NewsFeed liveArticle={live} />
            )}
          </div>

          <aside className="space-y-6 lg:sticky lg:top-20 lg:self-start">
            <SentimentStats />
            <TrendingSidebar />
          </aside>
        </div>
      </main>

      <footer className="mx-auto max-w-6xl px-4 py-6 text-center text-xs text-muted">
        FinPulse · FinBERT sentiment · Groq summaries · MiniLM semantic search
      </footer>
    </div>
  );
}

export default function Page() {
  return (
    <Suspense fallback={<div className="p-8 text-sm text-muted">Loading…</div>}>
      <Dashboard />
    </Suspense>
  );
}
