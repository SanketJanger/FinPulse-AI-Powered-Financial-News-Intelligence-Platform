import type { Article } from "@/lib/types";
import { relativeTime } from "@/lib/format";
import { SentimentBadge } from "./SentimentBadge";
import { ImpactMeter } from "./ImpactMeter";

export function ArticleCard({
  article,
  score,
  highlight = false,
}: {
  article: Article;
  score?: number;
  highlight?: boolean;
}) {
  const when = article.published_at || article.fetched_at;
  const body = article.summary || article.description;

  return (
    <article
      className={`rounded-xl border bg-surface p-4 transition-colors ${
        highlight ? "border-accent/50 ring-1 ring-accent/30" : "border-border"
      }`}
    >
      <div className="mb-1.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted">
        <span className="font-medium text-foreground/80">{article.source}</span>
        <span aria-hidden>·</span>
        <time dateTime={when}>{relativeTime(when)}</time>
        {article.category && (
          <>
            <span aria-hidden>·</span>
            <span className="rounded bg-border/60 px-1.5 py-0.5 capitalize">
              {article.category.replace(/-/g, " ")}
            </span>
          </>
        )}
        {score != null && (
          <span className="ml-auto rounded bg-accent/15 px-1.5 py-0.5 font-medium tabular-nums text-accent">
            {(score * 100).toFixed(0)}% match
          </span>
        )}
      </div>

      <h3 className="text-[15px] font-semibold leading-snug">
        <a
          href={article.url}
          target="_blank"
          rel="noopener noreferrer"
          className="hover:underline"
        >
          {article.title}
        </a>
      </h3>

      {body && (
        <p className="mt-1.5 text-sm leading-relaxed text-foreground/80 line-clamp-3">
          {body}
        </p>
      )}

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <SentimentBadge sentiment={article.sentiment} confidence={article.confidence} />
        {article.impact_score != null && (
          <ImpactMeter score={article.impact_score} />
        )}
        {article.tickers?.map((t) => (
          <span
            key={t}
            className="rounded bg-border/60 px-1.5 py-0.5 font-mono text-[11px] font-medium text-foreground/80"
          >
            ${t}
          </span>
        ))}
      </div>
    </article>
  );
}
