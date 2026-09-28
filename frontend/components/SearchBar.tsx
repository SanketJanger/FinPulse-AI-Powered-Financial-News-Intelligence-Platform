"use client";

import { useState } from "react";

export function SearchBar({
  onSearch,
  onClear,
  loading,
  active,
  initialValue = "",
}: {
  onSearch: (q: string) => void;
  onClear: () => void;
  loading: boolean;
  active: boolean;
  initialValue?: string;
}) {
  const [value, setValue] = useState(initialValue);

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const q = value.trim();
    if (q.length >= 2) onSearch(q);
  };

  const clear = () => {
    setValue("");
    onClear();
  };

  return (
    <form onSubmit={submit} className="relative">
      <svg
        className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted"
        width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
      >
        <circle cx="11" cy="11" r="7" />
        <path d="m21 21-4.3-4.3" />
      </svg>
      <input
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder="Semantic search — e.g. “Fed impact on tech stocks”"
        className="w-full rounded-lg border border-border bg-surface py-2.5 pl-9 pr-24 text-sm outline-none ring-accent/40 placeholder:text-muted focus:ring-2"
      />
      <div className="absolute right-1.5 top-1/2 flex -translate-y-1/2 items-center gap-1">
        {(active || value) && (
          <button
            type="button"
            onClick={clear}
            className="rounded-md px-2 py-1 text-xs text-muted hover:text-foreground"
          >
            clear
          </button>
        )}
        <button
          type="submit"
          disabled={loading || value.trim().length < 2}
          className="rounded-md bg-accent px-3 py-1.5 text-xs font-medium text-white disabled:opacity-40"
        >
          {loading ? "…" : "Search"}
        </button>
      </div>
    </form>
  );
}
